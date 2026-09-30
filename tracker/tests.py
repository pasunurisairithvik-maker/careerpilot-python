from datetime import date,timedelta
from django.test import TestCase,Client,override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Application,Profile
from .matching import analyse,contains
from .views import valid_recovery_code
User=get_user_model()
class WorkflowTests(TestCase):
    def setUp(self):
        self.password='synthetic-private-pass-912!'
        self.a=User.objects.create_user('alice',password=self.password);self.b=User.objects.create_user('bob',password=self.password)
        Profile.objects.create(user=self.a,recovery_hash=make_password('recovery-alice'),resume='Built a Python API using SQL and unit tests.')
        Profile.objects.create(user=self.b,recovery_hash=make_password('recovery-bob'))
        self.item=Application.objects.create(owner=self.a,company='ExampleCo',role='Backend intern',description='Python SQL Java',due=date.today()+timedelta(days=3),next_step='Prepare demo')
        self.client.force_login(self.a)
    def data(self):return {'company':'SyntheticCo','role':'Python intern','description':'Python and Django','stage':'saved','source_url':'https://example.org/jobs/1','requirements':'','notes':'','next_step':'Review requirements','due':''}
    def test_public_pages(self):
        c=Client()
        for p in ['/','/privacy/','/login/','/signup/','/recover/','/livez','/healthz']:self.assertEqual(c.get(p).status_code,200)
    def test_private_pages_require_authentication(self):
        c=Client()
        for p in ['/dashboard/','/resume/','/export/','/backup/','/calendar/','/account/','/archived/']:self.assertEqual(c.get(p).status_code,302)
    def test_owner_isolation(self):
        self.client.force_login(self.b)
        for suffix in ['/','/edit/','/archive/']:
            path=f'/applications/{self.item.pk}'+suffix
            r=self.client.post(path) if suffix=='/archive/' else self.client.get(path)
            self.assertEqual(r.status_code,404)
        self.assertNotContains(self.client.get('/dashboard/'),'ExampleCo');self.assertNotContains(self.client.get('/export/'),'ExampleCo')
        self.assertEqual(self.client.get('/backup/').json()['applications'],[])
    def test_application_deletion_requires_archive_owner_password_and_confirmation(self):
        p=f'/applications/{self.item.pk}/delete/'
        self.assertEqual(self.client.post(p,{'password':self.password,'confirmation':'DELETE'}).status_code,404)
        self.item.archived=True;self.item.save()
        self.client.post(p,{'password':'wrong','confirmation':'DELETE'});self.assertTrue(Application.objects.filter(pk=self.item.pk).exists())
        self.client.post(p,{'password':self.password,'confirmation':'DELETE'});self.assertFalse(Application.objects.filter(pk=self.item.pk).exists())
    def test_create_edit_and_match(self):
        r=self.client.post('/applications/new/',self.data());self.assertEqual(r.status_code,302)
        item=Application.objects.get(company='SyntheticCo')
        d=self.data();d['stage']='interview';self.client.post(f'/applications/{item.pk}/edit/',d)
        item.refresh_from_db();self.assertEqual(item.stage,'interview')
        self.assertContains(self.client.get(f'/applications/{self.item.pk}/'),'Built a Python API')
    def test_invalid_stage_rejected(self):
        d=self.data();d['stage']='invented';self.assertEqual(self.client.post('/applications/new/',d).status_code,200);self.assertFalse(Application.objects.filter(company='SyntheticCo').exists())
    def test_duplicate_submission(self):
        import uuid
        d=self.data();d['submission_id']=str(uuid.uuid4())
        self.client.post('/applications/new/',d);self.client.post('/applications/new/',d)
        self.assertEqual(Application.objects.filter(company='SyntheticCo').count(),1)
        d['role']='changed';r=self.client.post('/applications/new/',d);self.assertContains(r,'already saved with different data')
    def test_csrf_required(self):
        c=Client(enforce_csrf_checks=True);c.force_login(self.a)
        for p in ['/applications/new/','/resume/',f'/applications/{self.item.pk}/archive/','/account/recovery/','/account/delete/']:self.assertEqual(c.post(p).status_code,403)
    def test_archive_and_restore(self):
        p=f'/applications/{self.item.pk}/archive/'
        self.assertEqual(self.client.get(p).status_code,405)
        self.client.post(p);self.item.refresh_from_db();self.assertTrue(self.item.archived)
        self.assertContains(self.client.get('/archived/'),'ExampleCo')
        self.client.post(p);self.item.refresh_from_db();self.assertFalse(self.item.archived)
    def test_resume_import_bounds(self):
        file=SimpleUploadedFile('resume.txt',b'Python and Django')
        self.assertEqual(self.client.post('/resume/',{'resume_file':file}).status_code,302)
        self.a.profile.refresh_from_db();self.assertEqual(self.a.profile.resume,'Python and Django')
        for name,raw in [('resume.pdf',b'PDF'),('resume.txt',b'x'*80001),('resume.txt',b'\xff'),('resume.txt',b'a\x00b')]:
            r=self.client.post('/resume/',{'resume_file':SimpleUploadedFile(name,raw)});self.assertEqual(r.status_code,200)
            self.a.profile.refresh_from_db();self.assertEqual(self.a.profile.resume,'Python and Django')
    def test_resume_can_be_cleared(self):
        self.client.post('/resume/',{'resume':''});self.a.profile.refresh_from_db();self.assertEqual(self.a.profile.resume,'')
    def test_exports_and_formula_protection(self):
        self.item.company='=DANGEROUS()';self.item.save()
        self.assertContains(self.client.get('/export/'),"'=DANGEROUS()")
        backup=self.client.get('/backup/').json();self.assertEqual(backup['resume'],self.a.profile.resume);self.assertEqual(len(backup['applications']),1)
    def test_calendar_escape_and_privacy(self):
        self.item.company='A\nB;C';self.item.save()
        r=self.client.get('/calendar/');self.assertContains(r,'BEGIN:VALARM');self.assertContains(r,'A\\nB\\;C')
        self.client.force_login(self.b);self.assertNotContains(self.client.get('/calendar/'),'Backend intern')
    def test_html_escaping(self):
        self.item.company='<script>alert(1)</script>';self.item.save()
        self.assertContains(self.client.get('/dashboard/'),'&lt;script&gt;');self.assertNotContains(self.client.get('/dashboard/'),'<script>')
    def test_url_validation(self):
        for url in ['javascript:alert(1)','https://name:password@example.org/job']:
            d=self.data();d['source_url']=url;self.assertEqual(self.client.post('/applications/new/',d).status_code,200)
            self.assertFalse(Application.objects.filter(company='SyntheticCo').exists())
    @override_settings(MAX_APPLICATIONS=1)
    def test_quota_includes_archive(self):
        self.item.archived=True;self.item.save();r=self.client.post('/applications/new/',self.data());self.assertContains(r,'Account limit')
    def test_recovery_and_single_use(self):
        self.client.logout();d={'username':'alice','recovery_code':'recovery-alice','password1':'different-private-882!','password2':'different-private-882!'}
        r=self.client.post('/recover/',d);self.assertContains(r,'Save your recovery code');self.client.logout();self.assertContains(self.client.post('/recover/',d),'incorrect')
    def test_recovery_key_independence(self):
        with override_settings(SECRET_KEY='new-key'):
            self.assertTrue(valid_recovery_code('recovery-alice',self.a.profile.recovery_hash))
    def test_recovery_replacement_authentication(self):
        self.client.post('/account/recovery/',{'password':'wrong'});self.a.profile.refresh_from_db();self.assertTrue(valid_recovery_code('recovery-alice',self.a.profile.recovery_hash))
        r=self.client.post('/account/recovery/',{'password':self.password});self.a.profile.refresh_from_db();self.assertTrue(valid_recovery_code(r.context['code'],self.a.profile.recovery_hash))
    def test_delete_account_requires_password_and_confirmation(self):
        self.client.post('/account/delete/',{'password':'wrong','confirmation':'DELETE'});self.assertTrue(User.objects.filter(pk=self.a.pk).exists())
        self.client.post('/account/delete/',{'password':self.password,'confirmation':'DELETE'});self.assertFalse(User.objects.filter(pk=self.a.pk).exists());self.assertTrue(User.objects.filter(pk=self.b.pk).exists());self.assertFalse(Application.objects.filter(owner_id=self.a.pk).exists())
    def test_timezone_and_pages(self):
        for path in ['/resume/','/account/','/archived/','/account/password/']:self.assertEqual(self.client.get(path).status_code,200)
        self.client.post('/account/',{'timezone':'UTC'});self.a.profile.refresh_from_db();self.assertEqual(self.a.profile.timezone,'UTC')
    def test_request_headers(self):
        r=self.client.get('/dashboard/');self.assertEqual(r['Cache-Control'],'no-store');self.assertEqual(len(r['X-Request-ID']),32);self.assertIn("script-src 'none'",r['Content-Security-Policy'])
    def test_signup_and_normalized_login(self):
        self.client.logout();r=self.client.post('/signup/',{'username':'NewUser','password1':self.password,'password2':self.password});self.assertContains(r,'Save your recovery code')
        self.client.post('/logout/');self.assertEqual(self.client.post('/login/',{'username':'NEWUSER','password':self.password}).status_code,302)
    def test_database_failure_is_retryable(self):
        from unittest.mock import patch
        from django.db import OperationalError
        with patch('tracker.views.Application.objects.filter',side_effect=OperationalError('private database details')):
            r=self.client.get('/dashboard/');self.assertEqual(r.status_code,503);self.assertNotContains(r,'private database',status_code=503)
class MatchingTests(TestCase):
    def test_boundaries_and_aliases(self):
        self.assertFalse(contains('JavaScript','Java'));self.assertFalse(contains('legitimate','Git'));self.assertTrue(contains('C++ developer','C++'))
        r=analyse('Python Java PostgreSQL','Python and Postgres project');self.assertEqual(r['matched'],2);self.assertEqual(r['total'],3)
    def test_custom_phrases_and_empty_requirements(self):
        r=analyse('Unknown domain','Built a sorting engine','sorting engine\nsorting engine');self.assertEqual(r['total'],1);self.assertEqual(r['coverage'],100)
        self.assertIsNone(analyse('Unknown domain','Python')['coverage'])
    def test_evidence_preserves_context(self):
        r=analyse('Java','No Java experience');self.assertEqual(r['rows'][0]['evidence'],'No Java experience')
