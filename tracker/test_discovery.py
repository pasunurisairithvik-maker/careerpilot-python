import io,zipfile
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase,Client
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from .models import Job,Profile,SavedSearch,ResumeDraft,Application,FeedState
from .discovery import evidence,normalize,refresh,safe_url,plain
from .job_views import JobFilter,filtered
from .resume_tools import extract_file,docx,build_text,checks
class DiscoveryTests(TestCase):
    def setUp(self):
        self.a=get_user_model().objects.create_user('discovery-alice',password='synthetic-only-password!')
        self.b=get_user_model().objects.create_user('discovery-bob',password='synthetic-only-password!')
        for u in [self.a,self.b]:Profile.objects.create(user=u,recovery_hash=make_password('synthetic-code'),resume='Python SQL REST APIs')
        self.job=Job.objects.create(source_key='greenhouse:synthetic:1',provider='greenhouse',board='synthetic',company='Example',title='Junior Python developer',location='Remote US',description='Python SQL. OPT candidates welcome. We do not offer visa sponsorship.',url='https://example.org/job/1',role='developer',level='entry',workplace='remote',evidence=evidence('OPT candidates welcome. We do not offer visa sponsorship.'),checked=timezone.now())
        self.client.force_login(self.a)
    def test_public_pages_and_templates(self):
        c=Client()
        for p in ['/jobs/',f'/jobs/{self.job.pk}/']:
            self.assertEqual(c.get(p).status_code,200)
        self.assertContains(c.get('/jobs/'),'Example')
        self.assertContains(c.get('/jobs/'),'STEM OPT')
        for p in ['/resume/check/','/resume/build/']:
            self.assertEqual(c.get(p).status_code,302);self.assertEqual(self.client.get(p).status_code,200)
    def test_filter_combination_unknown_and_negation(self):
        unknown=Job.objects.create(source_key='lever:synthetic:2',provider='lever',board='synthetic',company='Other',title='Analyst',location='Chicago',description='SQL',url='https://example.org/job/2',role='analyst',level='unspecified',workplace='unspecified',evidence=evidence('SQL'),checked=timezone.now())
        form=JobFilter({'role':'developer','authorization':'opt','sponsorship':'no','workplace':'remote'});self.assertTrue(form.is_valid());self.assertEqual(list(filtered(form.cleaned_data)),[self.job])
        form=JobFilter({'authorization':'stem_opt'});self.assertTrue(form.is_valid());self.assertEqual(filtered(form.cleaned_data).count(),0)
        form=JobFilter({'authorization':'stem_opt','include_unknown':'on'});self.assertTrue(form.is_valid());self.assertEqual(filtered(form.cleaned_data).count(),2)
        self.assertNotContains(self.client.get('/jobs/?role=invalid'),'Junior Python developer')
        self.assertEqual(evidence('We cannot sponsor H-1B visas.')['h1b']['state'],'excluded')
        self.assertEqual(evidence('Authorized to work in the US. E-Verify employer.')['stem_opt']['state'],'unknown')
    def test_source_failure_preserves_records_and_success_closes_removed(self):
        with patch('tracker.discovery.SOURCES',[('greenhouse','synthetic','Example')]),patch('tracker.discovery.download',side_effect=TimeoutError):refresh(force=True)
        self.job.refresh_from_db();self.assertTrue(self.job.active);self.assertTrue(FeedState.objects.get(key='greenhouse:synthetic').error)
        with patch('tracker.discovery.SOURCES',[('greenhouse','synthetic','Example')]),patch('tracker.discovery.download',return_value=[]):refresh(force=True)
        self.job.refresh_from_db();self.assertFalse(self.job.active)
        self.assertEqual(FeedState.objects.get(key='greenhouse:synthetic').count,0)
    def test_upsert_and_refresh_cooldown(self):
        row={'id':1,'title':'Updated role','location':{'name':'India'},'absolute_url':'https://example.org/job/1','content':'Python'}
        with patch('tracker.discovery.SOURCES',[('greenhouse','synthetic','Example')]),patch('tracker.discovery.download',return_value=[row]):
            refresh(force=True);self.assertTrue(refresh().get('busy'))
        self.job.refresh_from_db();self.assertEqual(self.job.title,'Updated role');self.assertTrue(self.job.active);self.assertEqual(Job.objects.count(),1)
    def test_duplicate_canonical_links_not_distinct_requisitions(self):
        Job.objects.create(source_key='lever:synthetic:3',provider='lever',board='synthetic',company='Example',title='Junior Python developer',url=self.job.url,role='developer',level='entry',workplace='remote',checked=timezone.now())
        self.assertEqual(filtered({}).count(),1)
        self.assertEqual(safe_url('https://example.org/jobs/1?utm_source=a&job=1#top'),'https://example.org/jobs/1?job=1')
        self.assertEqual(safe_url('https://user:password@example.org/jobs/1'),'')
    def test_saved_search_ownership_caps_seen_alerts_and_backup(self):
        self.client.post('/searches/save/',{'name':'Python','q':'Python'})
        s=SavedSearch.objects.get(owner=self.a);self.assertContains(self.client.get('/jobs/'),'Python')
        self.client.force_login(self.b)
        self.assertNotContains(self.client.get('/jobs/'),'Open &amp; mark reviewed')
        for suffix in ['seen','remove']:self.assertEqual(self.client.post(f'/searches/{s.pk}/{suffix}/').status_code,404)
        self.client.force_login(self.a);self.client.post(f'/searches/{s.pk}/seen/');s.refresh_from_db();self.assertIsNotNone(s.seen)
        self.assertEqual(len(self.client.get('/backup/').json()['saved_searches']),1)
        for i in range(12):self.client.post('/searches/save/',{'name':str(i)})
        self.assertEqual(SavedSearch.objects.filter(owner=self.a).count(),10)
    def test_tracking_is_private_idempotent_and_post_only(self):
        p=f'/jobs/{self.job.pk}/track/'
        self.assertEqual(self.client.get(p).status_code,405)
        self.client.post(p);self.client.post(p);self.assertEqual(Application.objects.filter(owner=self.a).count(),1)
        self.client.force_login(self.b);self.client.post(p);self.assertEqual(Application.objects.filter(owner=self.b).count(),1)
    def test_csrf_protects_search_track_and_refresh(self):
        c=Client(enforce_csrf_checks=True);c.force_login(self.a)
        for p in ['/searches/save/',f'/jobs/{self.job.pk}/track/','/jobs/refresh/']:self.assertEqual(c.post(p).status_code,403)
    def builder_data(self):return {'name':'Synthetic Student','contact':'student@example.org','summary':'BTech student','skills':'Java, Python','experience':'','projects':'Built a Python CSV tool.','education':'BTech 2028','confirmed':'on'}
    def test_builder_preview_export_truthfulness_and_private_drafts(self):
        d=self.builder_data();r=self.client.post('/resume/build/',{**d,'action':'preview'});self.assertContains(r,'Synthetic Student');self.assertFalse(ResumeDraft.objects.exists())
        self.client.post('/resume/build/',{**d,'action':'save'});self.assertTrue(ResumeDraft.objects.filter(owner=self.a).exists())
        response=self.client.post('/resume/build/',{**d,'action':'docx'});f=SimpleUploadedFile('resume.docx',response.content);text=extract_file(f);self.assertIn('Built a Python CSV tool.',text);self.assertNotIn('SQL',text)
        text=build_text(d,self.job);self.assertIn('Python, Java',text);self.assertNotIn('SQL',text)
        self.assertEqual(self.client.get('/backup/').json()['resume_draft']['name'],'Synthetic Student')
        self.client.force_login(self.b);self.assertNotContains(self.client.get('/resume/build/'),'Synthetic Student')
    def test_review_does_not_save_resume_and_escapes_text(self):
        original=self.a.profile.resume
        r=self.client.post('/resume/check/',{'resume':'<script>alert(1)</script> Python','description':'Java Python'});self.assertContains(r,'&lt;script&gt;');self.assertNotContains(r,'<script>');self.a.profile.refresh_from_db();self.assertEqual(self.a.profile.resume,original)
    def test_uploads_invalid_scans_and_limits(self):
        for name,raw in [('r.pdf',b'not pdf'),('r.docx',b'not zip'),('r.txt',b'\xff'),('r.exe',b'hello'),('r.txt',b'x'*80001)]:
            with self.assertRaises(ValueError):extract_file(SimpleUploadedFile(name,raw))
        self.assertEqual(extract_file(SimpleUploadedFile('r.txt',b'Python engineer')),'Python engineer')
        from pypdf import PdfWriter
        out=io.BytesIO();writer=PdfWriter();writer.add_blank_page(width=72,height=72);writer.write(out)
        with self.assertRaises(ValueError):extract_file(SimpleUploadedFile('scan.pdf',out.getvalue()))
        bomb=io.BytesIO()
        with zipfile.ZipFile(bomb,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('word/document.xml','x'*10000001)
        with self.assertRaises(ValueError):extract_file(SimpleUploadedFile('bomb.docx',bomb.getvalue()))
    def test_feed_html_and_links_never_execute(self):
        self.assertNotIn('secret()',plain('<script>secret()</script><p>Python</p>'))
        with self.assertRaises(ValueError):normalize('greenhouse','bad','Bad',{'id':3,'title':'Job','absolute_url':'javascript:alert(1)'})
    def test_closed_and_stale_filters(self):
        self.job.checked=timezone.now()-timedelta(days=2);self.job.save()
        form=JobFilter({'fresh':'on'});self.assertTrue(form.is_valid());self.assertEqual(filtered(form.cleaned_data).count(),0)
        self.job.active=False;self.job.save();self.assertEqual(filtered({}).count(),0);self.assertEqual(filtered({'closed':True}).count(),1)
    def test_account_deletion_cascades_private_new_data(self):
        SavedSearch.objects.create(owner=self.a,name='Private');ResumeDraft.objects.create(owner=self.a,fields={'name':'Private'})
        self.a.delete();self.assertFalse(SavedSearch.objects.exists());self.assertFalse(ResumeDraft.objects.exists());self.assertTrue(Job.objects.exists())
    def test_positive_pdf_extraction_and_docx_upload_above_old_limit(self):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
        writer=PdfWriter();page=writer.add_blank_page(width=300,height=300)
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 20 200 Td (Python SQL) Tj ET');page[NameObject('/Contents')]=writer._add_object(stream)
        out=io.BytesIO();writer.write(out)
        self.assertIn('Python SQL',extract_file(SimpleUploadedFile('text.pdf',out.getvalue())))
        import os
        out=io.BytesIO(docx('Python engineer'))
        with zipfile.ZipFile(out,'a') as z:z.writestr('unused-padding.bin',os.urandom(300000))
        r=self.client.post('/resume/',{'resume_file':SimpleUploadedFile('resume.docx',out.getvalue())})
        self.assertEqual(r.status_code,302);self.a.profile.refresh_from_db();self.assertEqual(self.a.profile.resume,'Python engineer')
    def test_discovery_refinements_and_empty_recovery(self):
        f=JobFilter({'q':'SQL','title_only':'on'});self.assertTrue(f.is_valid());self.assertEqual(filtered(f.cleaned_data).count(),0)
        f=JobFilter({'q':'Python','exclude':' SQL, Java ','sort':'company'});self.assertTrue(f.is_valid());self.assertEqual(filtered(f.cleaned_data).count(),0)
        response=self.client.get('/jobs/?authorization=h1b&q=Python&location=Remote')
        self.assertContains(response,'Include unknown status listings')
        self.assertContains(response,'not imported or verified')
        self.assertContains(response,'LinkedIn')
        self.assertEqual(len(response.context['external']),4)
        self.assertEqual(response.context['available'],1)
        self.assertIn('q=Python',response.context['broader']);self.assertIn('location=Remote',response.context['broader'])
        self.assertIn('include_unknown=on',response.context['broader'])
        self.assertTrue(any('Listing mentions status' in c['label'] for c in response.context['chips']))
        self.assertNotContains(response,'<script>alert')
        self.client.post('/searches/save/',{'name':'Filtered','q':'Python','exclude':'Java','title_only':'on','sort':'title'})
        self.assertEqual(SavedSearch.objects.get(name='Filtered').filters['exclude'],'Java')
        self.assertEqual(SavedSearch.objects.get(name='Filtered').filters['sort'],'title')

    def test_new_board_initializes_during_existing_cooldown(self):
        FeedState.objects.create(key='refresh',attempted=timezone.now())
        FeedState.objects.create(key='greenhouse:synthetic',attempted=timezone.now(),success=timezone.now(),count=1)
        with patch('tracker.discovery.SOURCES',[('greenhouse','synthetic','Example'),('greenhouse','newboard','New employer')]),patch('tracker.discovery.download',return_value=[]) as fetch:
            self.assertEqual(refresh(),{'New employer':0})
            fetch.assert_called_once_with('greenhouse','newboard')
            self.assertTrue(refresh().get('busy'))
        self.job.refresh_from_db();self.assertTrue(self.job.active)

    def test_low_result_suggestions_are_counted_and_do_not_change_search(self):
        self.job.role='analyst';self.job.level='unspecified';self.job.evidence=evidence('SQL');self.job.save()
        response=self.client.get('/jobs/?role=analyst&level=entry&authorization=opt')
        self.assertEqual(response.context['total'],0)
        alternatives=response.context['suggestions']
        self.assertTrue(any(item['count']==1 and 'include_unstated=on' in item['query'] and 'include_unknown=on' in item['query'] for item in alternatives))
        self.assertContains(response,'not confirmation of suitability')
        form=JobFilter({'role':'analyst','level':'entry','authorization':'opt','include_unstated':'on','include_unknown':'on'})
        self.assertTrue(form.is_valid());self.assertEqual(filtered(form.cleaned_data).count(),1)
        self.job.level='senior';self.job.save()
        self.assertEqual(filtered(form.cleaned_data).count(),0)
        form=JobFilter({'level':'entry','include_unstated':'on','authorization':'opt'})
        self.assertTrue(form.is_valid());self.assertEqual(filtered(form.cleaned_data).count(),0)
    def test_all_discovery_sources_are_allowlisted_and_unique(self):
        from .discovery import SOURCES
        self.assertEqual(len(SOURCES),20)
        self.assertEqual(len({(p,b) for p,b,_ in SOURCES}),20)
        for provider,board,company in SOURCES:
            self.assertIn(provider,['greenhouse','lever'])
            self.assertRegex(board,r'^[a-z0-9]+$')
            self.assertTrue(company)

    def test_external_shortcuts_include_role_location_without_private_data(self):
        from urllib.parse import urlsplit,parse_qs
        response=self.client.get('/jobs/?role=analyst&location=Chicago&authorization=opt')
        for site in response.context['external']:
            params=parse_qs(urlsplit(site['url']).query)
            self.assertTrue(any('analyst' in values for values in params.values()))
            self.assertTrue(any('Chicago' in values for values in params.values()))
            self.assertNotIn('authorization',params)
            self.assertNotIn('resume',params)
