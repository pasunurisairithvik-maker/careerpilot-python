from django.test import SimpleTestCase
from .job_traits import level,workplace,salary
from .discovery import evidence
class DescriptionTraitsTests(SimpleTestCase):
 def test_description_experience(self):
  self.assertEqual(level('Data Analyst','3 years of experience'),'mid')
  self.assertEqual(level('Data Analyst','6 years of experience'),'senior')
  self.assertEqual(level('Data Analyst','1 year of experience'),'entry')
  self.assertEqual(level('Finance Manager',''), 'management')
 def test_workplace_and_restrictions(self):
  self.assertEqual(workplace('Chicago','This is a hybrid position, three days in our Chicago office.')[0],'hybrid')
  self.assertEqual(workplace('US','This is a fully remote role within the United States.')[0],'remote')
  self.assertEqual(workplace('Boston','This is an onsite position.')[0],'onsite')
  self.assertEqual(workplace('Boston','Remote work is not available.')[0],'unspecified')
 def test_salary_requires_pay_context(self):
  self.assertIn('$80,000',salary('Annual base salary: $80,000 to $100,000 USD.'))
  self.assertEqual(salary('Equipment budget of $1000.'),'')
 def test_no_sponsorship_and_silence(self):
  for text in ['No sponsorship provided.','Visa sponsorship is not provided.','Sponsorship will not be offered.']:
   self.assertEqual(evidence(text)['sponsorship']['state'],'no',text)
  self.assertEqual(evidence('Build Python applications.')['sponsorship']['state'],'unknown')
