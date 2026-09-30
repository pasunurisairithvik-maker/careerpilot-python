from unittest.mock import patch
import subprocess
from django.test import SimpleTestCase
from ops.start import main

class StartupBoundTests(SimpleTestCase):
    def test_optional_cleanup_timeout_does_not_block_serving(self):
        calls = []
        def run(args, **kwargs):
            calls.append((args, kwargs))
            if "housekeeping" in args:
                self.assertEqual(kwargs.get("timeout"), 30)
                raise subprocess.TimeoutExpired(args, 30)
            return subprocess.CompletedProcess(args, 0)
        with patch("ops.start.os.chdir"), patch("ops.start.subprocess.run", side_effect=run), patch("ops.start.os.execvp", side_effect=RuntimeError("synthetic-exec-marker")) as execute, patch.dict("os.environ", {"DEBUG":"1", "PORT":"10000", "WEB_CONCURRENCY":"1", "WEB_THREADS":"4"}):
            with self.assertRaisesRegex(RuntimeError, "synthetic-exec-marker"):
                main()
            self.assertEqual(execute.call_args.args[0], "gunicorn")
        self.assertTrue(any("migrate" in args and kwargs.get("check") for args,kwargs in calls))
        self.assertFalse(any("sync_jobs" in args or "reclassify_jobs" in args for args,kwargs in calls))

