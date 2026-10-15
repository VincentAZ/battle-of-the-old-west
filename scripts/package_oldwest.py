#!/usr/bin/env python3
"""Preflight, build, or validate a Development Linux Battle of the Old West package.

The default is a read-only preflight. --build explicitly runs Unreal's normal
BuildCookRun pipeline. Successful staging is followed by inspection of the ELF,
Pak/IoStore contents, cooked dynamic assets, and the actual packaged card data.
This does not certify graphics, gameplay, or Internet connectivity.
"""
import argparse
import csv
import hashlib
import json
import math
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENGINE = Path.home() / 'Applications/UnrealEngine-5.8.2'
COOK_ROOTS = ['/Game/Characters/Mannequins', '/Game/Weapons', '/Game/Art/WaterDepotV2',
              '/Game/Art/Survivors', '/Game/Art/Camps', '/Game/Art/CardPortraits', '/Game/Art/ActionProps',
              '/Game/Art/Effects', '/Game/Art/Vehicles', '/Game/Art/Western/StampedeStudy', '/Game/Art/Western/Drifter', '/Game/Art/Western/Quanah', '/Game/Art/Western/Lozen', '/Game/Art/Western/Sarah', '/Game/Art/Western/Crew', '/Game/Art/Western/Holdings', '/Game/Art/Western/Trouble', '/Game/Art/Western/Regions', '/Game/Audio']
ENGINE_PRIMITIVES = tuple('/Engine/BasicShapes/' + name for name in ('Cube', 'Sphere', 'Cylinder', 'Cone', 'Plane'))
COOK_ROOTS += ['/Game/Art/Western/ExpansionHoldings', '/Game/Art/Western/Bandages', '/Game/Art/Western/Reveal']
MAP = '/Game/Maps/WaterDepotV2'
TARGET = 'OldWestGame'
EDITOR_TARGET = 'OldWestGameEditor'
AUTOMATION_ENV = Path('/usr/bin/env')
SCIENTIST_DATA = 'Content/Data/scientist-presentation.json'
SCIENTIST_SCHEMA = 'oldwest.scientist.presentation.v1'
SCIENTIST_TRACKS = {'Full', 'Holster', 'Unholster', 'WorkHold', 'SortLeft', 'SortRight', 'SkipRecover'}
SHELTER_PACKAGES = tuple('/Game/Art/Camps/ShelterStudy/Meshes/SM_Shelter_' + name for name in (
    'ConcreteBase', 'Column_N_N', 'Column_N_P', 'Column_P_N', 'Column_P_P',
    'BackCladding', 'LeftCladding', 'RightCladding', 'RoofAssembly',
    'SideRoofRail_N', 'SideRoofRail_P'))
LAUNCHER = 'launch_battle_of_the_old_west.sh'
MANIFEST = 'package-manifest.json'
# Player-facing files only. Development notes, the research follow-up and the
# source-rules reference stay in the repository; they are not shipped.
BUNDLED_FILES = {'PLAYER_GUIDE.md': ROOT/'game/PLAYER_GUIDE.md',
                 'PLAYTEST.md': ROOT/'game/PLAYTEST.md',
                 'playtests/TEMPLATE.md': ROOT/'game/playtests/TEMPLATE.md',
                 'REMOTE_PLAY.md': ROOT/'game/REMOTE_PLAY.md',
                 'THIRD_PARTY_NOTICES.md': ROOT/'game/THIRD_PARTY_NOTICES.md',
                 LAUNCHER: ROOT/'scripts'/LAUNCHER}


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def scientist_data_schema(data):
    """Validate the runtime contract and return every JSON-loaded package."""
    def require(condition, reason):
        if not condition:
            raise ValueError('Prospector presentation data: ' + reason)
    require(isinstance(data, dict), 'expected an object')
    require(data.get('schema') == SCIENTIST_SCHEMA, 'unsupported schema')
    require(data.get('fps') == 30 and data.get('native_bones') == 54 and data.get('authoring_bones') == 53,
            'expected 30fps and the shared 53/54-bone rig')
    require(isinstance(data.get('complete_contract_sha256'), str) and
            re.fullmatch(r'[0-9a-f]{64}', data['complete_contract_sha256']) is not None, 'invalid art contract SHA-256')
    props, tracks = data.get('props'), data.get('tracks')
    require(isinstance(props, list) and len(props) == 11, 'expected eleven props')
    require(isinstance(tracks, dict) and set(tracks) == SCIENTIST_TRACKS, 'required seven tracks differ')
    names, packages, sample_indices = set(), set(), []
    for prop in props:
        require(isinstance(prop, dict), 'invalid prop record')
        name, asset, index = prop.get('name'), prop.get('asset'), prop.get('sample_index')
        require(isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9_]+', name) is not None and name not in names,
                'missing, invalid, or duplicate prop name')
        require(isinstance(asset, str) and re.fullmatch(
            r'/Game/Art/Survivors/ScientistAnalysis/Props/SM_[A-Za-z0-9_]+', asset) is not None,
            'noncanonical prop package path')
        require(asset not in packages, 'duplicate prop package path')
        require(type(index) is int and -1 <= index <= 2, 'invalid sample ordinal')
        names.add(name); packages.add(asset)
        if index >= 0: sample_indices.append(index)
    require(sorted(sample_indices) == [0, 1, 2], 'each of the three sample ordinals must appear once')
    frame_counts = {}
    for name, track in tracks.items():
        require(isinstance(track, dict), 'invalid track record')
        expected = f'/Game/Art/Survivors/ScientistAnalysis/Animations/A_Scientist_{name}_Cm'
        require(track.get('asset') == expected, 'noncanonical track package path for ' + name)
        seconds, frames = track.get('seconds'), track.get('frames')
        require(type(seconds) in (int, float) and math.isfinite(seconds) and seconds > 0, 'invalid track duration')
        require(isinstance(frames, list) and len(frames) == round(seconds * 30) + 1, 'track frame count mismatch')
        for index, frame in enumerate(frames):
            require(isinstance(frame, dict) and type(frame.get('time')) in (int, float) and
                    math.isfinite(frame['time']) and abs(frame['time'] - index / 30) <= .00001,
                    'track frame clock mismatch')
        packages.add(expected); frame_counts[name] = len(frames)
    rifle = '/Game/Weapons/Rifle/Meshes/SM_Rifle'
    require(data.get('rifle_asset') == rifle, 'unexpected declared rifle package')
    packages.add(rifle)
    return {'schema': SCIENTIST_SCHEMA, 'prop_count': len(props), 'track_count': len(tracks),
            'frame_counts': frame_counts, 'frame_count': sum(frame_counts.values()),
            'complete_contract_sha256': data['complete_contract_sha256'], 'required_packages': sorted(packages)}


def scientist_data_inventory(project):
    path = project.parent / SCIENTIST_DATA
    try:
        raw = path.read_bytes()
        metadata = scientist_data_schema(json.loads(raw))
    except (OSError, ValueError) as error:
        raise ValueError(f'Cannot validate {path}: {error}') from error
    return {'relative_path': SCIENTIST_DATA, 'sha256': hashlib.sha256(raw).hexdigest(), **metadata}


def ufs_dependency_errors(project, relative_paths):
    module = project.parent/'Source/OldWestGame/OldWestGame.Build.cs'
    text = module.read_text(encoding='utf-8') if module.exists() else ''
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    errors = []
    for relative in relative_paths:
        declaration = r'RuntimeDependencies\s*\.\s*Add\s*\(\s*"' + re.escape('$(ProjectDir)/' + relative) + \
                      r'"\s*,\s*StagedFileType\s*\.\s*UFS\s*\)'
        if not re.search(declaration, text):
            errors.append(f'{relative} needs its explicit UFS RuntimeDependency in OldWestGame.Build.cs.')
    return errors


def source_inventory(project, scientist=None):
    content = project.parent/'Content'
    required = {MAP, *ENGINE_PRIMITIVES}
    # Shelter names are assembled at runtime. Retain their exact inventory
    # even when a source mesh is missing, so neither platform silently cooks
    # an incomplete shelter just because its directory glob became smaller.
    required.update(SHELTER_PACKAGES)
    required.update('/Game/Art/Western/Drifter/' + name for name in (
        'SK_Drifter', 'SK_Drifter_Skeleton', 'M_Drifter', 'PA_Drifter',
        'Textures/T_Drifter_BaseColor', 'Textures/T_Drifter_Normal', 'Textures/T_Drifter_ORM',
        'Animations/RA_MM_Idle', 'Animations/RA_MF_Unarmed_Walk_Fwd',
        'Animations/RA_MM_HitReact_Front_Lgt_01', 'Animations/RA_MM_Attack_01'))
    required.update('/Game/Art/Western/Quanah/' + name for name in (
        'SK_Quanah', 'SK_Quanah_Skeleton', 'M_Quanah', 'PA_Quanah',
        'Textures/T_Quanah_BaseColor', 'Textures/T_Quanah_Normal', 'Textures/T_Quanah_ORM',
        'Animations/RA_MM_Idle', 'Animations/RA_MF_Unarmed_Walk_Fwd',
        'Animations/RA_MM_HitReact_Front_Lgt_01', 'Animations/RA_MM_Attack_01'))
    for character in ('Lozen', 'Sarah'):
        required.update('/Game/Art/Western/' + character + '/' + name for name in (
            'SK_'+character, 'SK_'+character+'_Skeleton', 'M_'+character, 'PA_'+character,
            'Textures/T_'+character+'_BaseColor', 'Textures/T_'+character+'_Normal', 'Textures/T_'+character+'_ORM',
            'Animations/RA_MM_Idle', 'Animations/RA_MF_Unarmed_Walk_Fwd',
            'Animations/RA_MM_HitReact_Front_Lgt_01', 'Animations/RA_MM_Attack_01'))
    # Distinct physical Crew copies use runtime-assembled cosmetic paths.
    # Require every approved copy, even when an import is accidentally absent.
    crew_approval = ROOT/'art/western/crew/review-v003/appearance-approval.json'
    if crew_approval.is_file():
        crew = json.loads(crew_approval.read_text())['projects']
        assert len(crew) == 46
        for slug, record in crew.items():
            if slug in {'quanah-parker', 'lozen', 'sarah-winnemucca'}:
                continue
            character = record['asset_name']
            required.update('/Game/Art/Western/Crew/' + character + '/' + name for name in (
                'SK_'+character, 'SK_'+character+'_Skeleton', 'M_'+character, 'PA_'+character,
                'Textures/T_'+character+'_BaseColor', 'Textures/T_'+character+'_Normal', 'Textures/T_'+character+'_ORM',
                'Animations/RA_MM_Idle', 'Animations/RA_MF_Unarmed_Walk_Fwd',
                'Animations/RA_MM_HitReact_Front_Lgt_01', 'Animations/RA_MM_Attack_01'))
    # Base camp holdings are assembled from the camp id at runtime. Require each
    # imported mesh, material, condition variant and texture explicitly.
    holdings_import = ROOT/'art/western/holdings/game-v001/unreal-import.json'
    if holdings_import.is_file():
        imported = json.loads(holdings_import.read_text())
        assert imported['ok'] and len(imported['holdings']) == 34
        for record in imported['holdings'].values():
            folder, mesh = record['mesh'].split('.', 1)[0].rsplit('/', 1)
            name = mesh.removeprefix('SM_Holding_')
            required.update(folder + '/' + leaf for leaf in (
                'SM_Holding_' + name, 'M_Holding_' + name,
                'Conditions/M_Soot_M_Holding_' + name, 'Conditions/M_Ruin_M_Holding_' + name,
                'Textures/T_Holding_' + name + '_BaseColor', 'Textures/T_Holding_' + name + '_Normal',
                'Textures/T_Holding_' + name + '_ORM'))
    required.update('/Game/Art/Western/StampedeStudy/' + name for name in (
        'SK_Longhorn', 'SK_Longhorn_Skeleton', 'M_Longhorn',
        'Animations/A_Longhorn_Idle', 'Animations/A_Longhorn_Run',
        'Textures/T_Longhorn_BaseColor', 'Textures/T_Longhorn_Normal', 'Textures/T_Longhorn_ORM'))
    # Every visible identity must survive cooking even though its path is
    # assembled from the public card id. Do not infer completeness from globs.
    identities = [c['id'] for c in json.loads((ROOT/'game/data/cards.json').read_text())['cards']
                  if c['type']=='person' and c['id'] not in {'prospector','gatling_gunner','bounty_hunter','blacksmith'}] + ['punk']
    for identity in identities:
        name = ''.join(word.title() for word in identity.split('_'))
        required.add('/Game/Art/Survivors/Identities/SKM_'+name+'_Cm')
        required.add('/Game/Art/Survivors/Identities/Materials/M_'+name+'_Outfit')
        for channel in ('BaseColor','Roughness','Metallic','Normal'):
            required.add('/Game/Art/Survivors/Identities/Textures/T_'+name+'_Outfit_'+channel)

    scientist = scientist_data_inventory(project) if scientist is None else scientist
    required.update(scientist['required_packages'])
    # Material graph texture references do not appear in runtime C++ paths.
    # Keep these required even if a source atlas is accidentally removed.
    required.update('/Game/Art/Effects/EngineFireStudy/' + name for name in ('T_Fire_SubUV', 'T_Smoke_SubUV'))
    for source in (project.parent/'Source').rglob('*.cpp'):
        for value in re.findall(r'TEXT\("(/Game/[^"\n]+)"\)', source.read_text()):
            if '.' in value and '%' not in value:
                required.add(value.split('.', 1)[0])
    # Animation paths are also assembled from a directory plus a clip name.
    for path in (content/'Art/Survivors').rglob('Animations/*.uasset'):
        required.add('/Game/' + path.relative_to(content).with_suffix('').as_posix())
    # Sound paths are constructed at runtime, including numbered variants.
    # The source manifest retains required names even if an import is deleted.
    audio_manifest = ROOT/'art/audio/audio-manifest.json'
    if audio_manifest.is_file():
        for asset in json.loads(audio_manifest.read_text())['assets'].values():
            required.add(asset['unreal_path'])
    roots = {}
    for root in COOK_ROOTS:
        directory = content/root.removeprefix('/Game/')
        assets = list(directory.rglob('*.uasset'))
        roots[root] = {'directory': str(directory), 'asset_count': len(assets),
                       'source_bytes': sum(p.stat().st_size for p in assets)}
        if root.startswith('/Game/Art/Western/') or root in ('/Game/Art/Camps', '/Game/Art/CardPortraits', '/Game/Art/ActionProps', '/Game/Art/Effects', '/Game/Audio'):
            for path in assets:
                if root.startswith('/Game/Art/Western/') or root == '/Game/Art/Effects' or path.stem.startswith(('SM_', 'SW_', 'M_')):
                    required.add('/Game/' + path.relative_to(content).with_suffix('').as_posix())
    return sorted(required), roots


def preflight(args):
    errors, warnings = [], []
    engine = args.engine/'Engine'
    required_files = [args.project, engine/'Build/BatchFiles/RunUAT.sh',
        engine/'Build/BatchFiles/Linux/Build.sh',
        engine/'Binaries/DotNET/AutomationTool/AutomationTool.dll',
        engine/'Binaries/Linux/UnrealEditor-Cmd', engine/'Binaries/Linux/UnrealPak',
        engine/'Binaries/Linux/UnrealGame.target',
        args.project.parent/'Source/OldWestGame.Target.cs',
        args.project.parent/'Source/OldWestGameEditor.Target.cs']
    for path in required_files:
        if not path.is_file():
            errors.append(f'Missing required file: {path}')
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'AMD64'):
        errors.append('This pipeline requires a Linux x86_64 host.')
    if args.cook_core_limit < 1:
        errors.append('--cook-core-limit must be at least 1.')
    try:
        version = json.loads((engine/'Build/Build.version').read_text())
        sdk_config = json.loads((engine/'Config/Linux/Linux_SDK.json').read_text())
    except (OSError, json.JSONDecodeError) as error:
        version, sdk_config = {}, {}
        errors.append(str(error))
    sdk_version = sdk_config.get('MainVersion', '')
    sdk = Path(os.environ.get('LINUX_MULTIARCH_ROOT') or
               str(engine/'Extras/ThirdPartyNotUE/SDKs/HostLinux/Linux_x64'/sdk_version))
    compiler = sdk/'x86_64-unknown-linux-gnu/bin/clang++'
    if not compiler.is_file():
        compiler = sdk/'x86_64-unknown-linux-gnu/bin/clang'
    if not compiler.is_file():
        errors.append(f'Linux toolchain compiler is missing: {compiler}')
    if os.environ.get('UE_SDKS_ROOT'):
        warnings.append('UE_SDKS_ROOT is set; AutomationTool makes the final AutoSDK selection. The inherited value is preserved.')
    for utility in ('bash', 'readelf', 'ldd'):
        if not shutil.which(utility):
            errors.append(f'Required local utility is unavailable: {utility}')
    if not AUTOMATION_ENV.is_file() or not os.access(AUTOMATION_ENV, os.X_OK):
        errors.append(f'AutomationTool requires executable system env: {AUTOMATION_ENV}')
    scientist = None
    if args.project.exists():
        try:
            scientist = scientist_data_inventory(args.project)
            packages, roots = source_inventory(args.project, scientist)
        except (OSError, ValueError) as error:
            packages, roots = [], {}
            errors.append(str(error))
        config = (args.project.parent/'Config/DefaultGame.ini').read_text()
        configured = set(re.findall(r'^\+DirectoriesToAlwaysCook=\(Path="([^"]+)"\)', config, re.M))
        if '/Engine/BasicShapes' not in configured:
            errors.append('Missing always-cook root in DefaultGame.ini: /Engine/BasicShapes')
        for root, inventory in roots.items():
            if root not in configured:
                errors.append(f'Missing always-cook root in DefaultGame.ini: {root}')
            if not inventory['asset_count']:
                errors.append(f'No imported assets under required dynamic-load root: {root}')
        for package in packages:
            relative = package.removeprefix('/Game/').removeprefix('/Engine/')
            extension = '.umap' if package == MAP else '.uasset'
            content_root = engine/'Content' if package.startswith('/Engine/') else args.project.parent/'Content'
            if not (content_root/f'{relative}{extension}').is_file():
                errors.append(f'Referenced runtime package is absent: {package}')
        errors.extend(ufs_dependency_errors(args.project, ['Content/Data/cards.json', 'Content/Data/rules-help.json', SCIENTIST_DATA]))
    else:
        packages, roots = [], {}
    bundled_files = []
    for name, source in BUNDLED_FILES.items():
        if not source.is_file():
            errors.append(f'Missing bundled player file: {source}')
            continue
        bundled_files.append({'name': name, 'source': str(source), 'bytes': source.stat().st_size,
                              'sha256': digest(source)})
    catalog = args.project.parent/'Content/Data/cards.json'
    catalog_hash, card_count = None, None
    try:
        data = json.loads(catalog.read_text())
        catalog_hash, card_count = digest(catalog), len(data['cards'])
        for ruleset in ('base_2024', 'boomtown'):
            if ruleset not in data['rulesets']:
                errors.append(f'Runtime catalog is missing ruleset {ruleset}.')
        authoritative = ROOT/'game/data/cards.json'
        if authoritative.exists() and digest(authoritative) != catalog_hash:
            errors.append('Content/Data/cards.json differs from game/data/cards.json; rebuild/sync the runtime catalog.')
    except (OSError, ValueError, KeyError) as error:
        errors.append(f'Cannot validate runtime card data: {error}')
    help_hash = None
    try:
        help_path = args.project.parent/'Content/Data/rules-help.json'
        help_hash = digest(help_path)
        help_data = json.loads(help_path.read_text())
        for key in ('basis', 'sections', 'cards'):
            if key not in help_data:
                errors.append(f'Offline rules help is missing its {key!r} entry.')
        if any(not section.get('title') or not section.get('text') for section in help_data.get('sections', [])):
            errors.append('Offline rules help has a section without a title or text.')
        explained = {entry.get('id') for entry in help_data.get('cards', []) if entry.get('explanation')}
        if catalog.exists():
            missing = sorted(card['id'] for card in json.loads(catalog.read_text())['cards'] if card['id'] not in explained)
            if missing:
                errors.append(f'Offline rules help lacks explanations for: {", ".join(missing)}')
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        errors.append(f'Cannot validate offline rules help: {error}')
    existing = args.output
    while not existing.exists():
        existing = existing.parent
    free = shutil.disk_usage(existing).free
    if free < args.minimum_free_gib * 1024**3:
        errors.append(f'Less than the configured {args.minimum_free_gib} GiB free-space floor is available.')
    # UAT owns and refreshes stage/archive output. Never point it at a source root.
    for protected in (ROOT, args.project.parent, args.engine, Path('/')):
        if args.output == protected or args.output in protected.parents:
            errors.append(f'Package output must not contain a source/engine root: {args.output}')
    return {'ok': not errors, 'kind': 'preflight', 'errors': errors, 'warnings': warnings,
            'engine': str(args.engine), 'engine_version': version, 'project': str(args.project),
            'target': TARGET, 'platform': 'Linux', 'configuration': 'Development',
            'sdk_version': sdk_version, 'compiler': str(compiler),
            'available_gib': round(free/1024**3, 2), 'catalog_sha256': catalog_hash, 'rules_help_sha256': help_hash,
            'card_definitions': card_count, 'required_packages': packages, 'cook_roots': roots,
            'scientist_presentation': scientist,
            'bundled_files': bundled_files,
            'cook_core_limit': args.cook_core_limit,
            'automation_env': {'source': str(AUTOMATION_ENV),
                'per_build_launcher': '<build-log-directory>/tools/env',
                'path_policy': 'Prepend only the per-build tools directory; preserve the remaining caller PATH'},
            'limitations': ['Static preflight only; no build, cook, launch, or visual validation performed.']}


def build_command(args):
    command = [str(args.engine/'Engine/Build/BatchFiles/RunUAT.sh'), 'BuildCookRun',
        f'-project={args.project}', '-noP4', '-nocompileuat', f'-target={TARGET}', '-platform=Linux',
        '-clientconfig=Development', '-build', '-skipbuildeditor', '-cook', f'-map={MAP}', '-stage', '-pak', '-iostore',
        '-UbtArgs=-NoUBA -MaxParallelActions=2 -WaitMutex',
        f'-AdditionalCookerOptions=-corelimit={args.cook_core_limit}',
        '-archive', f'-stagingdirectory={args.output}/stage', f'-archivedirectory={args.output}/archive',
        '-unattended', '-utf8output']
    reserved = {a.split('=', 1)[0].lower() for a in command[2:]}
    for argument in args.uat_arg:
        if argument.split('=', 1)[0].lower() in reserved:
            raise ValueError(f'Extra UAT argument conflicts with a managed build parameter: {argument}')
    return command + args.uat_arg


def editor_build_command(args):
    # UAT's UbtArgs applies to cooked targets, not its Editor agenda. Build the
    # editor explicitly so both targets receive the stable workstation flags.
    return [str(args.engine/'Engine/Build/BatchFiles/Linux/Build.sh'), EDITOR_TARGET,
            'Linux', 'Development', f'-Project={args.project}', '-NoUBA', '-MaxParallelActions=2', '-WaitMutex']


def run_logged(command, path, cwd, env=None, timeout=None):
    """Record every command/output; interrupt only this invocation's process group."""
    path.parent.mkdir(parents=True, exist_ok=True)
    save_json(path.with_suffix('.command.json'), {'argv': command, 'cwd': str(cwd)})
    start, progress = time.monotonic(), time.monotonic()
    with path.open('w') as output:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=output,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while process.poll() is None:
                if timeout and time.monotonic()-start > timeout:
                    raise TimeoutError(f'Command exceeded {timeout}s: {path}')
                if time.monotonic()-progress >= 30:
                    print(f'Still running ({int(time.monotonic()-start)}s): {path.name}', flush=True)
                    progress = time.monotonic()
                time.sleep(0.2)
        except BaseException:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
            raise
    if process.returncode:
        tail = '\n'.join(path.read_text(errors='replace').splitlines()[-25:])
        raise RuntimeError(f'Command failed ({process.returncode}); {path}\n{tail}')
    return path.read_text(errors='replace')


def automation_environment(logs, inherited):
    """Avoid UAT selecting a non-executable user env file; never alter it."""
    directory = logs/'tools'
    directory.mkdir(parents=True, exist_ok=True)
    launcher = directory/'env'
    launcher.symlink_to(AUTOMATION_ENV)
    environment = inherited.copy()
    original_path = environment.get('PATH', os.defpath)
    environment['PATH'] = str(directory) + os.pathsep + original_path
    save_json(logs/'automation-environment.json', {'selected_env': str(launcher),
        'resolved_env': str(launcher.resolve(strict=True)),
        'prepended_path_directory': str(directory), 'remaining_path_preserved': True})
    return environment, launcher


def package_root(path, project_name):
    candidates = [path, path/'Linux', path/'LinuxNoEditor']
    for candidate in candidates:
        if (candidate/project_name/'Binaries/Linux').is_dir():
            return candidate
    raise ValueError(f'No staged Linux package with {project_name}/Binaries/Linux under {path}')


def bundle_support_files(root, plan):
    for item in plan['bundled_files']:
        source = Path(item['source'])
        if digest(source) != item['sha256']:
            raise ValueError(f'Bundled player file changed after preflight: {source}')
        destination = root/item['name']
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        if item['name'] == LAUNCHER:
            destination.chmod(0o755)


def extract_pak_json(pak_tool, pak, root, logs, index, label, filename, project_name):
    destination = logs/f'{label}-extract-{index}'
    destination.mkdir(parents=True, exist_ok=False)
    # UE5.8 PakFileUtilities.cpp reconstructs the input with a literal
    # backslash even on Linux. Both aliases point to the actual staged Pak;
    # never substitute loose source JSON or modify the container.
    with tempfile.TemporaryDirectory(prefix='pak-extract-', dir=logs) as scratch:
        scratch = Path(scratch)
        input_dir = scratch/'input'
        input_dir.mkdir()
        normal_alias = input_dir/pak.name
        normal_alias.symlink_to(pak.resolve())
        backslash_alias = scratch/('input\\' + pak.name)
        backslash_alias.symlink_to(pak.resolve())
        save_json(logs/f'{label}-{index}-input.json', {
            'container': str(pak), 'normal_alias': str(normal_alias),
            'linux_extractor_alias': str(backslash_alias), 'temporary_aliases_removed_after_extraction': True})
        run_logged([str(pak_tool), str(normal_alias), '-Extract', str(destination), f'-Filter=*{filename}', '-unattended'],
                   logs/f'{label}-{index}.log', root, timeout=120)
    # A same-named JSON in another directory cannot satisfy the runtime load.
    path = destination/project_name/'Content/Data'/filename
    return [path] if path.is_file() else []


def verify_extracted_scientist(plan, paths):
    if 'scientist_presentation' not in plan:
        return {'status': 'not_required_by_legacy_plan', 'verified': False,
                'reason': 'Recorded package plan predates the Prospector JSON validation contract.'}
    expected = plan['scientist_presentation']
    if not isinstance(expected, dict) or not isinstance(expected.get('sha256'), str) or \
            not re.fullmatch(r'[0-9a-f]{64}', expected['sha256']):
        raise ValueError('Recorded Prospector presentation plan has no valid source SHA-256.')
    if not paths:
        raise ValueError('Runtime scientist-presentation.json could not be extracted from its packaged Content/Data path.')
    for path in paths:
        if digest(path) != expected['sha256']:
            raise ValueError('Packaged Prospector presentation data differs from its build-start SHA-256.')
        actual = scientist_data_schema(json.loads(path.read_bytes()))
        if actual['required_packages'] != expected['required_packages'] or \
                not set(actual['required_packages']) <= set(plan['required_packages']):
            raise ValueError('Packaged Prospector asset declarations differ from the required package inventory.')
    return {'status': 'verified_from_pak', 'verified': True, 'sha256': expected['sha256'],
            'extracted_paths': [str(path) for path in paths], **actual}


def validate(args, directory, plan, logs):
    root = package_root(directory, args.project.stem)
    binary = root/args.project.stem/'Binaries/Linux'/TARGET
    if not binary.is_file():
        binary = binary.with_name(f'{TARGET}-Linux-Development')
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise ValueError(f'Packaged executable is missing or is not executable: {binary}')
    elf = run_logged(['readelf', '-h', str(binary)], logs/'elf.log', root, timeout=30)
    if 'ELF64' not in elf or 'X86-64' not in elf.upper():
        raise ValueError('The staged executable is not an x86_64 ELF64 binary.')
    linkage = run_logged(['ldd', str(binary)], logs/'ldd.log', root, timeout=30)
    if 'not found' in linkage:
        raise ValueError(f'Unresolved shared-library dependencies; inspect {logs}/ldd.log')
    pak_tool = args.engine/'Engine/Binaries/Linux/UnrealPak'
    paks = sorted(root.rglob('*.pak'))
    tocs = sorted(root.rglob('*.utoc'))
    if not paks or not tocs:
        raise ValueError('Expected both Pak files and IoStore .utoc containers from this packaging command.')
    names, extracted_catalogs, extracted_scientist, extracted_help = [], [], [], []
    for index, pak in enumerate(paks):
        text = run_logged([str(pak_tool), str(pak), '-List', '-unattended'], logs/f'pak-{index}.log', root, timeout=120)
        names.extend(re.findall(r'"([^"\n]+)"', text))
        if 'Data/cards.json'.lower() in text.lower():
            extracted_catalogs.extend(extract_pak_json(pak_tool, pak, root, logs, index,
                                      'catalog', 'cards.json', args.project.stem))
        if plan.get('rules_help_sha256') and 'data/rules-help.json' in text.replace('\\', '/').lower():
            extracted_help.extend(extract_pak_json(pak_tool,pak,root,logs,index,'rules-help','rules-help.json',args.project.stem))
        if 'scientist_presentation' in plan and 'data/scientist-presentation.json' in text.replace('\\', '/').lower():
            extracted_scientist.extend(extract_pak_json(pak_tool, pak, root, logs, index,
                                       'prospector', 'scientist-presentation.json', args.project.stem))
    for index, toc in enumerate(tocs):
        if not toc.with_suffix('.ucas').is_file():
            raise ValueError(f'IoStore TOC has no matching data container: {toc}')
        csv_path = logs/f'iostore-{index}.csv'
        run_logged([str(pak_tool), f'-ListContainer={toc}', f'-Csv={csv_path}', '-unattended'],
                   logs/f'iostore-{index}.log', root, timeout=120)
        with csv_path.open(encoding='utf-8-sig') as source:
            for row in csv.DictReader(source, skipinitialspace=True):
                names.extend(str(value).strip() for key, value in row.items()
                             if key and key.strip() in ('PackageName', 'Filename') and value)
    cooked_packages = set()
    for name in names:
        value = name.replace('\\', '/').strip().lower()
        if value.startswith(('/game/', '/engine/')) and '.' not in value:
            cooked_packages.add(value)
        elif '/engine/content/' in value and value.endswith(('.uasset', '.umap')):
            cooked_packages.add('/engine/' + value.split('/engine/content/', 1)[1].rsplit('.', 1)[0])
        elif '/content/' in value and value.endswith(('.uasset', '.umap')):
            cooked_packages.add('/game/' + value.split('/content/', 1)[1].rsplit('.', 1)[0])
    missing = []
    for package in plan['required_packages']:
        if package.lower() not in cooked_packages:
            missing.append(package)
    for cook_root in plan['cook_roots']:
        if not any(package.startswith(cook_root.lower() + '/') for package in cooked_packages):
            missing.append(cook_root + ' (entire dynamic-load directory)')
    if missing:
        raise ValueError('Required cooked packages are absent from the actual containers: ' + ', '.join(missing))
    if not extracted_catalogs:
        raise ValueError('The runtime cards.json could not be found and extracted from the packaged Pak files.')
    if any(digest(path) != plan['catalog_sha256'] for path in extracted_catalogs):
        raise ValueError('Packaged card data differs from the source catalog captured at build start.')
    catalog = json.loads(extracted_catalogs[0].read_text())
    if not {'base_2024', 'boomtown'} <= catalog['rulesets'].keys():
        raise ValueError('Packaged runtime data is missing a supported ruleset.')
    if plan.get('rules_help_sha256'):
        if not extracted_help or any(digest(path)!=plan['rules_help_sha256'] for path in extracted_help):
            raise ValueError('Pak-extracted rules help is missing or differs from its build-start hash.')
        help_cards=json.loads(extracted_help[0].read_text())['cards']
        if {card['id'] for card in help_cards}!={card['id'] for card in catalog['cards']}:
            raise ValueError('Packaged rules help does not cover the packaged card catalog.')
    scientist_validation = verify_extracted_scientist(plan, extracted_scientist)
    bundled_paths = []
    for item in plan['bundled_files']:
        path = root/item['name']
        if not path.is_file() or digest(path) != item['sha256']:
            raise ValueError(f'Bundled player file is missing or changed: {path}')
        if item['name'] == LAUNCHER and not os.access(path, os.X_OK):
            raise ValueError(f'Bundled launch script is not executable: {path}')
        bundled_paths.append(path)
    inventory = [{'path': str(path.relative_to(root)), 'bytes': path.stat().st_size,
                  'sha256': digest(path)} for path in [binary, *paks, *tocs, *sorted(root.rglob('*.ucas')), *bundled_paths]]
    result = {'ok': True, 'kind': 'staged_artifact_validation', 'root': str(root),
              'binary': str(binary), 'configuration': 'Development', 'artifacts': inventory,
              'catalog_sha256': plan['catalog_sha256'], 'card_definitions': len(catalog['cards']),
              'scientist_presentation': scientist_validation,
              'rules_help': {'verified_from_pak':bool(extracted_help),'sha256':plan.get('rules_help_sha256')},
              'verified_required_packages': plan['required_packages'], 'container_entry_count': len(names),
              'checks': ['Executable x86_64 ELF', 'Local shared-library linkage', 'Pak and IoStore inspection',
                         'Map and dynamic runtime assets cooked', 'Extracted runtime catalog matches source SHA-256',
                         'Player guide and executable launch script match source SHA-256'],
              'limitations': ['No executable launch performed by this validator', 'Graphics and gameplay unverified by packaging',
                              'Local ldd results do not establish compatibility with another Linux installation']}
    if scientist_validation['verified']:
        result['checks'].append('Pak-extracted Prospector presentation JSON matches build-start SHA-256 and declared asset inventory')
    else:
        result['limitations'].append('Legacy recorded plan does not require or verify Prospector presentation JSON')
    save_json(logs/'validation.json', result)
    save_json(root/MANIFEST, {'source': plan, 'validation': result})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--preflight', action='store_true', help='Inspect readiness without cooking/building (default)')
    mode.add_argument('--build', action='store_true', help='Build, cook, stage, archive, then validate')
    mode.add_argument('--validate', type=Path, metavar='DIRECTORY', help='Inspect an existing stage/archive')
    parser.add_argument('--engine', type=Path, default=Path(os.environ.get('OLDWEST_UNREAL_ROOT', os.environ.get('UE_ROOT', str(DEFAULT_ENGINE)))))
    parser.add_argument('--project', type=Path, default=Path(os.environ.get('OLDWEST_PROJECT', str(ROOT/'game/OldWest/OldWest.uproject'))))
    parser.add_argument('--output', type=Path, default=Path(os.environ.get('OLDWEST_PACKAGE_ROOT', str(ROOT/'dist/linux-development'))))
    parser.add_argument('--minimum-free-gib', type=float, default=20, help='Preflight free-space floor; not a size prediction')
    parser.add_argument('--cook-core-limit', type=int, default=3,
                        help='Per-cooker reported CPU cap; 3 selects two shader workers in the installed engine')
    parser.add_argument('--uat-arg', action='append', default=[], help='Additional non-conflicting UAT option; use --uat-arg=-name=value')
    args = parser.parse_args()
    args.engine, args.project, args.output = (p.expanduser().resolve() for p in (args.engine, args.project, args.output))
    plan = preflight(args)
    plan['editor_build_command'] = editor_build_command(args)
    plan['uat_command'] = build_command(args)
    if not args.build and not args.validate:
        print(json.dumps(plan, indent=2))
        return 0 if plan['ok'] else 1
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + f'-{os.getpid()}'
    logs = args.output/'logs'/stamp
    logs.mkdir(parents=True, exist_ok=True)
    save_json(logs/'preflight.json', plan)
    if args.validate:
        directory = args.validate.expanduser().resolve()
        root = package_root(directory, args.project.stem)
        manifest = root/MANIFEST
        if manifest.exists():
            plan = json.loads(manifest.read_text())['source']
        result = validate(args, directory, plan, logs)
        print(json.dumps(result, indent=2))
        return 0
    if not plan['ok']:
        raise RuntimeError('Packaging preflight failed:\n' + '\n'.join(plan['errors']))
    env, env_launcher = automation_environment(logs, os.environ)
    plan['automation_env']['selected_env'] = str(env_launcher)
    save_json(logs/'preflight.json', plan)
    env.setdefault('uebp_LogFolder', str(logs/'automation'))
    print(f'Editor build log: {logs}/editor-build.log', flush=True)
    run_logged(plan['editor_build_command'], logs/'editor-build.log', ROOT, env)
    print(f'Build/cook log: {logs}/build-cook-stage.log', flush=True)
    build_log = run_logged(plan['uat_command'], logs/'build-cook-stage.log', ROOT, env)
    workers = sorted(set(map(int, re.findall(r'Using (\d+) local workers for shader compilation', build_log))))
    worker_cap = max(1, args.cook_core_limit - 1) if args.cook_core_limit <= 4 else args.cook_core_limit
    save_json(logs/'shader-workers.json', {'cook_core_limit': args.cook_core_limit,
              'maximum_expected_workers': worker_cap, 'observed_worker_counts': workers,
              'observed': bool(workers)})
    if workers and max(workers) > worker_cap:
        raise RuntimeError(f'Cooker exceeded its shader worker cap: observed {workers}, expected at most {worker_cap}')
    results = []
    for name in ('stage', 'archive'):
        directory = args.output/name
        root = package_root(directory, args.project.stem)
        bundle_support_files(root, plan)
        result = validate(args, directory, plan, logs/name)
        results.append(result)
    save_json(logs/'result.json', {'ok': True, 'packages': results})
    print(json.dumps({'ok': True, 'log_directory': str(logs), 'stage': results[0]['root'],
                      'archive': results[1]['root'], 'runtime_launch_tested': False}, indent=2))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, TimeoutError, KeyError) as error:
        print(f'Packaging failed: {error}', file=sys.stderr)
        sys.exit(1)
