"""Focused asset/runtime checks shared by actual Unreal gameplay harnesses.

Report categories and counts rather than dumping engine logs, which may contain
private connection details. These checks supplement process and state checks.
"""
import re
from pathlib import Path


PATTERNS = {
    'material usage fallback': r'missing usage flag|Default Material will be used in game',
    'material shader compilation failure': r'Failed to compile Material|Shader compilation failures are Fatal',
    'invalid material instance parent': r'is not a valid parent for MaterialInstanceDynamic',
    'missing cinematic supply asset': r'OLDWEST_ACTION_PROP_ERROR',
    'missing fire presentation asset': r'OLDWEST_FIRE_VISUAL_ERROR',
    'missing game package': r"(?:Couldn.t find file for package|Failed to find object|Failed to load package|Unable to find package)[^\r\n]*/(?:Game/|Engine/BasicShapes/)",
    'fatal native runtime error': r'Critical error:|Assertion failed:|Unhandled Exception:|Signal (?:6|7|11) caught',
}


def assert_runtime_assets(log_paths):
    checked, failures = [], []
    for path in log_paths:
        if not path.is_file():
            failures.append(f'{path.name}: runtime log missing')
            continue
        contents = path.read_text(errors='replace')
        checked.append(str(path))
        for label, pattern in PATTERNS.items():
            count = len(re.findall(pattern, contents, flags=re.IGNORECASE))
            if count:
                failures.append(f'{path.name}: {label} ({count} matches)')
    if failures:
        raise AssertionError('Runtime asset validation failed: ' + '; '.join(failures))
    return {'ok': True, 'logs_checked': checked, 'categories': list(PATTERNS)}


def assert_packaged_file_access(trace_paths, package_root, forbidden_roots):
    """Inspect successful opens from this launch's strace -f -yy output.

    Returned file descriptors include resolved absolute paths, avoiding guesses
    about relative paths or a process's changing working directory. Failed opens
    do not establish a dependency. Trace only the launched game and its children.
    """
    package_root = Path(package_root).resolve()
    forbidden = [Path(root).resolve() for root in forbidden_roots]
    assert not any(package_root.is_relative_to(root) for root in forbidden), \
        'The isolation check requires a package outside the source and engine directories'
    rows, violations = [], set()
    for trace in trace_paths:
        assert trace.is_file(), f'Packaged file trace is missing: {trace.name}'
        opened = set()
        with trace.open(errors='replace') as source:
            for line in source:
                # Includes resumed openat calls in multithreaded traces. The
                # descriptor suffix is present only for successful file opens.
                if not re.search(r'(?:openat2?\(|<\.\.\. openat2? resumed>)', line):
                    continue
                match = re.search(r' = \d+<(/[^>]+)>\s*$', line.rstrip())
                if match:
                    opened.add(Path(match[1]).resolve())
        assert opened, f'No successful file opens were recorded: {trace.name}'
        packaged = sorted(path for path in opened if path.is_relative_to(package_root))
        extensions = {path.suffix for path in packaged}
        assert {'.pak', '.utoc', '.ucas'} <= extensions, \
            f'Trace does not show opening all three cooked container types: {trace.name}'
        violations.update(str(path) for path in opened if any(path.is_relative_to(root) for root in forbidden))
        rows.append({'trace': str(trace), 'distinct_successful_opens': len(opened),
                     'packaged_files_opened': len(packaged),
                     'containers': [str(path.relative_to(package_root)) for path in packaged
                                    if path.suffix in ('.pak', '.utoc', '.ucas')]})
    assert not violations, 'Packaged game opened source/engine files: ' + ', '.join(sorted(violations))
    return {'ok': True, 'package_root': str(package_root), 'traces': rows,
            'forbidden_roots': [str(path) for path in forbidden],
            'limitations': ['Evidence covers successful file opens in these launches only.',
                            'System libraries, drivers and user settings remain external dependencies.',
                            'This is not a test on a computer with Unreal uninstalled.']}
