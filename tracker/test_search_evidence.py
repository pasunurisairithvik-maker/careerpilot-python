from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from itertools import product
from .discovery import evidence, classify
from .job_traits import workplace
from .models import Job
from .job_views import filtered

class EvidenceRegressions(SimpleTestCase):
 def test_explicit_visa_support(self):
  for text in ['We do sponsor and take over sponsorship of employment visas for this role.', 'We will sponsor employment visas.']:
   self.assertEqual(evidence(text)['sponsorship']['state'],'yes')
  for text in ['We do not sponsor employment visas.', 'We are unable to sponsor employment visas.']:
   self.assertEqual(evidence(text)['sponsorship']['state'],'no')
 def test_company_remote_benefits_do_not_override_attendance(self):
  for text in ['Four days a week in the office. We have a fully remote program.', 'We require three coordinated days in the office per week. Four weeks of fully remote work is a perk.']:
   self.assertEqual(workplace('San Francisco',text)[0],'hybrid')
  self.assertEqual(workplace('San Francisco','Our fully remote program is a benefit.')[0],'unspecified')
 def test_nonsoftware_engineering_not_developer(self):
  for title in ['Associate Process Engineer','Industrial Engineering Intern']:
   self.assertNotEqual(classify(title),'developer')
  for title in ['Software Engineer','Embedded Software Engineer']:
   self.assertEqual(classify(title),'developer')

class FilterMatrix(TestCase):
 def test_role_level_workplace_status_and_sponsorship_intersections(self):
  fixtures=[]
  for i,(role,level,place,status,sponsor) in enumerate(product(['developer','analyst'],['entry','senior'],['remote','hybrid'],['stated','unknown'],['yes','no'])):
   fixtures.append(Job(source_key=f'synthetic:matrix:{i}',provider='greenhouse',board='synthetic',company='Synthetic',title='Synthetic listing',role=role,level=level,workplace=place,description='1 year of experience.' if level=='entry' else '6 years of experience.',evidence={'opt':{'state':status,'evidence':[]},'sponsorship':{'state':sponsor,'evidence':[]}},url=f'https://example.org/{i}',checked=timezone.now()))
  Job.objects.bulk_create(fixtures)
  for role,level,place,sponsor,unknown in product(['developer','analyst'],['entry','senior'],['remote','hybrid'],['yes','no'],[False,True]):
   data=dict(role=role,level=level,workplace=place,sponsorship=sponsor,authorization='opt',include_unknown=unknown)
   rows=list(filtered(data))
   self.assertEqual(len(rows),2 if unknown else 1,data)
   for row in rows:
    self.assertEqual((row.role,row.level,row.workplace,row.evidence['sponsorship']['state']),(role,level,place,sponsor))
  self.assertEqual(filtered({'role':'qa'}).count(),0)
