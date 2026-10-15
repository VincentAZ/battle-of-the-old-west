#!/usr/bin/env python3
"""Capture selected survivor LOD views in isolated, sequential Unreal Editors.

Each view has its own settings and logs. Native asset hashes, fresh reports and
PNG hashes must agree. A capture can be useful even if Editor shutdown fails;
that failure is recorded separately and still makes this command exit nonzero.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from native_launch import create_native_run_directory, stop_owned_process_groups

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'art/characters/oldwest_survivor/lods'
EDITOR = Path.home() / 'Applications/UnrealEngine-5.8.2/Engine/Binaries/Linux/UnrealEditor'
SHOTS = ['rifle-idle', 'rifle-fire', 'hit', 'walk'] + [
    f'face-{expression}-lod{lod}' for expression in ('neutral', 'expression') for lod in range(4)
] + [f'auto-{distance}m' for distance in (6, 9, 15, 30, 45)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('shots', nargs='+', choices=SHOTS)
    parser.add_argument('--editor', type=Path, default=EDITOR)
    parser.add_argument('--timeout', type=float, default=180)
    parser.add_argument('--sdl-video-driver', choices=['dummy', 'x11', 'wayland'],
                        help='Use an isolated SDL driver override to investigate Editor shutdown; records the actual driver')
    args = parser.parse_args()
    folder = create_native_run_directory('oldwest-lod-review-')
    report = {'shots': [], 'logs': str(folder), 'visual_inspection_required': True,
              'requested_sdl_video_driver': args.sdl_video_driver}
    environment = os.environ.copy()
    if args.sdl_video_driver:
        environment['SDL_VIDEO_DRIVER'] = args.sdl_video_driver
        environment['SDL_VIDEODRIVER'] = args.sdl_video_driver

    def publish():
        report['captures_complete'] = len(report['shots']) == len(args.shots) and all(
            item['capture_verified'] for item in report['shots'])
        report['clean_editor_shutdown'] = all(item['exit_code'] == 0 for item in report['shots'])
        report['ok'] = report['captures_complete'] and report['clean_editor_shutdown']
        temporary = folder/'result.tmp'
        temporary.write_text(json.dumps(report, indent=2)+'\n')
        temporary.replace(folder/'result.json')

    print(f'Native survivor LOD review: {folder}', flush=True)
    for shot in args.shots:
        shot_dir = folder/shot
        shot_dir.mkdir()
        fresh_report = OUT/f'deformation-captures-{shot}.json'
        capture = OUT/f'{shot}-lod-comparison.png'
        for path in (fresh_report, capture):
            if path.exists():
                shutil.copy2(path, shot_dir/('previous-'+path.name))
        fresh_report.unlink(missing_ok=True)
        log = shot_dir/'editor.log'
        argv = [str(args.editor), str(ROOT/'game/OldWest/OldWest.uproject'),
                f'-ExecutePythonScript={ROOT}/scripts/preview_survivor_lods.py',
                f'-SurvivorLODPreviewShot={shot}', '-RenderOffscreen', '-windowed', '-ForceRes',
                '-ResX=2560', '-ResY=1440', '-nosound', '-unattended', '-nosplash', '-NoLiveCoding',
                '-stdout', '-FullStdOutLogOutput', f'-abslog={log}',
                f'-GameUserSettingsINI={shot_dir}/GameUserSettings.ini']
        (shot_dir/'command.json').write_text(json.dumps(argv, indent=2)+'\n')
        started = time.monotonic()
        entry = {'shot': shot, 'capture_verified': False, 'exit_code': None, 'logs': str(shot_dir)}
        process = None
        with (shot_dir/'console.log').open('w') as stream:
            try:
                print(f'Capturing {shot}', flush=True)
                process = subprocess.Popen(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                           env=environment, start_new_session=True)
                try:
                    entry['exit_code'] = process.wait(timeout=args.timeout)
                except subprocess.TimeoutExpired:
                    entry['failure'] = 'Editor exceeded its capture deadline'
                if fresh_report.exists():
                    data = json.loads(fresh_report.read_text())
                    assert all(sha(Path(path)) == value for path, value in data['protected_sha256'].items()), \
                        'Protected asset changed during preview'
                    assert len(data['captures']) == 1 and data['captures'][0]['shot']['name'] == shot
                    native = data['captures'][0]
                    assert Path(native['path']).resolve() == capture.resolve()
                    assert capture.is_file() and sha(capture) == native['sha256'], 'Capture hash mismatch'
                    png = capture.read_bytes()
                    assert png[:8] == b'\x89PNG\r\n\x1a\n' and png.endswith(b'IEND\xaeB`\x82')
                    assert int.from_bytes(png[16:20], 'big') == 2560 and int.from_bytes(png[20:24], 'big') == 1440
                    native_log = log.read_text(errors='replace')
                    assert 'SURVIVOR_LOD_PREVIEW_COMPLETE' in native_log
                    drivers = re.findall(r"Using SDL video driver '([^']+)'", native_log)
                    entry['actual_sdl_video_driver'] = drivers[-1] if drivers else None
                    if args.sdl_video_driver:
                        assert entry['actual_sdl_video_driver'] == args.sdl_video_driver, 'SDL diagnostic override did not take effect'
                    for path in (fresh_report, capture):
                        shutil.copy2(path, shot_dir/path.name)
                    entry['capture_verified'] = True
                    entry['capture'] = native
                else:
                    entry.setdefault('failure', 'No fresh completed capture report')
            except Exception as error:
                entry['failure'] = str(error)
            finally:
                if process is not None:
                    stop_owned_process_groups([process])
        entry['elapsed_seconds'] = round(time.monotonic()-started, 2)
        if entry['exit_code'] != 0 and entry['capture_verified']:
            entry['shutdown_failure'] = 'Capture and protected hashes verified, but Editor did not exit cleanly'
        report['shots'].append(entry)
        publish()
        print(f'{shot}: capture={entry["capture_verified"]}, exit={entry["exit_code"]}', flush=True)
        if not entry['capture_verified']:
            break
    publish()
    print(f'Report: {folder}/result.json', flush=True)
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
