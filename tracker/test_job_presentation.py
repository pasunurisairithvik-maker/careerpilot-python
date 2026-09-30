from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from tracker.job_presentation import experience_requirement, description_sections, authorization_rows
from tracker.job_views import filtered
from tracker.models import Job

class JobPresentationUnitTests(SimpleTestCase):
    def test_experience_patterns_and_nonexperience_dates(self):
        for text, expected in [
            ("6+ years of experience, ideally in finance.", 6),
            ("Minimum of 5 years of professional experience required.", 5),
            ("3–5 years relevant experience.", 3),
            ("1 to 2 years of work experience.", 1),
            ("2 years of experience. 6 years of experience preferred.", 6),
        ]:
            self.assertEqual(experience_requirement(text)["years"], expected)
        for text in ["Founded 20 years ago.", "Graduating in 2028.", "No experience required."]:
            self.assertIsNone(experience_requirement(text))

    def test_readable_sections_retain_text_without_trusted_html(self):
        sections = description_sections("Who we are:\nExample employer.\nThe role:\nFinance.\nWhat you'll need:\n6+ years of experience.\n<script>alert(1)</script>")
        self.assertTrue(any("6+ years" in p for s in sections for p in s["paragraphs"]))
        self.assertTrue(any(s["heading"] == "What you'll need" for s in sections))
        self.assertEqual(description_sections("Simple description")[0]["paragraphs"], ["Simple description"])

    def test_unknown_authorization_has_no_empty_rows(self):
        self.assertEqual(authorization_rows({"opt": {"state": "unknown", "evidence": []}}), [])
        self.assertEqual(authorization_rows({"stem_opt": {"state": "mentioned", "evidence": ["STEM OPT candidates"]}})[0]["label"], "STEM OPT")

class JobPresentationIntegrationTests(TestCase):
    def make_job(self, key, description, level="unspecified"):
        return Job.objects.create(source_key=key, provider="greenhouse", board="synthetic",
            company="Synthetic Finance", title="Data Analyst", location="United States",
            description=description, url="https://example.org/jobs/" + key, role="analyst",
            level=level, workplace="unspecified", checked=timezone.now(),
            evidence={"opt": {"state": "unknown", "evidence": []}})

    def test_description_experience_excluded_even_with_unstated_seniority(self):
        senior = self.make_job("senior", "What you'll need:\n6+ years of experience, ideally in financial services.")
        junior = self.make_job("junior", "Qualifications:\n1-2 years of experience.")
        from django.core.management import call_command
        call_command('reclassify_jobs',verbosity=0)
        self.assertEqual(list(filtered({"role": "analyst", "level": "entry", "include_unstated": True})), [junior])
        # A JD stating entry-level experience is not an unstated internship.
        self.assertEqual(list(filtered({"role": "analyst", "level": "intern", "include_unstated": True})), [])
        self.assertEqual(filtered({"role": "analyst"}).count(), 2)
        response = self.client.get(f"/jobs/{senior.pk}/")
        self.assertContains(response, "6+ years")
        self.assertContains(response, "Apply on company website")
        self.assertContains(response, "What you&#x27;ll need")
        self.assertNotContains(response, "OPT — Unknown")
        self.assertNotContains(response, "Phrase coverage: 0%")

    def test_entry_title_does_not_override_six_year_requirement(self):
        self.make_job("conflicting", "Minimum 6 years of relevant experience.", level="entry")
        self.assertEqual(filtered({"level": "entry"}).count(), 0)

    def test_employer_html_and_authorization_evidence_are_escaped(self):
        job = self.make_job("unsafe", "<script>alert(1)</script>\nWhat you'll need:\nSQL")
        job.evidence = {"opt": {"state": "mentioned", "evidence": ["<script>bad</script>"]}}
        job.save()
        response = self.client.get(f"/jobs/{job.pk}/")
        self.assertNotContains(response, "<script>")
        self.assertContains(response, "&lt;script&gt;")

