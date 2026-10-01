from django.test import SimpleTestCase
from tracker.discovery import classify,normalize
from tracker.employment import terms

class JDIngestionTests(SimpleTestCase):
 def test_ambiguous_title_and_conflicting_description(self):
  self.assertEqual(classify('Associate','We need a data analyst to build reporting.'),'analyst')
  self.assertEqual(classify('Associate','Data analyst and software engineer opportunities.'),'other')
  self.assertEqual(classify('Senior Software Engineer','Partner with a data analyst.'),'developer')
  self.assertEqual(classify('Associate','Maintain COBOL mainframe applications.'),'mainframe')
 def test_public_ashby_fields_and_private_rejection(self):
  row={'id':'synthetic','title':'Associate','location':'Remote US','descriptionPlain':'We need a data analyst. 1 year of experience.','jobUrl':'https://example.org/jobs/synthetic','isListed':True,'employmentType':'FullTime','workplaceType':'Remote','compensation':{'compensationTierSummary':'USD 60,000–80,000'}}
  job=normalize('ashby','synthetic','Synthetic',row)
  self.assertEqual(job['provider'],'ashby');self.assertEqual(job['role'],'analyst');self.assertEqual(job['level'],'entry');self.assertEqual(job['workplace'],'remote')
  self.assertIn('full_time',terms(job['title'],job['description'])['keys'])
  self.assertEqual(job['evidence']['sponsorship']['state'],'unknown')
  self.assertTrue(job['salary'])
  row['isListed']=False
  with self.assertRaises(ValueError):normalize('ashby','synthetic','Synthetic',row)
