"""Run Crew generation through Mixar with cross-process session serialization.

Uses stampede_mixar_job.py's unchanged request and idempotency protocol.
Only one Crew service call runs at a time so rotating login refreshes cannot
race between independent background Mixar processes. Remote generation jobs
can still run concurrently. No credentials are read or written by this wrapper.
"""
import fcntl
from pathlib import Path
import runpy


if __name__ == '__main__':
    with Path('/tmp/oldwest-crew-mixar-service.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        runpy.run_path(str(Path(__file__).with_name('stampede_mixar_job.py')),
                       run_name='__main__')
