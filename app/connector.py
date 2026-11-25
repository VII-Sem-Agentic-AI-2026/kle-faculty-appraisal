"""Single governed tool surface used by every data-facing agent."""
import hashlib
from pathlib import Path
from .store import ROOT,hashobj,now
from .importer import key
from .security import fail,scope
class Connector:
    def __init__(self,store):self.store=store
    def profile(self,user,fid):
        scope(user,fid);p=self.store.get('profiles',fid)
        if not p:fail('Faculty profile not found.',404)
        return p
    def candidates(self,user,fid,category=None):
        p=self.profile(user,fid);aliases={key(a) for a in p['aliases']}
        records=[]
        for r in self.store.all('records'):
            explicit_fid=r.get('faculty_id')
            assigned=explicit_fid==fid if explicit_fid else any(key(a) in aliases for a in r.get('authors',[]))
            if assigned and (not category or r['category']==category):
                records.append(r)
        return records
    def source_path(self,source):
        if source.get('uploaded'):return self.store.path.parent/'uploads'/source['id']
        return ROOT/'data/source'/source['name']
    def intact(self,sid):
        s=self.store.get('sources',sid)
        if not s:return False
        p=self.source_path(s)
        return p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==s['sha256']
    def fingerprint(self,user,fid):
        records=self.candidates(user,fid)
        return hashobj({'profile':self.profile(user,fid),'records':records,
            'consents':[c for c in self.store.all('consents') if c['faculty_id']==fid],
            'evidence':[self.store.get('evidence',fid+':'+r['id']) for r in records]})
    def collect(self,user,fid,category,run_id):
        self.profile(user,fid);items=[];errors=[]
        for r in self.candidates(user,fid,category):
            consent=self.store.get('consents',fid+':'+r['source_id'])
            if not consent or not consent['granted']:
                errors.append({'id':r['id'],'reason':'Source consent missing or revoked','source_id':r['source_id']});continue
            review=self.store.get('evidence',fid+':'+r['id'])
            s=self.store.get('sources',r['source_id'])
            items.append({**r,'evidence':review,'source_hash':s['sha256'],'source_name':s['name']})
        self.store.audit(user['id'],'connector.read',run_id,{'faculty_id':fid,'category':category,'input_ids':[r['id'] for r in self.candidates(user,fid,category)],'output_ids':[r['id'] for r in items],'errors':errors})
        return {'items':items,'errors':errors}
    def policy(self,pid):
        p=self.store.get('policies',pid)
        if not p or p['status']!='approved':fail('An approved policy is required.',409)
        if not self.intact(p['source_id']):fail('Policy source is missing or changed.',409)
        return p
    def history(self,user,fid):
        scope(user,fid)
        return [r for r in self.store.all('releases') if r['faculty_id']==fid]
