"""SQLite repository, atomic mutations and hash-linked audit events."""
import contextlib, hashlib, json, os, sqlite3, threading, uuid
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def now():return datetime.now(timezone.utc).isoformat()
def uid():return uuid.uuid4().hex
def canonical(obj):return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def hashobj(obj):return hashlib.sha256(canonical(obj).encode()).hexdigest()
class Store:
    def __init__(self,path=None):
        self.path=Path(path or os.getenv('APP_DB',ROOT/'runtime/app.db'));self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.local=threading.local()
        with self.tx() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS entities(kind TEXT,id TEXT,data TEXT,PRIMARY KEY(kind,id));
            CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY AUTOINCREMENT,time TEXT,actor TEXT,action TEXT,subject TEXT,payload TEXT,previous TEXT,hash TEXT);
            CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT,csrf TEXT,expires REAL);
            CREATE TABLE IF NOT EXISTS failures(name TEXT PRIMARY KEY,count INTEGER,until REAL);''')
    @contextlib.contextmanager
    def tx(self):
        if getattr(self.local,'db',None) is not None:
            yield self.local.db;return
        with self.lock:
            db=sqlite3.connect(self.path,timeout=30);db.row_factory=sqlite3.Row;db.execute('PRAGMA journal_mode=WAL');self.local.db=db
            try:
                db.execute('BEGIN IMMEDIATE');yield db;db.commit()
            except BaseException:db.rollback();raise
            finally:self.local.db=None;db.close()
    def get(self,kind,id,default=None):
        with self.tx() as db:r=db.execute('SELECT data FROM entities WHERE kind=? AND id=?',(kind,id)).fetchone()
        return json.loads(r['data']) if r else default
    def all(self,kind):
        with self.tx() as db:rows=db.execute('SELECT data FROM entities WHERE kind=? ORDER BY id',(kind,)).fetchall()
        return [json.loads(r['data']) for r in rows]
    def put(self,kind,item):
        with self.tx() as db:db.execute('INSERT INTO entities VALUES(?,?,?) ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data',(kind,item['id'],canonical(item)))
        return item
    def audit(self,actor,action,subject,payload):
        with self.tx() as db:
            last=db.execute('SELECT hash FROM audit ORDER BY seq DESC LIMIT 1').fetchone();prev=last['hash'] if last else '0'*64
            e={'time':now(),'actor':actor,'action':action,'subject':subject,'payload':payload,'previous':prev};h=hashobj(e)
            db.execute('INSERT INTO audit(time,actor,action,subject,payload,previous,hash) VALUES(?,?,?,?,?,?,?)',(e['time'],actor,action,subject,canonical(payload),prev,h))
    def audit_rows(self):
        with self.tx() as db:rs=db.execute('SELECT * FROM audit ORDER BY seq').fetchall()
        return [{**dict(r),'payload':json.loads(r['payload'])} for r in rs]
    def verify_audit(self):
        previous='0'*64
        for r in self.audit_rows():
            data={k:r[k] for k in ('time','actor','action','subject','payload','previous')}
            if r['previous']!=previous or r['hash']!=hashobj(data):return False
            previous=r['hash']
        return True
    def seed(self):
        if self.get('meta','import'):return
        seed=json.loads((ROOT/'data/seed.json').read_text(encoding='utf-8'))
        with self.tx():
            for s in seed['sources']:self.put('sources',s)
            for p in seed['profiles']:self.put('profiles',p)
            from .importer import key
            for a in seed['research']+seed['feedback']:
                if a.get('category')=='teaching' and not a.get('faculty_id'):
                    matches=[]
                    for p in seed['profiles']:
                        aliases=p.get('aliases') or [p.get('source_name') or p.get('name')]
                        if any(key(author) in {key(alias) for alias in aliases} for author in a.get('authors',[])):
                            matches.append(p)
                    if len(matches)==1:a=dict(a,faculty_id=matches[0]['id'])
                self.put('records',a)
            self.put('meta',{'id':'import','cycle':seed['cycle'],'notes':seed['notes'],'issues':seed['issues'],'created':now()})
            self.audit('system','sources.staged','import',{'research':len(seed['research']),'feedback':len(seed['feedback']),'source_hashes':[s['sha256'] for s in seed['sources']]})
