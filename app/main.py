"""Authenticated local application. All consequential actions are server-gated."""
import hashlib,json,os,time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from fastapi import FastAPI,Request,Response,Depends,UploadFile,File,Form,HTTPException
from fastapi.responses import FileResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
from .store import Store,ROOT,uid,now,hashobj
from .security import fail,require_role,scope,login,create_user,public_user
from .connector import Connector
from .contracts import PlanInput,PolicyInput,ActivityInput,Decision,EvidenceDecision
from .skills import plan_skill
from .workflow import Runtime
from .memory import retrieve

store=Store();connector=Connector(store);runtime=Runtime(store)
@asynccontextmanager
async def lifespan(app):
    store.seed();yield
app=FastAPI(title='KLE Faculty Appraisal',version='1.0.0',lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
@app.middleware('http')
async def headers(req,call_next):
    if req.headers.get('content-length','0').isdigit() and int(req.headers.get('content-length','0'))>12*1024*1024:return JSONResponse({'detail':'Maximum request size is 12 MB.'},413)
    res=await call_next(req)
    res.headers.update({'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'same-origin',
        'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",'Cache-Control':'no-store'})
    return res

def actor(req:Request):
    token=hashlib.sha256(req.cookies.get('session','').encode()).hexdigest()
    with store.tx() as db:r=db.execute('SELECT * FROM sessions WHERE token=? AND expires>?',(token,time.time())).fetchone()
    if not r:fail('Please sign in.',401)
    user=store.get('users',r['user_id'])
    if not user or not user['active']:fail('Account inactive.',401)
    if req.method not in ('GET','HEAD','OPTIONS') and req.headers.get('x-csrf-token')!=r['csrf']:fail('Invalid request token. Refresh the page.',403)
    return user
class LoginBody(BaseModel):username:str=Field(max_length=100);password:str=Field(max_length=500)
@app.post('/api/login')
def sign_in(body:LoginBody,res:Response):
    result=login(store,body.username,body.password)
    if not result:fail('Incorrect username or password.',401)
    token,csrf,user=result;res.set_cookie('session',token,httponly=True,samesite='strict',secure=os.getenv('COOKIE_SECURE')=='1',max_age=28800)
    return {'user':public_user(user),'csrf':csrf}
@app.get('/api/me')
def me(req:Request,u=Depends(actor)):
    with store.tx() as db:r=db.execute('SELECT csrf FROM sessions WHERE token=?',(hashlib.sha256(req.cookies['session'].encode()).hexdigest(),)).fetchone()
    return {'user':public_user(u),'csrf':r['csrf']}
@app.post('/api/logout')
def logout(req:Request,res:Response,u=Depends(actor)):
    with store.tx() as db:db.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(req.cookies['session'].encode()).hexdigest(),))
    res.delete_cookie('session');return {'ok':True}
@app.get('/api/health')
def health():return {'status':'ok','version':'1.0.0'}

@app.get('/api/profiles')
def profiles(u=Depends(actor)):
    return [p for p in store.all('profiles') if u['role']!='faculty' or p['id']==u['faculty_id']]
@app.post('/api/profiles')
def new_profile(body:dict,u=Depends(actor)):
    require_role(u,'admin');name=str(body.get('name','')).strip()
    if len(name)<3:fail('Enter the faculty member’s full name.')
    p={'id':'fac-'+uid()[:10],'name':name,'source_name':name,'department':'Computer Science and Engineering','identity_status':'pending','aliases':[name]}
    store.put('profiles',p);store.audit(u['id'],'profile.create',p['id'],p);return p
@app.post('/api/profiles/{fid}/verify')
def verify_profile(fid:str,body:dict,u=Depends(actor)):
    require_role(u,'admin');p=connector.profile(u,fid);note=str(body.get('note',''));sid=body.get('source_id');source=store.get('sources',sid)
    if len(note)<5 or not source or not connector.intact(sid):fail('Identity review needs an intact source and a verification note.')
    aliases=body.get('aliases',p['aliases'])
    if not isinstance(aliases,list) or not aliases or any(not isinstance(a,str) or not a.strip() for a in aliases):fail('Provide a non-empty list of name aliases.')
    from .importer import key
    for other in store.all('profiles'):
        if other['id']!=fid and other['identity_status']=='verified' and {key(a) for a in other['aliases']}&{key(a) for a in aliases}:fail('An alias is already bound to another verified profile.')
    p.update(identity_status='verified',aliases=aliases,identity_review={'actor':u['id'],'source_id':sid,'note':note,'at':now()})
    store.put('profiles',p);store.audit(u['id'],'identity.verify',fid,p['identity_review']);return p
@app.get('/api/users')
def users(u=Depends(actor)):require_role(u,'admin');return [public_user(x) for x in store.all('users')]
@app.post('/api/users')
def user_create(body:dict,u=Depends(actor)):
    require_role(u,'admin');v=create_user(store,str(body.get('username','')),str(body.get('name','')),str(body.get('password','')),body.get('role'),body.get('faculty_id'))
    store.audit(u['id'],'user.create',v['id'],public_user(v));return public_user(v)

@app.post('/api/password')
def password_change(body:dict,req:Request,u=Depends(actor)):
    from .security import check_password,password_hash
    old=str(body.get('current_password',''));new=str(body.get('new_password',''))
    if not check_password(old,u['password']):fail('Current password is incorrect.',403)
    if len(new)<12:fail('New password must contain at least 12 characters.')
    with store.tx() as db:
        u['password']=password_hash(new);store.put('users',u)
        current=hashlib.sha256(req.cookies['session'].encode()).hexdigest()
        db.execute('DELETE FROM sessions WHERE user_id=? AND token!=?',(u['id'],current))
        store.audit(u['id'],'auth.password_change',u['id'],{})
    return {'ok':True}
@app.post('/api/users/{user_id}/active')
def user_active(user_id:str,body:dict,u=Depends(actor)):
    require_role(u,'admin');target=store.get('users',user_id)
    if not target or not isinstance(body.get('active'),bool):fail('Choose an account and active state.')
    if user_id==u['id']:fail('You cannot deactivate your own administrator session.')
    with store.tx() as db:
        target['active']=body['active'];store.put('users',target)
        if not target['active']:db.execute('DELETE FROM sessions WHERE user_id=?',(user_id,))
        store.audit(u['id'],'user.active',user_id,{'active':target['active']})
    return public_user(target)

@app.get('/api/sources')
def sources(u=Depends(actor)):
    allowed=None
    if u['role']=='faculty':allowed={r['source_id'] for r in connector.candidates(u,u['faculty_id'])}|{s['id'] for s in store.all('sources') if s.get('owner')==u['id']}
    return [{**s,'intact':connector.intact(s['id'])} for s in store.all('sources') if allowed is None or s['id'] in allowed]
@app.get('/api/sources/{sid}/download')
def source_download(sid:str,u=Depends(actor)):
    s=store.get('sources',sid)
    if not s:fail('Source not found.',404)
    if u['role']=='faculty' and s.get('owner')!=u['id']:fail('Department source documents contain other faculty data. Use your scoped record view.',403)
    store.audit(u['id'],'source.download',sid,{})
    return FileResponse(connector.source_path(s),filename=s['name'],media_type='application/octet-stream')
@app.post('/api/sources/upload')
async def upload(file:UploadFile=File(...),kind:str=Form(...),u=Depends(actor)):
    if kind not in ('research','teaching','administrative','policy','identity'):fail('Invalid source type.')
    if kind in ('policy','identity'):require_role(u,'admin','dean','iqac')
    blob=await file.read(10*1024*1024+1)
    if not blob or len(blob)>10*1024*1024:fail('Upload a file of up to 10 MB.')
    name=Path(file.filename or 'evidence').name
    if Path(name).suffix.lower() not in ('.pdf','.png','.jpg','.jpeg','.csv','.txt','.xlsx'):fail('Supported: PDF, PNG, JPG, CSV, TXT and XLSX.')
    sid=uid();folder=store.path.parent/'uploads';folder.mkdir(exist_ok=True);(folder/sid).write_bytes(blob)
    s={'id':sid,'name':name,'kind':kind,'sha256':hashlib.sha256(blob).hexdigest(),'bytes':len(blob),'owner':u['id'],'uploaded':True,'created':now()}
    store.put('sources',s);store.audit(u['id'],'source.upload',sid,{k:v for k,v in s.items() if k!='owner'});return s

@app.get('/api/faculty/{fid}/records')
def records(fid:str,u=Depends(actor)):
    rs=connector.candidates(u,fid)
    return [{**r,'raw':r['raw'] if u['role']!='faculty' else None,'provenance':r.get('provenance',[]) if u['role']!='faculty' else [],'review':store.get('evidence',fid+':'+r['id']),'consent':store.get('consents',fid+':'+r['source_id'])} for r in rs]
@app.get('/api/faculty/{fid}/consents')
def consents(fid:str,u=Depends(actor)):
    scope(u,fid);return [r for r in store.all('consents') if r['faculty_id']==fid]
@app.post('/api/faculty/{fid}/consents/{sid}')
def consent(fid:str,sid:str,body:dict,u=Depends(actor)):
    require_role(u,'faculty');scope(u,fid)
    profile=store.get('profiles',fid)
    if not profile or profile.get('identity_status')!='verified':fail('Verify your faculty identity before managing source consent.')
    source=store.get('sources',sid)
    if not source:fail('Unknown source.',404)
    if not connector.intact(sid):fail('Consent source is missing or has changed. Restore the original intact file.')
    if sid not in {r['source_id'] for r in connector.candidates(u,fid)}:fail('Source has no activity assigned to your profile.')
    if not isinstance(body.get('granted'),bool):fail('Choose grant or revoke.')
    previous=store.get('consents',fid+':'+sid)
    granted=body['granted']
    v={'id':fid+':'+sid,'faculty_id':fid,'source_id':sid,'granted':granted,'actor':u['id'],'at':now()}
    store.put('consents',v)
    store.audit(u['id'],'consent.granted' if granted else 'consent.revoked',fid,{
        'faculty_id':fid,'source_id':sid,'granted':granted,'actor':u['id'],'at':v['at'],
        'previous':previous
    })
    return v
@app.post('/api/activities')
def activity(body:ActivityInput,u=Depends(actor)):
    require_role(u,'faculty');scope(u,body.faculty_id);connector.profile(u,body.faculty_id)
    try:d=date.fromisoformat(body.date)
    except ValueError:fail('Use an ISO date: YYYY-MM-DD.')
    if not date(2025,8,1)<=d<=date(2026,7,31):fail('Activity date must be within 1 Aug 2025 – 31 Jul 2026.')
    source=store.get('sources',body.source_id)
    if not source or not connector.intact(source['id']):fail('Attach an intact evidence source.')
    if u['role']=='faculty' and source.get('owner')!=u['id']:fail('Use evidence uploaded by your account.',403)
    a={**body.model_dump(exclude={'date'}),'id':'activity-'+uid(),'year':d.year,'month':d.month,'students':body.students or 0,'authors':[],'raw':body.model_dump(),'created':now()}
    store.put('records',a);store.audit(u['id'],'activity.create',body.faculty_id,a);return a
@app.post('/api/faculty/{fid}/evidence/{rid}')
def evidence(fid:str,rid:str,body:EvidenceDecision,u=Depends(actor)):
    require_role(u,'hod','dean','iqac');rows=connector.candidates(u,fid);r=next((r for r in rows if r['id']==rid),None)
    if not r:fail('Record is outside this faculty scope.',404)
    if body.status=='verified' and not connector.intact(r['source_id']):fail('Cannot verify missing or changed evidence.')
    v={**body.model_dump(),'id':fid+':'+rid,'faculty_id':fid,'record_id':rid,'record_hash':hashobj(r),'actor':u['id'],'reviewer':u['name'],'at':now()}
    store.put('evidence',v);store.audit(u['id'],'evidence.'+body.status,fid,v);return v

@app.get('/api/policies')
def policies(u=Depends(actor)):return store.all('policies')
@app.post('/api/policies')
def policy_create(body:PolicyInput,u=Depends(actor)):
    require_role(u,'dean','iqac');s=store.get('sources',body.source_id)
    if not s or s['kind']!='policy' or not connector.intact(s['id']):fail('Upload the policy document first.')
    p={**body.model_dump(),'id':uid(),'status':'draft','created_by':u['id'],'created':now()};store.put('policies',p);store.audit(u['id'],'policy.draft',p['id'],p);return p
@app.post('/api/policies/{pid}/approve')
def policy_approve(pid:str,body:dict,u=Depends(actor)):
    require_role(u,'dean','iqac');p=store.get('policies',pid)
    if not p or p['status']!='draft':fail('Only a draft policy can be approved.',409)
    if len(str(body.get('note','')))<5:fail('Enter the institutional approval reference.')
    if not connector.intact(p['source_id']):fail('Policy source changed.')
    p.update(status='approved',approved_by=u['id'],approved_name=u['name'],approved_at=now(),approval_note=body['note']);store.put('policies',p);store.audit(u['id'],'policy.approve',pid,p);return p

@app.post('/api/planner/clarify')
def clarify(body:dict,u=Depends(actor)):
    questions=[]
    if not body.get('faculty_id'):questions.append('Which faculty member should this appraisal cover?')
    if not body.get('policy_id'):questions.append('Which institution-approved policy and track apply?')
    if not body.get('completeness'):questions.append('Are research, teaching and administrative records complete for this cycle?')
    return {'questions':questions,'outline':['Confirm identity and consent','Lock scope and policy','Collect three activity areas in parallel','Validate every claim','Calculate using approved rules','Obtain quality review, HoD endorsement and final release']}
@app.post('/api/plans')
def plan_create(body:PlanInput,u=Depends(actor)):
    require_role(u,'faculty');scope(u,body.faculty_id);p=connector.profile(u,body.faculty_id);policy=connector.policy(body.policy_id)
    if p['identity_status']!='verified':fail('Identity review is required.')
    if policy['profile']!=body.profile or policy['cycle']!=body.cycle:fail('Policy must match cycle and specialist track.')
    if set(body.completeness)!={'research','teaching','administrative'} or any(len(str(v).strip())<5 for v in body.completeness.values()):fail('Provide a completeness declaration for all three areas, including any confirmed nil activity.')
    plan=plan_skill(body,connector.fingerprint(u,body.faculty_id),policy);plan['owner']=u['id'];store.put('plans',plan);store.audit(u['id'],'plan.draft',body.faculty_id,plan);return plan
@app.get('/api/plans')
def plans(u=Depends(actor)):return [p for p in store.all('plans') if u['role']!='faculty' or p['faculty_id']==u['faculty_id']]
@app.post('/api/plans/{pid}/lock')
def plan_lock(pid:str,u=Depends(actor)):
    p=store.get('plans',pid)
    if not p or p['owner']!=u['id']:fail('Only the plan owner can lock it.',403)
    if p['status']!='draft':fail('Plan is already locked.',409)
    p.update(status='locked',fingerprint=connector.fingerprint(u,p['faculty_id']),locked_at=now());store.put('plans',p);store.audit(u['id'],'plan.lock',p['faculty_id'],{'id':pid,'hash':hashobj(p)});return p

def visible_run(u,r):
    scope(u,r['faculty_id']);result=dict(r)
    # Faculty and technical administrators cannot inspect unpublished API scores.
    if r['status']!='published' and (u['role'] in ('faculty','admin') or (u['role']=='hod' and r['status'] not in ('awaiting_hod','awaiting_release'))):
        result.pop('report',None)
    return result
@app.get('/api/runs')
def runs(u=Depends(actor)):
    return [visible_run(u,r) for r in store.all('runs') if u['role']!='faculty' or r['faculty_id']==u['faculty_id']]
@app.post('/api/batches')
def batch_create(body:dict,u=Depends(actor)):
    require_role(u,'hod','dean','iqac')
    ids=body.get('plan_ids',[])
    if not isinstance(ids,list) or not 1<=len(ids)<=10 or len(set(ids))!=len(ids):fail('Select one to ten distinct locked plans.')
    plans=[store.get('plans',pid) for pid in ids]
    if any(p is None for p in plans):fail('Unknown plan.')
    from .batch import run_batch
    results,rejected=run_batch(store,runtime,connector,plans,u)
    return {'runs':[visible_run(u,r) for r in results],'rejected':rejected}

@app.get('/api/runs/{rid}')
def run_read(rid:str,u=Depends(actor)):
    r=store.get('runs',rid)
    if not r:fail('Run not found.',404)
    return visible_run(u,r)
@app.post('/api/runs')
def run_create(body:dict,u=Depends(actor)):
    p=store.get('plans',body.get('plan_id'))
    if not p or p['owner']!=u['id']:fail('Only the faculty plan owner can start this run.',403)
    if p['status']!='locked':fail('Lock the plan before running it.')
    if connector.fingerprint(u,p['faculty_id'])!=p['fingerprint']:fail('Data changed after locking. Create a revised plan.',409)
    r={'id':uid(),'plan':p,'faculty_id':p['faculty_id'],'owner':u['id'],'status':'running','created':now(),'node_count':0}
    store.put('runs',r);store.audit(u['id'],'run.start',r['id'],{'faculty_id':r['faculty_id'],'plan_hash':hashobj(p)})
    try:runtime.drive(r['id'])
    except Exception:pass
    return visible_run(u,store.get('runs',r['id']))
@app.post('/api/runs/{rid}/resume')
def run_resume(rid:str,u=Depends(actor)):
    r=store.get('runs',rid)
    if not r:fail('Run not found.',404)
    if u['id']!=r['owner'] and u['role']!='admin':fail('Only the run owner or administrator may resume.',403)
    if r['status'] not in ('failed','running'):fail('This run is not interrupted by a failure.',409)
    if connector.fingerprint(store.get('users',r['owner']),r['faculty_id'])!=r['plan']['fingerprint']:fail('Inputs changed; create a revised plan.',409)
    try:runtime.drive(rid,resume=True)
    except Exception:pass
    return visible_run(u,store.get('runs',rid))
@app.post('/api/runs/{rid}/decision')
def run_decide(rid:str,body:Decision,u=Depends(actor)):
    with runtime.lock(rid):
        r=store.get('runs',rid)
        if not r:fail('Run not found.',404)
        stage=r['status'].removeprefix('awaiting_');roles={'quality':('dean','iqac'),'hod':('hod',),'release':('dean','iqac')}
        if stage not in roles:fail('This run is not awaiting review.',409)
        require_role(u,*roles[stage])
        if not all(c['passed'] for c in r.get('checks',[])) or not r.get('checks'):fail('Validation must pass before human review.',409)
        if body.rating_override and body.action!='override':fail('Use an explicit override action for a rating override.')
        policy=connector.policy(r['plan']['policy_id'])
        if body.rating_override and body.rating_override not in {b['label'] for b in policy['bands']}:fail('Override must use a rating from the approved policy.')
        decision={**body.model_dump(),'actor':u['id'],'reviewer':u['name'],'role':u['role'],'at':now()}
        store.audit(u['id'],'review.decision',rid,decision)
        try:runtime.drive(rid,decision=decision)
        except Exception:pass
        return visible_run(u,store.get('runs',rid))

@app.get('/api/releases')
def releases(u=Depends(actor)):
    return [{**r,'active':(store.get('active',r['faculty_id']) or {}).get('release_id')==r['id']} for r in store.all('releases') if u['role']!='faculty' or r['faculty_id']==u['faculty_id']]
@app.post('/api/releases/{rid}/rollback')
def rollback(rid:str,body:dict,u=Depends(actor)):
    require_role(u,'dean','iqac');r=store.get('releases',rid)
    if not r or len(str(body.get('note','')))<5:fail('Select a released version and give a rollback reason.')
    with store.tx():
        previous=store.get('active',r['faculty_id']);store.put('active',{'id':r['faculty_id'],'release_id':rid})
        store.audit(u['id'],'release.rollback',r['faculty_id'],{'previous':previous,'restored':rid,'reason':body['note']})
    return {'ok':True}
@app.post('/api/releases/{rid}/appeal')
def appeal(rid:str,body:dict,u=Depends(actor)):
    require_role(u,'faculty');r=store.get('releases',rid)
    if not r:fail('Release not found.',404)
    scope(u,r['faculty_id'])
    if len(str(body.get('note','')))<10:fail('Describe the requested correction.')
    a={'id':uid(),'release_id':rid,'faculty_id':r['faculty_id'],'note':body['note'],'status':'open','created':now(),'actor':u['id']};store.put('appeals',a);store.audit(u['id'],'appeal.open',r['faculty_id'],a);return a
@app.get('/api/appeals')
def appeals(u=Depends(actor)):return [a for a in store.all('appeals') if u['role']!='faculty' or a['faculty_id']==u['faculty_id']]
@app.post('/api/appeals/{aid}/resolve')
def resolve_appeal(aid:str,body:dict,u=Depends(actor)):
    require_role(u,'hod','dean','iqac');a=store.get('appeals',aid)
    if not a or len(str(body.get('note','')))<10:fail('Provide a reasoned appeal decision.')
    a.update(status='resolved',resolution=body['note'],resolved_by=u['name'],resolved_at=now());store.put('appeals',a);store.audit(u['id'],'appeal.resolve',a['faculty_id'],a);return a

@app.get('/api/audit')
def audit(u=Depends(actor)):
    # Raw traces can contain unpublished scores; restricted to the quality authorities.
    require_role(u,'dean','iqac');return {'valid':store.verify_audit(),'events':store.audit_rows()}
@app.get('/api/faculty/{fid}/retrieve')
def search(fid:str,q:str,category:str|None=None,u=Depends(actor)):
    if len(q)>500:fail('Search must be 500 characters or fewer.')
    return retrieve(store,u,fid,q,category)
@app.get('/api/readiness')
def readiness(u=Depends(actor)):
    output=[]
    for p in profiles(u):
        rows=connector.candidates(u,p['id']);areas={}
        for category in ('research','teaching','administrative'):
            items=[r for r in rows if r['category']==category]
            verified=sum((store.get('evidence',p['id']+':'+r['id']) or {}).get('status')=='verified' for r in items)
            areas[category]={'total':len(items),'verified':verified,'percent':round(100*verified/len(items)) if items else None}
        output.append({'id':p['id'],'areas':areas})
    return output

@app.get('/api/overview')
def overview(u=Depends(actor)):
    ps=profiles(u);rs=runs(u);records_count=sum(len(connector.candidates(u,p['id'])) for p in ps)
    return {'profiles':len(ps),'verified_profiles':sum(p['identity_status']=='verified' for p in ps),'publication_records':len([r for r in store.all('records') if r['category']=='research']) if u['role']!='faculty' else len(connector.candidates(u,u['faculty_id'],'research')),
        'feedback_rows':len([r for r in store.all('records') if r['category']=='teaching']) if u['role']!='faculty' else len(connector.candidates(u,u['faculty_id'],'teaching')),
        'awaiting_review':sum(r['status'].startswith('awaiting_') for r in rs),'released':len(releases(u)),
        'cycle':'2025–26','notes':store.get('meta','import')['notes'],'engine':'LangGraph · SQLite checkpoints','llm':'Ollama local' if os.getenv('OLLAMA_MODEL') else 'Deterministic report assembly'}
@app.get('/api/releases/{rid}/export')
def export(rid:str,u=Depends(actor)):
    r=store.get('releases',rid)
    if not r:fail('Released report not found.',404)
    scope(u,r['faculty_id'])
    from .reports import render_pdf
    blob=render_pdf(r);store.audit(u['id'],'release.export',r['faculty_id'],{'release_id':rid})
    return Response(blob,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="appraisal-v{r["version"]}.pdf"'})
app.mount('/assets',StaticFiles(directory=ROOT/'web/assets'),name='assets')
@app.get('/')
def index():return FileResponse(ROOT/'web/index.html')
