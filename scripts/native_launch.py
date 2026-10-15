"""Resolve an actual packaged launcher without falling back to the source tree.

Editor runs preserve their existing command and working directory. Package runs
use the launch script inside the selected package, from an isolated run folder
or the package root. App-specific launcher overrides are removed from the child
environment so they cannot silently redirect an explicit package test.
"""
from dataclasses import dataclass
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time


@dataclass(frozen=True)
class NativeLaunch:
    argv: list[str]
    cwd: Path
    env: dict[str, str] | None
    package_root: Path | None


def create_native_run_directory(prefix: str, *, outside_project: bool = False) -> Path:
    """Keep evidence across reboots; mkdtemp still makes each run private/unique."""
    # File-access isolation tests audit the whole source tree. Their own logs,
    # screenshots and control files must therefore live outside that tree too.
    root = (Path.home() / '.local/state/oldwest-tests/runs' if outside_project else
            Path(__file__).resolve().parents[1] / 'game/tests/runs')
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=prefix, dir=root))


def resolve_native_launch(editor: Path, project: Path, package_directory: Path | None = None,
                          *, run_directory: Path | None = None, editor_directory: Path | None = None) -> NativeLaunch:
    if package_directory is None:
        return NativeLaunch([str(editor), str(project)], editor_directory or project.parent, None, None)

    requested = package_directory.expanduser().resolve(strict=True)
    candidates = (requested, requested/'Linux', requested/'LinuxNoEditor')
    root = next((candidate for candidate in candidates if (candidate/project.stem/'Binaries/Linux').is_dir()), None)
    if root is None:
        raise FileNotFoundError(f'No packaged {project.stem}/Binaries/Linux directory under {requested}')
    root = root.resolve(strict=True)
    launcher = root/'launch_battle_of_the_old_west.sh'
    if not launcher.is_file():
        raise FileNotFoundError(f'Bundled package launcher is missing: {launcher}; source-tree fallback is disabled')
    if not launcher.resolve().is_relative_to(root):
        raise ValueError(f'Bundled launcher resolves outside its package: {launcher}')
    if not os.access(launcher, os.X_OK):
        raise PermissionError(f'Bundled package launcher is not executable: {launcher}')
    cwd = run_directory.expanduser().resolve(strict=True) if run_directory else root
    if not cwd.is_dir():
        raise NotADirectoryError(f'Native run directory is not a directory: {cwd}')
    environment = os.environ.copy()
    for key in ('OLDWEST_BINARY', 'OLDWEST_PACKAGE_DIR', 'OLDWEST_PACKAGE_ROOT',
                'OLDWEST_PROJECT_NAME', 'OLDWEST_TARGET_NAME'):
        environment.pop(key, None)
    return NativeLaunch([str(launcher), '--package-dir', str(root), '--'], cwd, environment, root)


def game_net_driver_ports(log_text: str) -> list[int]:
    """Ignore Trace/control listeners; require the actual named game driver."""
    return [int(value) for value in re.findall(
        r'\bLogNet:[^\r\n]*\bName:GameNetDriver\b[^\r\n]*\blistening on port\s+(\d+)\b',
        log_text, flags=re.IGNORECASE)]


def _live_owned_groups(group_ids: set[int]) -> set[int]:
    """Find living members; an orphan zombie cannot run or respond to signals."""
    existing = set()
    for group in group_ids:
        try:
            os.killpg(group, 0)
            existing.add(group)
        except ProcessLookupError:
            pass
    if not existing or not Path('/proc/self/stat').is_file():
        return existing
    live, uncertain = set(), False
    # Linux may leave an orphan zombie until its new parent reaps it. Counting
    # that as a live game would falsely fail cleanup after a tracer crash.
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            fields = (entry/'stat').read_text().rsplit(')', 1)[1].split()
            group = int(fields[2])
            if group in existing and fields[0] not in ('Z', 'X'):
                live.add(group)
        except (FileNotFoundError, ProcessLookupError):
            pass
        except (OSError, IndexError, ValueError):
            uncertain = True
    return existing if uncertain else live


def stop_owned_process_groups(processes, streams=(), *, grace_seconds: float = 15,
                              kill_wait_seconds: float = 5) -> None:
    """Stop only Popen children explicitly launched with start_new_session=True.

    The caller must retain those original Popen objects. Each child's PID is
    its owned session/process-group ID, including after a tracer leader exits.
    Descendants which deliberately create another session are outside this
    contract. All groups share one grace deadline and one escalation deadline;
    leader exit never substitutes for checking the remaining group members.
    Leaders are reaped and all passed streams are closed, including on error.
    """
    children = list({process.pid: process for process in processes}.values())
    errors, groups = [], set()

    def send(group, sig):
        try:
            os.killpg(group, sig)
        except ProcessLookupError:
            pass
        except OSError as error:
            errors.append(f'Cannot signal owned process group {group}: {error}')

    def wait_groups(active, seconds):
        deadline = time.monotonic() + max(0, seconds)
        while True:
            for child in children:
                child.poll()  # Reap an exited leader, independently of its group.
            active = _live_owned_groups(active)
            if not active or time.monotonic() >= deadline:
                return active
            time.sleep(min(.05, max(0, deadline-time.monotonic())))

    try:
        for child in children:
            group = child.pid
            try:
                if group <= 1 or group == os.getpgrp():
                    raise ValueError('refusing to signal the current or a system process group')
                try:
                    if os.getpgid(group) != group or os.getsid(group) != group:
                        raise ValueError('child was not launched with start_new_session=True')
                except ProcessLookupError:
                    # Its tracer may already have exited; descendants still
                    # belong to the explicitly owned original process group.
                    pass
                groups.add(group)
            except (OSError, ValueError) as error:
                errors.append(f'Unsafe cleanup request for child {group}: {error}')
        for group in groups:
            send(group, signal.SIGTERM)
        remaining = wait_groups(groups, grace_seconds)
        for group in remaining:
            send(group, signal.SIGKILL)
        remaining = wait_groups(remaining, kill_wait_seconds)
        if remaining:
            errors.append('Owned process groups still contain live members: ' + ', '.join(map(str, sorted(remaining))))
        for child in children:
            if child.pid in groups:
                try:
                    # /proc can show an exiting leader as a zombie before
                    # waitpid exposes it to Popen. Allow that final handoff.
                    child.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    errors.append(f'Owned child {child.pid} could not be reaped after escalation')
    finally:
        for stream in streams:
            try:
                stream.close()
            except Exception as error:
                errors.append(f'Cannot close native process log stream: {error}')
    if errors:
        raise RuntimeError('; '.join(errors))
