from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from .employment import terms
from .models import Job
from .discovery import evidence
from .job_views import filtered

class EmploymentTermsTests(SimpleTestCase):
    def test_tax_documents_are_not_engagement_terms(self):
        for text in ['Prepare W-2 forms and 1099 statements.', 'Reconcile Form W2 and Form 1099.']:
            self.assertFalse(terms('Payroll Analyst',text)['keys'] & {'w2','1099'})
        self.assertIn('w2',terms('Analyst','This is a W-2 contract role.')['keys'])
        self.assertIn('1099',terms('Analyst','This is a 1099 independent contractor role.')['keys'])

    def test_overlapping_dimensions_and_explicit_negation(self):
        keys=terms('Developer', 'Full-time contract position. W-2 only. No C2C. 1099 not accepted.')['keys']
        self.assertEqual(keys, {'full_time','contract','w2'})
        self.assertEqual(terms('Analyst', 'Review contracts and tax reports.')['keys'],set())
        self.assertEqual(terms('Intern', 'Part-time internship. Independent contractor.')['keys'],{'internship','part_time','1099'})
        self.assertIn('c2c',terms('Developer','Corp-to-corp contract role.')['keys'])
        self.assertNotIn('internship',terms('New Graduate Engineer','Previous internship experience is preferred.')['keys'])
        self.assertNotIn('1099',terms('Developer','Form 1098 is required.')['keys'])

class EmploymentFilterTests(TestCase):
    def setUp(self):
        for i,desc in enumerate(['Full-time contract position. W-2 only. No C2C.', 'Part-time position. 1099 independent contractor.', 'Develop Python applications.']):
            Job.objects.create(source_key=f'synthetic:employment:{i}',provider='greenhouse',board='synthetic',company='Synthetic',title='Junior Developer',role='developer',level='entry',description=desc,evidence=evidence(desc),url=f'https://example.org/employment/{i}',checked=timezone.now())
    def test_mix_filters_unknown_and_page_evidence(self):
        for data,count in [({'employment':'full_time','engagement':'w2'},1),({'employment':'full_time','engagement':'1099'},0),({'employment':'contract','role':'developer','level':'entry'},1),({'employment':'unknown'},1),({'engagement':'unknown'},1),({'engagement':'c2c'},0)]:
            self.assertEqual(filtered(data).count(),count,data)
        response=self.client.get('/jobs/?employment=full_time&engagement=w2')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['total'],1)
        self.assertContains(response,'Full-time')
        job=response.context['page'][0]
        self.assertContains(self.client.get(f'/jobs/{job.pk}/'),'W-2 only')
        self.assertEqual(self.client.get('/jobs/?engagement=1098').context['total'],0)
