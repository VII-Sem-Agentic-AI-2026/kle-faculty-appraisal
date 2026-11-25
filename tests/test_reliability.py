import threading

from conftest import sign
from app.store import hashobj,now
from app.batch import select_aligned
from app.connector import Connector


def test_three_collection_agents_execute_concurrently(env,start,monkeypatch):
    original=Connector.collect
    barrier=threading.Barrier(3,timeout=10)
    categories=[]
    lock=threading.Lock()
    def synchronized_collect(self,user,fid,category,run_id):
        with lock:categories.append(category)
        barrier.wait()
        return original(self,user,fid,category,run_id)
    monkeypatch.setattr(Connector,'collect',synchronized_collect)
    result=start()
    assert result['status']=='awaiting_quality',result
    assert sorted(categories)==['administrative','research','teaching']

def test_bounded_retry_on_unrepairable_output(env,start,monkeypatch):
    import app.workflow as workflow
    original=workflow.format_skill
    def broken(*args,**kwargs):
        out=original(*args,**kwargs);out['cycle']='unexpected-cycle';return out
    monkeypatch.setattr(workflow,'format_skill',broken)
    r=start();assert r['status']=='blocked',r
    events=[e for e in env['store'].audit_rows() if e['action']=='agent.targeted_repair'];assert len(events)==2
    assert env['store'].all('releases')==[]

def test_batch_runs_two_units_and_merge(env,start):
    # First approved faculty plan, then a second independent synthetic faculty unit.
    first=start();s=env['store'];p=s.get('plans',first['plan']['id'])
    other=env['fixture']['users']['other']
    p2={**p,'id':'second-plan','faculty_id':'demo-river','owner':other['id']}
    for cat in ['research','teaching','administrative']:
        r=s.get('records','demo-'+cat);r={**r,'id':'river-'+cat,'faculty_id':'demo-river','authors':['River Demo']};s.put('records',r)
        s.put('consents',{'id':'demo-river:'+r['source_id'],'faculty_id':'demo-river','source_id':r['source_id'],'granted':True,'actor':other['id'],'at':now()})
        s.put('evidence',{'id':'demo-river:'+r['id'],'faculty_id':'demo-river','record_id':r['id'],'status':'verified','note':'Synthetic test verification','record_hash':hashobj(r),'actor':env['fixture']['users']['hod']['id'],'reviewer':'Demo Hod','at':now()})
    p2['fingerprint']=env['main'].connector.fingerprint(other,'demo-river');s.put('plans',p2)
    c=sign(env,'hod');out=c.post('/api/batches',json={'plan_ids':[p['id'],p2['id']]});assert out.status_code==200,out.text
    rows=out.json()['runs'];assert len(rows)==2;assert all(r['status']=='awaiting_quality' for r in rows),rows
    assert all('report' not in r for r in rows)

def test_selector_rejects_changed_plan():
    p={'id':'p','cycle':'2025-26'}
    r={'id':'r','plan':{**p,'cycle':'bad'},'faculty_id':'f','status':'awaiting_quality','created':'1'}
    good,bad=select_aligned([r],[p]);assert not good and bad[0]['reason']=='Plan mismatch'

def test_login_deactivation_and_password(env):
    c=sign(env,'faculty');new='new-test-password-123456'
    assert c.post('/api/password',json={'current_password':env['fixture']['password'],'new_password':new}).status_code==200
    assert c.post('/api/login',json={'username':'demo-faculty','password':env['fixture']['password']}).status_code==401
    c=sign(env,'admin');fid=env['fixture']['users']['faculty']['id']
    assert c.post('/api/users/'+fid+'/active',json={'active':False}).status_code==200
    assert c.post('/api/login',json={'username':'demo-faculty','password':new}).status_code==401

def test_upload_create_link_consent_and_review(env):
    c=sign(env,'faculty');r=c.post('/api/sources/upload',data={'kind':'administrative'},files={'file':('order.txt',b'Synthetic office order for service','text/plain')});assert r.status_code==200,r.text
    sid=r.json()['id'];a=c.post('/api/activities',json={'faculty_id':'demo-alex','category':'administrative','kind':'committee','title':'Synthetic committee duty','value':1,'date':'2026-06-01','source_id':sid,'locator':'Order, line 1'});assert a.status_code==200,a.text
    assert c.post('/api/faculty/demo-alex/consents/'+sid,json={'granted':True}).status_code==200
    c=sign(env,'hod');assert c.post('/api/faculty/demo-alex/evidence/'+a.json()['id'],json={'status':'verified','note':'Synthetic evidence inspected for test.'}).status_code==200

def test_scoped_memory_obeys_consent(env):
    c=sign(env,'faculty');hits=c.get('/api/faculty/demo-alex/retrieve?q=research').json();assert any(r['id']=='demo-research' for r in hits['hits'])
    c.post('/api/faculty/demo-alex/consents/synthetic-research',json={'granted':False})
    hits=c.get('/api/faculty/demo-alex/retrieve?q=research').json();assert not any(r['id']=='demo-research' for r in hits['hits'])

def test_resume_after_actual_node_failure(env,start,monkeypatch):
    import app.workflow as workflow
    original=workflow.compute
    def crash(*args,**kwargs):raise RuntimeError('Injected worker outage')
    monkeypatch.setattr(workflow,'compute',crash)
    r=start();assert r['status']=='failed',r
    monkeypatch.setattr(workflow,'compute',original)
    c=sign(env,'faculty');out=c.post('/api/runs/'+r['id']+'/resume');assert out.json()['status']=='awaiting_quality',out.text
    assert out.json()['id']==r['id']

def test_duplicate_claim_detection(env,start):
    s=env['store'];r=s.get('records','demo-research');dup={**r,'id':'duplicate-paper'};s.put('records',dup)
    review=s.get('evidence','demo-alex:demo-research');s.put('evidence',{**review,'id':'demo-alex:duplicate-paper','record_id':'duplicate-paper','record_hash':hashobj(dup)})
    out=start();assert out['status']=='blocked';assert any('duplicate' in x['reason'] for x in out['errors'])


def test_explicit_faculty_mapping_wins_over_name_alias(env):
    s=env['store'];r=s.get('records','demo-research')
    wrong_alias={**r,'id':'explicit-river','faculty_id':'demo-river','authors':['Alex Demo']}
    s.put('records',wrong_alias)
    c=Connector(s);alex=env['fixture']['users']['faculty']
    river=env['fixture']['users']['other']
    assert 'explicit-river' not in {row['id'] for row in c.candidates(alex,'demo-alex')}
    assert 'explicit-river' in {row['id'] for row in c.candidates(river,'demo-river')}


def test_consent_change_requires_verified_identity_and_audit(env):
    s=env['store'];c=sign(env,'faculty')
    assert c.post('/api/faculty/demo-alex/consents/synthetic-research',json={'granted':False}).status_code==200
    assert c.post('/api/faculty/demo-alex/consents/synthetic-research',json={'granted':True}).status_code==200
    audit=[e for e in s.audit_rows() if e['action'] in ('consent.revoked','consent.granted')]
    assert audit
    assert audit[-1]['subject']=='demo-alex'
    assert audit[-1]['payload']['actor']==env['fixture']['users']['faculty']['id']
    assert audit[-1]['payload']['granted'] is True

def test_consent_cannot_be_granted_for_unverified_profile(env):
    s=env['store'];profile=s.get('profiles','demo-alex')
    s.put('profiles',{**profile,'identity_status':'pending'})
    c=sign(env,'faculty')
    response=c.post('/api/faculty/demo-alex/consents/synthetic-research',json={'granted':True})
    assert response.status_code==400
    assert 'Verify your faculty identity' in response.text
