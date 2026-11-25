from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main
from conftest import sign
from app.store import hashobj

def decide(env,rid,role,action='approve',**extra):
    c=sign(env,role);return c.post(f'/api/runs/{rid}/decision',json={'action':action,'note':'Reviewed synthetic evidence and calculation.',**extra})

def test_end_to_end_gate_export_and_rollback(env,start):
    r=start();assert r['status']=='awaiting_quality',r
    rid=r['id'];assert 'report' not in r
    c=sign(env,'hod');assert 'report' not in c.get('/api/runs/'+rid).json()
    assert decide(env,rid,'faculty').status_code==403
    q=decide(env,rid,'dean');assert q.json()['status']=='awaiting_hod',q.text
    assert q.json()['report']['score']['total']==60
    assert decide(env,rid,'iqac').status_code==403
    h=decide(env,rid,'hod');assert h.json()['status']=='awaiting_release',h.text
    c=sign(env,'faculty');assert c.get('/api/releases').json()==[]
    f=decide(env,rid,'iqac');assert f.json()['status']=='published',f.text
    assert decide(env,rid,'iqac').status_code==409
    c=sign(env,'faculty');release=c.get('/api/releases').json()[0]
    pdf=c.get(f"/api/releases/{release['id']}/export");assert pdf.status_code==200 and pdf.content.startswith(b'%PDF')
    env['store'].path.parent.joinpath('test-report.pdf').write_bytes(pdf.content)
    a=c.post(f"/api/releases/{release['id']}/appeal",json={'note':'Synthetic appeal: please review the source date.'});assert a.status_code==200
    c=sign(env,'iqac');assert c.post('/api/appeals/'+a.json()['id']+'/resolve',json={'note':'Checked source and retained the approved result.'}).status_code==200
    assert c.post(f"/api/releases/{release['id']}/rollback",json={'note':'Restore this approved historical version.'}).status_code==200
    assert env['store'].verify_audit()

def test_overview_release_count_tracks_releases_without_changing_other_metrics(env,start):
    c=sign(env,'iqac')
    before=c.get('/api/overview').json()
    assert before['released']==0
    run=start();rid=run['id']
    decide(env,rid,'dean');decide(env,rid,'hod')
    assert c.get('/api/overview').json()['released']==0
    assert decide(env,rid,'iqac').json()['status']=='published'
    after=c.get('/api/overview').json()
    assert after['released']==len(env['store'].all('releases'))==1
    assert {key:after[key] for key in ('profiles','publication_records','feedback_rows')} == {
        key:before[key] for key in ('profiles','publication_records','feedback_rows')
    }
    assert env['store'].verify_audit()

def test_cross_faculty_isolation_and_source_download(env,start):
    r=start();c=sign(env,'other')
    for url in ['/api/faculty/demo-alex/records','/api/faculty/demo-alex/consents','/api/runs/'+r['id'],'/api/faculty/demo-alex/retrieve?q=research']:
        assert c.get(url).status_code==403,url
    assert c.get('/api/sources/synthetic-research/download').status_code==403
    assert c.get('/api/audit').status_code==403
    assert c.get('/data/seed.json').status_code==404
    assert len(c.get('/api/profiles').json())==1

def test_missing_consent_hard_gate(env,start):
    s=env['store'];c=s.get('consents','demo-alex:synthetic-research');c['granted']=False;s.put('consents',c)
    r=start();assert r['status']=='blocked';assert any('consent' in x['reason'] for x in r['errors']);assert not s.all('releases')

def test_missing_evidence_hard_gate(env,start):
    s=env['store'];r=s.get('evidence','demo-alex:demo-research');r['status']='flagged';s.put('evidence',r)
    out=start();assert out['status']=='blocked';assert not s.all('releases')

def test_changed_source_blocks(env,start):
    (env['store'].path.parent/'uploads/synthetic-teaching').write_text('tampered')
    r=start();assert r['status']=='blocked'

def test_revoked_consent_during_review_prevents_publish(env,start):
    r=start();rid=r['id'];decide(env,rid,'dean');decide(env,rid,'hod')
    c=sign(env,'faculty');assert c.post('/api/faculty/demo-alex/consents/synthetic-teaching',json={'granted':False}).status_code==200
    result=decide(env,rid,'iqac').json();assert result['status']=='blocked';assert env['store'].all('releases')==[]

def test_policy_required_and_profile_matched(env):
    s=env['store'];p=s.get('policies','synthetic-policy');p['status']='draft';s.put('policies',p)
    c=sign(env,'faculty');r=c.post('/api/plans',json={'faculty_id':'demo-alex','policy_id':'synthetic-policy','request':'Prepare an appraisal','completeness':{'research':'complete','teaching':'complete','administrative':'complete'}})
    assert r.status_code==409

def test_csrf_and_role_permissions(env):
    c=sign(env,'faculty');c.headers.pop('X-CSRF-Token');assert c.post('/api/logout').status_code==403
    c=sign(env,'faculty');assert c.post('/api/users',json={}).status_code==403;assert c.post('/api/policies/synthetic-policy/approve',json={'note':'Attempt bypass'}).status_code==403

def test_rate_limit_is_persistent(env):
    c=env['client']
    for i in range(8):assert c.post('/api/login',json={'username':'demo-faculty','password':'incorrect'}).status_code==401
    assert c.post('/api/login',json={'username':'demo-faculty','password':env['fixture']['password']}).status_code==429

def test_return_and_rating_override(env,start):
    r=start();returned=decide(env,r['id'],'dean','return');assert returned.json()['status']=='returned'
    r=start();decide(env,r['id'],'dean');decide(env,r['id'],'hod')
    f=decide(env,r['id'],'iqac','override',rating_override='Excellent (synthetic)').json();assert f['status']=='published';assert f['report']['score']['total']==60;assert f['report']['final_rating']=='Excellent (synthetic)'

def test_audit_tamper_detection(env):
    s=env['store'];assert s.verify_audit()
    with s.tx() as db:db.execute("UPDATE audit SET action='changed' WHERE seq=1")
    assert not s.verify_audit()

def test_stale_evidence_and_no_matching_rule(env,start):
    s=env['store'];r=s.get('records','demo-research');r['title']='Changed title after verification';s.put('records',r)
    out=start();assert out['status']=='blocked'

def test_checkpoint_survives_runtime_recreation(env,start):
    from app.workflow import Runtime
    r=start();env['main'].runtime=Runtime(env['store']);result=decide(env,r['id'],'dean');assert result.json()['status']=='awaiting_hod',result.text

def test_targeted_repair_after_injected_citation_fault(env,start,monkeypatch):
    import app.workflow as workflow
    original=workflow.format_skill;count=[0]
    def broken_once(*args,**kwargs):
        out=original(*args,**kwargs);count[0]+=1
        if count[0]==1:out['evidence']=[]
        return out
    monkeypatch.setattr(workflow,'format_skill',broken_once)
    r=start();assert r['status']=='awaiting_quality',r
    assert any(x['action']=='agent.targeted_repair' for x in env['store'].audit_rows())


def test_frontend_shell_exposes_workflow_controls():
    html = Path(__file__).resolve().parents[1] / 'web' / 'index.html'
    text = html.read_text(encoding='utf-8')
    for marker in ['id="login"', 'id="shell"', 'id="nav"', 'id="main"', 'id="modal"', 'id="toast"', 'FACULTY APPRAISAL MANAGEMENT']:
        assert marker in text, marker


def test_frontend_asset_wires_the_complete_appraisal_workflow(env):
    response = env['client'].get('/')
    assert response.status_code == 200
    assert '/assets/app.js' in response.text
    assert '/assets/style.css' in response.text
    script = env['client'].get('/assets/app.js')
    assert script.status_code == 200
    for action in ["actions.upload", "actions.consent", "actions.revoke", "actions['add-activity']",
                   "actions['new-plan']", "actions['lock-plan']", "actions['start-run']",
                   "actions.run", "actions.release", "actions.appeal", "actions.rollback",
                   "actions.resolve"]:
        assert action in script.text, action
    for endpoint in ["/activities", "/consents/", "/evidence/", "/plans", "/runs",
                     "/decision", "/export", "/appeals/", "/rollback", "/audit"]:
        assert endpoint in script.text, endpoint


def test_new_faculty_activity_runs_through_governed_release_history(env):
    def login(client, role):
        response = client.post('/api/login', json={
            'username': f'demo-{role}',
            'password': env['fixture']['password'],
        })
        assert response.status_code == 200, response.text
        client.headers['X-CSRF-Token'] = response.json()['csrf']
        return client

    with TestClient(main.app) as faculty_client, TestClient(main.app) as reviewer_client, \
            TestClient(main.app) as dean_client, TestClient(main.app) as hod_client, \
            TestClient(main.app) as iqac_client:
        faculty = login(faculty_client, 'faculty')
        activity_body = {
            'faculty_id': 'demo-alex',
            'category': 'administrative',
            'kind': 'committee',
            'title': 'Faculty senate committee service',
            'value': 1,
            'students': 0,
            'date': '2026-06-01',
            'source_id': 'synthetic-administrative',
            'locator': 'Synthetic evidence, line 2',
        }
        reviewer = login(reviewer_client, 'hod')
        assert reviewer.post('/api/activities', json=activity_body).status_code == 403

        upload = faculty.post(
            '/api/sources/upload',
            data={'kind': 'administrative'},
            files={'file': ('faculty-senate.txt', b'Synthetic committee evidence for this test.', 'text/plain')},
        )
        assert upload.status_code == 200, upload.text
        activity_body['source_id'] = upload.json()['id']
        created = faculty.post('/api/activities', json=activity_body)
        assert created.status_code == 200, created.text
        record_id = created.json()['id']
        consent = faculty.post(f"/api/faculty/demo-alex/consents/{upload.json()['id']}", json={'granted': True})
        assert consent.status_code == 200, consent.text

        reviewed = reviewer.post(
            f'/api/faculty/demo-alex/evidence/{record_id}',
            json={'status': 'verified', 'note': 'Checked the submitted order and its activity locator.'},
        )
        assert reviewed.status_code == 200, reviewed.text

        plan = faculty.post('/api/plans', json={
            'faculty_id': 'demo-alex',
            'cycle': '2025-26',
            'profile': 'balanced',
            'policy_id': 'synthetic-policy',
            'request': 'Prepare a complete synthetic appraisal from verified evidence.',
            'completeness': {
                'research': 'All available research records reviewed.',
                'teaching': 'All available teaching records reviewed.',
                'administrative': 'Committee service recorded above.',
            },
        })
        assert plan.status_code == 200, plan.text
        plan_id = plan.json()['id']
        assert faculty.post(f'/api/plans/{plan_id}/lock').status_code == 200

        def release_run():
            prior_releases = len(env['store'].all('releases'))
            run_response = faculty.post('/api/runs', json={'plan_id': plan_id})
            assert run_response.status_code == 200, run_response.text
            run = run_response.json()
            assert run['status'] == 'awaiting_quality', run
            assert len(env['store'].all('releases')) == prior_releases
            assert login(dean_client, 'dean').post(
                f"/api/runs/{run['id']}/decision",
                json={'action': 'approve', 'note': 'Quality review confirms evidence and policy alignment.'},
            ).json()['status'] == 'awaiting_hod'
            assert len(env['store'].all('releases')) == prior_releases
            assert login(hod_client, 'hod').post(
                f"/api/runs/{run['id']}/decision",
                json={'action': 'approve', 'note': 'HoD endorses the documented faculty appraisal.'},
            ).json()['status'] == 'awaiting_release'
            assert len(env['store'].all('releases')) == prior_releases
            published = login(iqac_client, 'iqac').post(
                f"/api/runs/{run['id']}/decision",
                json={'action': 'approve', 'note': 'IQAC authorizes controlled report publication.'},
            )
            assert published.status_code == 200, published.text
            assert published.json()['status'] == 'published'
            return published.json()

        first = release_run()
        first_release = first['release_id']
        assert first['report']['score']['total'] > 0
        assert any(item['record_id'] == record_id for item in first['report']['evidence'])
        second = release_run()
        second_release = second['release_id']

        history = faculty.get('/api/releases').json()
        versions = {release['id']: release['version'] for release in history}
        assert versions[first_release] == 1
        assert versions[second_release] == 2
        assert next(r for r in history if r['id'] == second_release)['active']
        pdf = faculty.get(f'/api/releases/{second_release}/export')
        assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF')

        appeal = faculty.post(
            f'/api/releases/{second_release}/appeal',
            json={'note': 'Please recheck the committee order citation in this release.'},
        )
        assert appeal.status_code == 200, appeal.text
        iqac = login(iqac_client, 'iqac')
        resolved = iqac.post(
            f"/api/appeals/{appeal.json()['id']}/resolve",
            json={'note': 'The committee order citation was reviewed; the release remains unchanged.'},
        )
        assert resolved.status_code == 200, resolved.text
        rollback = iqac.post(
            f'/api/releases/{first_release}/rollback',
            json={'note': 'Restore version one after the documented release review.'},
        )
        assert rollback.status_code == 200, rollback.text
        history = faculty.get('/api/releases').json()
        assert next(r for r in history if r['id'] == first_release)['active']
        assert next(r for r in history if r['id'] == second_release)['active'] is False
        audit = iqac.get('/api/audit').json()
        assert audit['valid']
        assert any(event['action'] == 'activity.create' for event in audit['events'])
        assert any(event['action'] == 'release.rollback' for event in audit['events'])


def test_human_driven_ui_workflow_matches_api_journey(env,start):
    def login(client, role):
        response = client.post('/api/login', json={'username': f'demo-{role}', 'password': env['fixture']['password']})
        assert response.status_code == 200, response.text
        client.headers['X-CSRF-Token'] = response.json()['csrf']
        return client

    faculty_client = TestClient(main.app)
    dean_client = TestClient(main.app)
    hod_client = TestClient(main.app)
    iqac_client = TestClient(main.app)
    faculty = login(faculty_client, 'faculty')
    overview = faculty.get('/api/overview').json()
    readiness = faculty.get('/api/readiness').json()
    assert overview['cycle'] == '2025–26'
    assert readiness and len(readiness) >= 1
    run = start()
    assert run['status'] in {'awaiting_quality', 'blocked'}
    if run['status'] == 'blocked':
        assert run['errors']
        return
    rid = run['id']
    assert login(dean_client, 'dean').post(f'/api/runs/{rid}/decision', json={'action': 'approve', 'note': 'Reviewed synthetic evidence and calculation.'}).json()['status'] == 'awaiting_hod'
    assert login(hod_client, 'hod').post(f'/api/runs/{rid}/decision', json={'action': 'approve', 'note': 'Reviewed synthetic evidence and calculation.'}).json()['status'] == 'awaiting_release'
    assert login(iqac_client, 'iqac').post(f'/api/runs/{rid}/decision', json={'action': 'approve', 'note': 'Reviewed synthetic evidence and calculation.'}).json()['status'] == 'published'
    release = faculty.get('/api/releases').json()[0]
    assert release['report']['final_rating']
    appeal = faculty.post(f"/api/releases/{release['id']}/appeal", json={'note': 'Faculty review indicates a source reference should be rechecked.'})
    assert appeal.status_code == 200, appeal.text
    result = login(iqac_client, 'iqac').post(f"/api/appeals/{appeal.json()['id']}/resolve", json={'note': 'Institutional review confirmed the published result remains valid.'})
    assert result.status_code == 200, result.text
    rollback = login(iqac_client, 'iqac').post(f"/api/releases/{release['id']}/rollback", json={'note': 'Restore the approved historical version for traceability.'})
    assert rollback.status_code == 200, rollback.text
