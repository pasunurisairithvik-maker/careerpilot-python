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

 def test_long_description_tail_is_analyzed_and_stored(self):
  description='Responsibilities. '+('General information. '*1200)+'\nRequirements: 6 years of experience. We do not offer visa sponsorship.'
  job=normalize('greenhouse','synthetic','Synthetic',{'id':'long','title':'Analyst','location':{'name':'US'},'content':description,'absolute_url':'https://example.org/long'})
  self.assertGreater(len(job['description']),20000)
  self.assertEqual(job['level'],'senior')
  self.assertEqual(job['evidence']['sponsorship']['state'],'no')
  with self.assertRaises(ValueError):normalize('greenhouse','synthetic','Synthetic',{'id':'huge','title':'Analyst','content':'x'*100001,'absolute_url':'https://example.org/huge'})
 def test_structured_lever_employment_and_clear_mobile_role(self):
  job=normalize('lever','synthetic','Synthetic',{'id':'1','text':'Senior Android Engineer','categories':{'location':'US','commitment':'Full-time'},'descriptionPlain':'Work with quality assurance and test automation.','hostedUrl':'https://example.org/mobile'})
  self.assertEqual(job['role'],'developer')
  self.assertIn('full_time',terms(job['title'],job['description'])['keys'])
 def test_more_description_role_families(self):
  self.assertEqual(classify('Associate','We need a financial analyst.'),'finance')
  self.assertEqual(classify('Associate','We need a UX designer.'),'design')
