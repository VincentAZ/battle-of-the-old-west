"""Real child-process regressions for native harness cleanup; no Unreal needed."""
import io
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'scripts'))
from native_launch import stop_owned_process_groups


@unittest.skipUnless(sys.platform == 'linux', 'Linux native harness cleanup')
class OwnedGroupTests(unittest.TestCase):
    def emergency_stop(self, process):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)

    def test_already_exited_process_is_fast_and_closes_stream(self):
        child = subprocess.Popen([sys.executable, '-c', 'pass'], start_new_session=True)
        self.addCleanup(self.emergency_stop, child)
        child.wait(timeout=5)
        stream = io.StringIO()
        started = time.monotonic()
        stop_owned_process_groups([child], [stream], grace_seconds=10)
        self.assertLess(time.monotonic()-started, .5)
        self.assertTrue(stream.closed)
        self.assertEqual(child.returncode, 0)

    def test_live_session_terminates_and_is_reaped(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(60)'], start_new_session=True)
        self.addCleanup(self.emergency_stop, child)
        stop_owned_process_groups([child], grace_seconds=.2, kill_wait_seconds=2)
        self.assertIsNotNone(child.returncode)
        self.assertFalse(Path(f'/proc/{child.pid}').exists())

    def test_inherited_group_is_rejected_but_stream_closes(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(60)'])
        self.addCleanup(child.wait, 5)
        self.addCleanup(child.kill)
        stream = io.StringIO()
        with self.assertRaisesRegex(RuntimeError, 'start_new_session=True'):
            stop_owned_process_groups([child], [stream], grace_seconds=.1)
        self.assertIsNone(child.poll())
        self.assertTrue(stream.closed)

    @unittest.skipUnless(shutil.which('strace'), 'strace is needed for the tracer-crash reproduction')
    def test_tracer_crash_still_kills_sigterm_ignoring_game(self):
        with tempfile.TemporaryDirectory(prefix='oldwest-trace-cleanup-test-') as temporary:
            folder = Path(temporary)
            pidfile = folder/'child.pid'
            code = ('import os,signal,time,pathlib;'
                    'signal.signal(signal.SIGTERM,signal.SIG_IGN);'
                    f'pathlib.Path({str(pidfile)!r}).write_text(str(os.getpid()));time.sleep(60)')
            tracer = subprocess.Popen(['strace', '-f', '-yy', '-e', 'trace=openat,openat2',
                '-o', str(folder/'files.trace'), sys.executable, '-c', code], start_new_session=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.addCleanup(self.emergency_stop, tracer)
            deadline = time.monotonic()+5
            while not pidfile.exists() and time.monotonic() < deadline:
                self.assertIsNone(tracer.poll(), 'Tracer exited before the child started; check ptrace permission')
                time.sleep(.02)
            child_pid = int(pidfile.read_text())
            tracer.kill()
            tracer.wait(timeout=5)
            self.assertEqual(tracer.returncode, -signal.SIGKILL)
            self.assertEqual(os.getpgid(child_pid), tracer.pid)
            stream = io.StringIO()
            started = time.monotonic()
            stop_owned_process_groups([tracer], [stream], grace_seconds=.15, kill_wait_seconds=2)
            self.assertLess(time.monotonic()-started, 2.5)
            self.assertTrue(stream.closed)
            try:
                state = Path(f'/proc/{child_pid}/stat').read_text().rsplit(')', 1)[1].split()[0]
            except FileNotFoundError:
                state = None
            self.assertIn(state, (None, 'Z', 'X'), 'The traced game still has a live process')


if __name__ == '__main__':
    unittest.main()
