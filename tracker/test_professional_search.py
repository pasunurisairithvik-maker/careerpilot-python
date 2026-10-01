from django.test import TestCase
from django.utils import timezone
from tracker.models import Job,FeedState
from tracker.job_views import JobFilter,filtered
class ProfessionalSearchTests(TestCase):
 def test_unknown_inclusion_never_includes_known_conflicts(self):
  for i,description in enumerate(['Full-time role.','Part-time role.','Employment details not supplied.']):
   Job.objects.create(source_key=f'synthetic:{i}',provider='greenhouse',board='synthetic',company='Example',title='Analyst',description=description,url=f'https://example.org/{i}',role='analyst',checked=timezone.now())
  form=JobFilter({'employment':'full_time','include_employment_unknown':'on'});self.assertTrue(form.is_valid())
  self.assertEqual(set(filtered(form.cleaned_data).values_list('source_key',flat=True)),{'synthetic:0','synthetic:2'})
  form=JobFilter({'employment':'full_time'});self.assertTrue(form.is_valid());self.assertEqual(filtered(form.cleaned_data).count(),1)
 def test_configured_boards_are_not_reported_as_successful(self):
  FeedState.objects.create(key='ashby:ramp',error='HTTPError',count=0)
  response=self.client.get('/jobs/')
  self.assertEqual(response.context['reporting_sources'],0);self.assertEqual(response.context['failed_sources'],1)
  self.assertContains(response,'boards with cached data / 38 configured')
