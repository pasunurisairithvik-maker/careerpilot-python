from unittest.mock import patch
from django.test import SimpleTestCase
from .smartrecruiters import download,normalize
class SmartRecruitersTests(SimpleTestCase):
 def test_public_detail_normalization(self):
  row={'id':'123','name':'Data Analyst Intern','visibility':'PUBLIC','postingUrl':'https://jobs.smartrecruiters.com/ServiceNow/123','location':{'fullLocation':'Chicago, US','remote':True},'jobAd':{'sections':{'qualifications':{'title':'Qualifications','text':'<p>1 year of experience. No visa sponsorship provided.</p>'}}}}
  data=normalize('ServiceNow','ServiceNow',row)
  self.assertEqual(data['provider'],'smartrecruiters');self.assertEqual(data['level'],'intern');self.assertEqual(data['workplace'],'remote');self.assertEqual(data['evidence']['sponsorship']['state'],'no')
 def test_incomplete_page_rejected(self):
  with patch('tracker.smartrecruiters.read',return_value={'totalFound':2,'content':[]}):
   with self.assertRaisesRegex(ValueError,'Incomplete'):download('ServiceNow')
 def test_detail_urls_reconstructed_and_private_rejected(self):
  with patch('tracker.smartrecruiters.read',side_effect=[{'totalFound':1,'content':[{'id':'123','ref':'https://example.com/evil'}]},{'visibility':'INTERNAL'}]) as get:
   with self.assertRaisesRegex(ValueError,'Non-public'):download('ServiceNow')
   self.assertEqual(get.call_args.args[0],'https://api.smartrecruiters.com/v1/companies/ServiceNow/postings/123')
