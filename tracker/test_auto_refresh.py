from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.utils import timezone
from .models import FeedState
from .discovery import classify, refresh
from .auto_refresh import maybe_refresh, _guard, _run

class ScheduledRefreshTests(TestCase):
    def test_specific_roles_precede_generic_engineer_and_analyst(self):
        for title, role in [('Security Analyst','security'),('Cloud Engineer','cloud'),('Finance Analyst','finance'),('HR Analyst','hr'),('COBOL Developer','mainframe'),('UX Designer','design'),('Customer Success Manager','sales')]:
            self.assertEqual(classify(title),role)

    @override_settings(AUTO_JOB_REFRESH=False)
    def test_tests_and_local_mode_do_not_contact_feeds(self):
        with patch('tracker.auto_refresh.threading.Thread') as thread:
            self.assertFalse(maybe_refresh())
            thread.assert_not_called()

    @override_settings(AUTO_JOB_REFRESH=True)
    def test_three_hour_due_and_single_background_thread(self):
        state=FeedState.objects.create(key='refresh',attempted=timezone.now()-timedelta(hours=2))
        from .discovery import SOURCES
        FeedState.objects.bulk_create([FeedState(key=f'{p}:{b}') for p,b,_ in SOURCES])
        with patch('tracker.auto_refresh.threading.Thread') as thread:
            self.assertFalse(maybe_refresh())
            thread.assert_not_called()
            state.attempted=timezone.now()-timedelta(hours=4);state.save()
            try:
                self.assertTrue(maybe_refresh())
                self.assertFalse(maybe_refresh())
                thread.assert_called_once()
                self.assertTrue(thread.call_args.kwargs['daemon'])
            finally:
                if _guard.locked():_guard.release()

    def test_refresh_failure_releases_guard(self):
        _guard.acquire()
        with patch('tracker.auto_refresh.refresh',side_effect=TimeoutError),patch('tracker.auto_refresh.close_old_connections'):
            with self.assertLogs('tracker.auto_refresh',level='ERROR'):
                _run()
        self.assertFalse(_guard.locked())

    def test_persistent_three_hour_cooldown(self):
        FeedState.objects.create(key='refresh',attempted=timezone.now()-timedelta(hours=2))
        FeedState.objects.create(key='greenhouse:synthetic')
        with patch('tracker.discovery.SOURCES',[('greenhouse','synthetic','Example')]),patch('tracker.discovery.download') as download:
            self.assertTrue(refresh(min_interval=180)['busy'])
            download.assert_not_called()

    @override_settings(AUTO_JOB_REFRESH=True)
    def test_optional_scheduler_failure_does_not_break_database_health(self):
        with patch('tracker.auto_refresh.maybe_refresh',side_effect=RuntimeError('synthetic')):
            with self.assertLogs('tracker.views',level='ERROR'):
                self.assertEqual(self.client.get('/healthz').status_code,200)

    def test_event_sponsorship_is_not_visa_sponsorship(self):
        from .discovery import evidence
        self.assertEqual(evidence('We provide event sponsorship for conferences.')['sponsorship']['state'],'unknown')
        self.assertEqual(evidence('We provide visa sponsorship.')['sponsorship']['state'],'yes')
        self.assertEqual(evidence('We do not offer visa sponsorship.')['sponsorship']['state'],'no')

