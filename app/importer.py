"""Reproducible, offline source extraction. Originals remain unchanged."""
import hashlib, json, re, unicodedata
from pathlib import Path
from openpyxl import load_workbook
from pypdf import PdfReader
ROOT = Path(__file__).resolve().parents[1]
def clean(v):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKC', str(v or '')) if unicodedata.category(c) != 'Cf').split())
def key(v):
    return re.sub(r'[^a-z0-9]', '', re.sub(r'^(dr|prof|mr|mrs|ms)\.?\s+', '', clean(v), flags=re.I).lower())
def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def extract(folder=None):
    folder = Path(folder or ROOT / 'data/source');sources=[];research={};feedback=[];issues=[]
    for p in sorted(folder.iterdir()):
        sources.append({'id':digest(p)[:16], 'label':{'image(20261011-041549).png':'Teaching staff directory / page 1','image(20261011-041558).png':'Teaching staff directory / page 2','image(20261011-041604).png':'Technical staff directory','image(20261011-041612).png':'Non-teaching staff directory / 2025-26','image(20261011-041620).png':'Staff directory / 2026-27 odd semester','image(20261011-041859).png':'Official website / visual reference','KLETECH_LOGO_JPG.jpg.jpeg':'University logo','Pasted text(20261011-041417).txt':'Worklet 8 / complete specification'}.get(p.name,p.name), 'name':p.name,'sha256':digest(p),'bytes':p.stat().st_size,
                        'kind': 'research' if p.suffix=='.xlsx' else 'teaching' if p.suffix=='.pdf' else 'reference'})
    src={s['name']:s for s in sources}
    for p in folder.glob('*.xlsx'):
        for sheet in load_workbook(p, data_only=True):
            rows=list(sheet.values);headers=[clean(x) for x in rows[0]]
            for n,row in enumerate(rows[1:],2):
                if not any(x is not None for x in row):continue
                raw={h:v.isoformat() if hasattr(v,'isoformat') else v for h,v in zip(headers,row)}
                pid=clean(raw.get('PUB ID'));title=clean(raw.get('PUBLICATION TITLE'))
                if not pid or not title:
                    issues.append({'source':p.name,'row':n,'issue':'Missing publication ID or title'});continue
                rec={'id':'pub-'+pid,'category':'research','kind':{'Conference':'conference','Journal':'journal','Book Chapter':'book_chapter','PrePrint':'preprint'}.get(clean(raw.get('ARTICLE TYPE')),'other'),
                     'title':title,'authors':[clean(x) for x in str(raw.get('HOME AUTHORS') or '').split(';') if clean(x)],
                     'year':raw.get('YEAR'),'month':raw.get('MONTH'),'doi':clean(raw.get('DOI')),'venue':clean(raw.get('SOURCE PUBLICATION')),
                     'abstract':clean(raw.get('ABSTRACT')),'value':1,'source_id':src[p.name]['id'],
                     'locator':f'{sheet.title}!G{n} (PUB ID {pid})','raw':raw,'provenance':[]}
                prov={'sheet':sheet.title,'row':n,'source_id':src[p.name]['id'],'raw':raw}
                if rec['id'] in research:
                    if key(research[rec['id']]['title'])!=key(title):issues.append({'id':rec['id'],'issue':'Conflicting titles across sheets'})
                    research[rec['id']]['provenance'].append(prov)
                else:rec['provenance'].append(prov);research[rec['id']]=rec
    for p in folder.glob('*.pdf'):
        mode='formative' if p.name.lower().startswith('formative') else 'summative'
        for page_no,page in enumerate(PdfReader(p).pages,1):
            for line in (page.extract_text() or '').splitlines():
                m=re.match(r'^\s*(\d+)\s+(.+?)\s*(CS,[46][A-Z])\s+(.+)$',line)
                if not m:continue
                tokens=m[4].split()
                try:
                    nums=[float(x) for x in tokens[-17:]]
                    assert len(nums)==17 and all(0<=x<=8 for x in nums[:14]) and 0<=nums[-2]<=100
                except (ValueError,AssertionError):issues.append({'source':p.name,'page':page_no,'issue':'Unparsed course line','line':line});continue
                title=' '.join(tokens[:-17]);name=clean(m[2]);rid=f'{mode}-{m[3]}-{m[1]}'
                feedback.append({'id':rid,'category':'teaching','kind':'feedback_'+mode,'title':title,'authors':[name],
                    'division':m[3],'questions':nums[:14],'total':nums[-3],'value':nums[-2],
                    'students':int(nums[-1]),'year':2026,'month':6,'source_id':src[p.name]['id'],
                    'locator':f'Page {page_no}, {m[3]}, row {m[1]}','raw':{'line':line},
                    'quality_flags':(['Small cohort (<5 responses)'] if nums[-1]<5 else [])+(['Truncated source name or subject'] if '....' in name+title else [])})
    names=sorted({x['authors'][0] for x in feedback})
    profiles=[{'id':'fac-'+hashlib.sha256(key(n).encode()).hexdigest()[:10],'name':n.title(),'source_name':n,
        'department':'Computer Science and Engineering','identity_status':'pending','aliases':[n]} for n in names]
    faculty_by_name={key(p['aliases'][0]):p['id'] for p in profiles}
    for row in feedback:
        row['faculty_id']=faculty_by_name.get(key(row['authors'][0]))
    return {'sources':sources,'research':list(research.values()),'feedback':feedback,'profiles':profiles,'issues':issues,
        'cycle':'2025-26','start':'2025-08-01','end':'2026-07-31','notes':[
        'Research workbook is a supplied snapshot, not a live integration.',
        'HOME AUTHORS includes students; never treat every author as a faculty member.',
        'PDF page 6 mentions 2026-2027, whereas the cover says Even Term 2026: cycle confirmation required.',
        'Name variants require human mapping; exact normalization is only a candidate match.',
        'No approved API rubric or administrative activity evidence was supplied.']}
if __name__=='__main__':
    data=extract();(ROOT/'data/seed.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'publications':len(data['research']),'feedback_rows':len(data['feedback']),'faculty_candidates':len(data['profiles']),'issues':data['issues']},indent=2))
