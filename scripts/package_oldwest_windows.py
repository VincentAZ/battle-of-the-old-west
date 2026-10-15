#!/usr/bin/env python3
"""Prepare a matching Win64 Development package on a Windows build machine.

Default: read-only preflight. --snapshot-output captures platform-neutral inputs
on either OS. --build invokes UE's Windows tools and never launches the game.
A successful package is NOT a verified Windows client or cross-platform match.
"""
import argparse
import hashlib
import json
import locale
import os
import platform
import shutil
import struct
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'game/OldWest/OldWest.uproject'
VERSION_KEYS = ('MajorVersion', 'MinorVersion', 'PatchVersion', 'Changelist', 'CompatibleChangelist', 'IsLicenseeVersion')
SUPPORT = {name: ROOT/'game'/name for name in ('PLAYER_GUIDE.md', 'REMOTE_PLAY.md', 'THIRD_PARTY_NOTICES.md')}


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            result.update(block)
    return result.hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def snapshot(engine):
    version = json.loads((engine/'Engine/Build/Build.version').read_text(encoding='utf-8-sig'))
    files = [PROJECT]
    for name in ('Source', 'Config', 'Content'):
        files.extend(p for p in (PROJECT.parent/name).rglob('*') if p.is_file())
    records = [{'path': p.relative_to(PROJECT.parent).as_posix(), 'bytes': p.stat().st_size, 'sha256': digest(p)}
               for p in sorted(files, key=lambda x: x.relative_to(PROJECT.parent).as_posix())]
    payload = {'engine': {key: version[key] for key in VERSION_KEYS}, 'files': records}
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
    return {'schema_version': 1, 'input_fingerprint': hashlib.sha256(encoded).hexdigest(), **payload}


def preflight(args):
    errors, warnings = [], []
    if platform.system() != 'Windows' or platform.machine().lower() not in ('amd64', 'x86_64'):
        errors.append('Win64 packaging requires a Windows x64 build machine with the Windows UE installation.')
    if platform.system() == 'Windows' and locale.getpreferredencoding(False).lower().replace('-', '') != 'utf8':
        errors.append('Run Python with -X utf8 so the shared asset inventory reads UTF-8 C++ source consistently.')
    engine = args.engine/'Engine'
    for rel in ('Build/BatchFiles/Build.bat', 'Build/BatchFiles/RunUAT.bat', 'Binaries/Win64/UnrealEditor-Cmd.exe',
                'Binaries/Win64/UnrealPak.exe', 'Binaries/Win64/UnrealGame.target'):
        if not (engine/rel).is_file(): errors.append('Missing Windows Unreal tool: '+str(engine/rel))
    inputs, scientist = None, None
    try:
        inputs = snapshot(args.engine)
        if tuple(inputs['engine'][k] for k in VERSION_KEYS[:3]) != (5, 8, 2):
            errors.append('Use Unreal 5.8.2 to match this project and the Linux host; do not silently upgrade it.')
        catalog = json.loads((PROJECT.parent/'Content/Data/cards.json').read_text(encoding='utf-8'))
        if len(catalog['cards']) != 104 or not {'base_2024','boomtown'} <= catalog['rulesets'].keys():
            errors.append('The runtime catalog must contain all 104 definitions and both rulesets.')
        if digest(PROJECT.parent/'Content/Data/cards.json') != digest(ROOT/'game/data/cards.json'):
            errors.append('Runtime and authoritative card catalogs differ.')
        config = (PROJECT.parent/'Config/DefaultGame.ini').read_text(encoding='utf-8')
        from package_oldwest import (source_inventory, scientist_data_inventory,
                                      ufs_dependency_errors, SCIENTIST_DATA, COOK_ROOTS)
        errors.extend(ufs_dependency_errors(PROJECT, ['Content/Data/cards.json', SCIENTIST_DATA]))
        scientist = scientist_data_inventory(PROJECT)
        required, _ = source_inventory(PROJECT, scientist)
        for root in [*COOK_ROOTS, '/Engine/BasicShapes']:
            if f'+DirectoriesToAlwaysCook=(Path="{root}")' not in config:
                errors.append('Missing dynamic asset cook root: '+root)
        for package in required:
            base = engine/'Content' if package.startswith('/Engine/') else PROJECT.parent/'Content'
            relative = package.removeprefix('/Engine/').removeprefix('/Game/')
            if not (base/(relative+('.umap' if package=='/Game/Maps/WaterDepotV2' else '.uasset'))).is_file():
                errors.append('Missing dynamically loaded asset: '+package)
    except (OSError, ValueError, KeyError) as error:
        errors.append(str(error)); required=[]
    if args.expected_inputs:
        expected = json.loads(args.expected_inputs.read_text(encoding='utf-8-sig'))
        if not inputs or expected.get('input_fingerprint') != inputs['input_fingerprint']:
            errors.append('Source/content/engine fingerprint differs from the paired Linux input snapshot.')
    elif args.build:
        errors.append('--build requires --expected-inputs from the exact source/content used for the Linux host.')
    for name, source in SUPPORT.items():
        if not source.is_file(): errors.append('Missing player support file: '+name)
    # Output must be a separate new directory. UAT may clean stage/archive trees.
    for protected in (ROOT, PROJECT.parent, args.engine):
        if args.output == protected or args.output in protected.parents or protected in args.output.parents and protected != ROOT:
            errors.append('Output may not contain or be inside project/engine input: '+str(args.output))
    if args.output.exists(): errors.append('Choose a new output directory; existing build evidence will not be overwritten.')
    existing = args.output.parent
    while not existing.exists(): existing=existing.parent
    if shutil.disk_usage(existing).free < args.minimum_free_gib*1024**3:
        errors.append(f'Less than the selected {args.minimum_free_gib}GiB free-space floor.')
    warnings.extend(['Windows SDK/compiler validity is checked by UE Turnkey when --build is requested.',
                     'Windows build, native startup, ACL/DPAPI tests and a real Windows-to-Linux match are still required.',
                     'The friend running the finished package does not need Unreal Editor, Visual Studio or Python.'])
    return {'ok': not errors, 'kind': 'windows_static_preflight', 'errors': errors, 'warnings': warnings,
            'inputs': inputs, 'required_packages': required, 'scientist_presentation': scientist,
            'runtime_validation_pending': True}


def run_batch(argv, log):
    # cmd.exe is required for Epic's .bat files. Reject shell metacharacters
    # rather than treating JSON quoting or a POSIX shell escape as Windows quoting.
    for arg in argv:
        if any(c in arg for c in '&|<>^%!\r\n"'):
            raise ValueError('Unsupported command/path character for the Windows batch build: '+arg)
    command = '"'+os.environ.get('COMSPEC', r'C:\Windows\System32\cmd.exe')+'" /d /s /c "'+subprocess.list2cmdline(argv)+'"'
    save(log.with_suffix('.command.json'), {'argv': argv, 'cwd': str(ROOT)})
    print('Running; full output: '+str(log), flush=True)
    with log.open('w', encoding='utf-8') as output:
        result = subprocess.run(command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, shell=False)
    if result.returncode:
        raise RuntimeError(f'Unreal tool failed with exit {result.returncode}; see {log}')


def validate_archive(archive, inputs):
    matches = list(archive.glob('**/OldWest/Binaries/Win64/OldWestGame.exe'))
    if len(matches) != 1: raise RuntimeError('Expected exactly one packaged OldWestGame.exe.')
    binary = matches[0]; root=binary.parents[3]
    with binary.open('rb') as f:
        if f.read(2) != b'MZ': raise RuntimeError('Packaged executable is not PE.')
        f.seek(0x3c); offset=struct.unpack('<I',f.read(4))[0];f.seek(offset)
        if f.read(4) != b'PE\0\0' or struct.unpack('<H',f.read(2))[0] != 0x8664:
            raise RuntimeError('Packaged executable is not Windows x64.')
    for ext in ('pak','utoc','ucas'):
        if not list((root/'OldWest/Content/Paks').glob('*.'+ext)):
            raise RuntimeError('Missing cooked '+ext+' container.')
    for name, source in SUPPORT.items():shutil.copy2(source,root/name)
    save(root/'oldwest-input-snapshot.json', inputs)
    # WinPlatform.Automation.cs uses TargetName for code-project bootstraps.
    bootstrap=root/'OldWestGame.exe'
    if not bootstrap.is_file(): raise RuntimeError('The generated Windows bootstrap OldWestGame.exe is missing.')
    launcher='@echo off\r\ncd /d "%~dp0"\r\n"%~dp0OldWestGame.exe" %*\r\n'
    (root/'launch_oldwest.bat').write_bytes(launcher.encode('ascii'))
    records=[{'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p)}
             for p in sorted(root.rglob('*')) if p.is_file()]
    manifest={'schema_version':1,'platform':'Win64','configuration':'Development','input_fingerprint':inputs['input_fingerprint'],
              'artifacts':records,'runtime_validation_pending':True,'release_ready':False,
              'checks':['x64 PE executable','Generated bootstrap and Pak/IoStore containers exist','Exact source/content snapshot unchanged during build'],
              'limitations':['No Windows runtime launch or cross-platform connection has been performed by this script.',
                             'Cooked package membership/catalog and Prospector JSON extraction still need independent artifact validation.']}
    save(root/'oldwest-windows-package-manifest.json',manifest)
    return str(root)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine',type=Path,required=True,help='Windows UE5.8.2 root; Linux root is accepted only for snapshot capture')
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--build',action='store_true')
    mode.add_argument('--snapshot-output',type=Path,help='Write exact transferable input identity; does not invoke UE')
    parser.add_argument('--expected-inputs',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'dist/windows-development')
    parser.add_argument('--minimum-free-gib',type=float,default=30)
    args=parser.parse_args();args.engine=args.engine.expanduser().resolve();args.output=args.output.expanduser().resolve()
    if args.snapshot_output:
        inputs=snapshot(args.engine);save(args.snapshot_output,inputs)
        print(json.dumps({'snapshot':str(args.snapshot_output),'input_fingerprint':inputs['input_fingerprint'],'file_count':len(inputs['files'])},indent=2));return 0
    plan=preflight(args)
    if not args.build:print(json.dumps(plan,indent=2));return 0 if plan['ok'] else 1
    if not plan['ok']:raise RuntimeError('\n'.join(plan['errors']))
    args.output.mkdir(parents=True)
    logs=args.output/'logs';logs.mkdir();save(logs/'preflight.json',plan)
    batch=args.engine/'Engine/Build/BatchFiles'
    run_batch([str(batch/'RunUAT.bat'),'Turnkey','-command=VerifySdk','-platform=Win64','-unattended'],logs/'sdk.log')
    run_batch([str(batch/'Build.bat'),'OldWestGameEditor','Win64','Development',f'-Project={PROJECT}','-NoUBA','-MaxParallelActions=2'],logs/'editor-build.log')
    run_batch([str(batch/'RunUAT.bat'),'BuildCookRun',f'-project={PROJECT}','-noP4','-target=OldWestGame','-platform=Win64',
               '-clientconfig=Development','-build','-skipbuildeditor','-cook','-map=/Game/Maps/WaterDepotV2','-stage','-pak','-iostore',
               '-prereqs','-UbtArgs=-NoUBA -MaxParallelActions=2','-archive',f'-stagingdirectory={args.output}/stage',
               f'-archivedirectory={args.output}/archive','-unattended','-utf8output'],logs/'build-cook-stage.log')
    after=snapshot(args.engine)
    if after['input_fingerprint'] != plan['inputs']['input_fingerprint']:
        raise RuntimeError('Build inputs changed during packaging; do not pair this artifact with the Linux host.')
    package=validate_archive(args.output/'archive',after)
    result={'ok':True,'package_root':package,'runtime_validation_pending':True,'created_utc':datetime.now(timezone.utc).isoformat()}
    save(logs/'result.json',result);print(json.dumps(result,indent=2));return 0


if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,ValueError,KeyError,RuntimeError) as error:
        print('Windows packaging unavailable/failed: '+str(error),file=sys.stderr);sys.exit(1)
