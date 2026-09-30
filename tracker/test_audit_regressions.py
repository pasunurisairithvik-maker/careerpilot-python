import io,json
from unittest.mock import patch,MagicMock
from urllib.error import HTTPError
from django.test import SimpleTestCase,TestCase
from .discovery import classify,seniority,download,normalize

class AuditRegressionTests(SimpleTestCase):
    def test_negation_after_sponsorship_and_us_abbreviation(self):
        from .discovery import evidence
        for text in ['Visa sponsorship is not available.','Visa sponsorship is not offered for this role.']:
            self.assertEqual(evidence(text)['sponsorship']['state'],'no')
        for text in ['Must be a U.S. citizen.','U.S. citizenship is required.']:
            self.assertNotEqual(evidence(text)['citizen']['state'],'unknown')

    def test_written_experience_years_are_not_ignored(self):
        from .job_presentation import experience_requirement
        for text,years in [('Five years of professional experience required.',5),('At least three years of experience.',3),('One year of experience.',1)]:
            result=experience_requirement(text)
            self.assertEqual(result['years'],years)
            self.assertIn(text.rstrip('.'),result['quote'])

    def test_abbreviations_and_title_word_boundaries(self):
        for title,role in [('SRE','cloud'),('Senior SRE','cloud'),('UX Researcher','design'),('UI Engineer','design')]:
            self.assertEqual(classify(title),role)
        for title in ['Internal Auditor','International Analyst','Leadership Development Associate']:
            self.assertNotEqual(seniority(title),'intern')
        self.assertEqual(seniority('Intern, Software Engineering'),'intern')
        self.assertEqual(seniority('Associate Director'),'senior')

    def response(self):
        response=MagicMock();response.__enter__.return_value=response
        response.read.return_value=json.dumps({'jobs':[]}).encode()
        return response

    def test_timeout_recovers_once_and_is_bounded(self):
        opener=MagicMock();opener.open.side_effect=[TimeoutError(),self.response()]
        with patch('tracker.discovery.urllib.request.build_opener',return_value=opener):
            self.assertEqual(download('greenhouse','synthetic'),[])
        self.assertEqual(opener.open.call_count,2)
        self.assertEqual(opener.open.call_args.kwargs['timeout'],12)
        opener.open.reset_mock();opener.open.side_effect=TimeoutError()
        with patch('tracker.discovery.urllib.request.build_opener',return_value=opener):
            with self.assertRaises(TimeoutError):download('greenhouse','synthetic')
        self.assertEqual(opener.open.call_count,2)

    def test_only_transient_http_statuses_retry(self):
        for status,retries in [(404,1),(401,1),(429,2),(503,2)]:
            opener=MagicMock();opener.open.side_effect=HTTPError('https://example.org',status,'synthetic',{},None)
            with patch('tracker.discovery.urllib.request.build_opener',return_value=opener):
                with self.assertRaises(HTTPError):download('greenhouse','synthetic')
            self.assertEqual(opener.open.call_count,retries)

    def test_malformed_payload_does_not_retry_or_invent_a_title(self):
        response=self.response();response.read.return_value=b'not json'
        opener=MagicMock();opener.open.return_value=response
        with patch('tracker.discovery.urllib.request.build_opener',return_value=opener):
            with self.assertRaises(ValueError):download('greenhouse','synthetic')
        self.assertEqual(opener.open.call_count,1)
        for value in [None,{},123,'']:
            with self.assertRaises(ValueError):normalize('greenhouse','synthetic','Example',{'id':1,'title':value,'absolute_url':'https://example.org/jobs/1'})

class SearchMatrixTests(TestCase):
    def test_public_label_checkpoint_resumes_after_interruption(self):
        from django.core.management import call_command
        from django.utils import timezone
        from .models import Job,FeedState
        jobs=[Job.objects.create(source_key=f'synthetic:resume:{i}',provider='greenhouse',board='synthetic',company='Example',title='SRE',role='other',url=f'https://example.org/job/{i}',checked=timezone.now()) for i in range(2)]
        FeedState.objects.create(key='normalization-v6',count=jobs[0].pk)
        call_command('reclassify_jobs',stdout=io.StringIO())
        jobs[0].refresh_from_db();jobs[1].refresh_from_db()
        self.assertEqual(jobs[0].role,'other');self.assertEqual(jobs[1].role,'cloud')
        self.assertIsNotNone(FeedState.objects.get(key='normalization-v6').success)

    def test_failed_feed_can_recover_without_refreshing_healthy_boards(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import FeedState
        from .discovery import refresh
        now=timezone.now()
        FeedState.objects.create(key='refresh',attempted=now)
        failed=FeedState.objects.create(key='greenhouse:broken',error='TimeoutError',attempted=now-timedelta(minutes=4))
        FeedState.objects.create(key='greenhouse:healthy',attempted=now,success=now)
        with patch('tracker.discovery.SOURCES',[('greenhouse','broken','Broken'),('greenhouse','healthy','Healthy')]),patch('tracker.discovery.download',return_value=[]) as download:
            self.assertTrue(refresh().get('busy'));download.assert_not_called()
            failed.attempted=now-timedelta(minutes=6);failed.save()
            self.assertEqual(refresh(),{'Broken':0})
            download.assert_called_once_with('greenhouse','broken')
            failed.refresh_from_db();self.assertEqual(failed.error,'');self.assertIsNotNone(failed.success)

    def test_existing_cache_relabels_without_changing_source_or_freshness(self):
        from django.core.management import call_command
        from django.utils import timezone
        from .models import Job
        checked=timezone.now()
        job=Job.objects.create(source_key='synthetic:relabel',provider='greenhouse',board='synthetic',company='Example',title='SRE',role='other',level='intern',description='Visa sponsorship is not available.',url='https://example.org/job',checked=checked)
        call_command('reclassify_jobs',stdout=io.StringIO())
        job.refresh_from_db()
        self.assertEqual(job.role,'cloud');self.assertEqual(job.level,'unspecified')
        self.assertEqual(job.evidence['sponsorship']['state'],'no')
        self.assertEqual(job.checked,checked);self.assertTrue(job.active)
        with patch('tracker.management.commands.reclassify_jobs.classify') as classify:
            call_command('reclassify_jobs',stdout=io.StringIO());classify.assert_not_called()

    def test_public_filter_combinations_and_query_bound(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from django.utils import timezone
        from .models import Job
        from .discovery import evidence
        Job.objects.bulk_create([Job(source_key=f'synthetic:{i}',provider='greenhouse',board='synthetic',company='Example',title='Junior Analyst',role='analyst',level='entry',description='1 year of experience. SQL. OPT applicants welcome. We do not offer visa sponsorship.',evidence=evidence('OPT applicants welcome. We do not offer visa sponsorship.'),url=f'https://example.org/jobs/{i}',checked=timezone.now()) for i in range(25)])
        with CaptureQueriesContext(connection) as queries:
            response=self.client.get('/jobs/')
        self.assertEqual(response.status_code,200)
        self.assertLess(len(queries),10)
        self.assertContains(response,'not offered')
        for query,count in [('role=analyst&level=entry&authorization=opt&sponsorship=no',25),('role=analyst&authorization=stem_opt',0),('authorization=stem_opt&include_unknown=on',25),('role=qa',0),('level=senior',0),('q=SQL&title_only=on',0),('q=SQL',25),('exclude=SQL',0),('provider=lever',0)]:
            response=self.client.get('/jobs/?'+query)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.context['total'],count,query)
        self.assertEqual(len(self.client.get('/jobs/?page=999').context['page']),5)
        self.assertEqual(self.client.get('/jobs/?role=invalid').context['total'],0)
