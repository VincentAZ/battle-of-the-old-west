"""Pure-Python preflight for approved Crew imports; never imports Unreal or writes Content."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'art/western/crew/playable-v001'
CONTENT = ROOT / 'game/OldWest/Content'
NATIVE = {'quanah-parker', 'lozen', 'sarah-winnemucca'}
FINGER_BONES = {side+'Hand'+finger+str(digit) for side in ('Left','Right')
                for finger in ('Thumb','Index','Middle','Ring','Pinky') for digit in (1,2,3)}
CLIPS = ('Unarmed/MM_Idle', 'Unarmed/Walk/MF_Unarmed_Walk_Fwd',
         'Rifle/HitReact/MM_HitReact_Front_Lgt_01', 'Unarmed/Attack/MM_Attack_01')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load_manifest():
    manifest = json.loads((BASE / 'manifest.json').read_text())
    approval_path = (ROOT / manifest['approval']).resolve()
    assert approval_path.is_relative_to(ROOT / 'art/western/crew'), 'Approval outside Crew source tree'
    approval = json.loads(approval_path.read_text())
    assert approval['rigging_authorized'] and approval['animation_and_game_integration_authorized']
    records = manifest['characters']
    assert len(records) == 46 and set(manifest['reuse_existing_playable']) == NATIVE
    assert records == approval['projects'], 'Manifest differs from approved appearance records'
    names, copies, hashes = set(), set(), set()
    for slug, record in records.items():
        assert re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug), slug
        assert re.fullmatch(r'[A-Z][A-Za-z0-9]*', record['asset_name']), record['asset_name']
        assert record['asset_name'] not in names, 'Duplicate destination'
        names.add(record['asset_name'])
        assert record['sha256'] not in hashes, 'Reused approved project'
        hashes.add(record['sha256'])
        assert len(record['copies']) == 1, 'Every appearance must own one physical copy'
        for copy in record['copies']:
            key = (copy['canonical_card_id'], copy['copy'])
            assert key not in copies, 'Reused physical copy'
            copies.add(key)
        source = (ROOT / record['path']).resolve()
        assert source.is_relative_to(ROOT / 'art/western'), 'Source escapes approved art tree'
        assert sha(source) == record['sha256'], f'Approved source changed: {slug}'
    assert len(copies) == 46
    return manifest


def character(slug, manifest=None, require_exports=True):
    manifest = manifest or load_manifest()
    assert slug in manifest['characters'] and slug not in NATIVE, 'Existing Native assets are immutable'
    record = manifest['characters'][slug]
    name = record['asset_name']
    out = BASE / slug
    result = dict(slug=slug, name=name, out=out, source=ROOT / record['path'],
                  source_sha256=record['sha256'], dest='/Game/Art/Western/Crew/' + name)
    if not require_exports:
        return result
    validation = json.loads((out / 'rig-validation.json').read_text())
    assert validation.get('status') == 'passed', f'Rig validation has not passed: {slug}'
    assert validation.get('source_project_sha256', validation.get('source_sha256')) == record['sha256'], 'Rig uses unapproved source'
    assert sha(out / (name + '-Rigged.blend')) == validation['project_sha256'], 'Rigged project changed'
    expected = {'SK_' + name + '.fbx'} | {'T_' + name + '_' + c + '.png' for c in ('BaseColor', 'ORM', 'Normal')}
    assert expected <= set(validation['files']), 'Missing FBX or atlas checksum'
    for filename, digest in validation['files'].items():
        assert Path(filename).name == filename, 'Export path must be a basename'
        assert sha(out / 'exports' / filename) == digest, f'Export checksum mismatch: {filename}'
    assert validation.get('bind_pose_max_error_m', float('inf')) < 1e-5, 'Bind pose changes approved geometry'
    assert validation.get('maximum_vertex_influences', 999) <= 4, 'Unsupported vertex influence count'
    assert validation.get('source_geometry_uv_sha256'), 'Missing approved geometry/UV evidence'
    assert FINGER_BONES <= set(validation.get('freeze_bones', [])), 'Missing approved bind-finger policy'
    result['validation'] = validation
    return result


def snapshot(exclude=()):
    exclude = [Path(path).resolve() for path in exclude]
    return {str(path.relative_to(CONTENT)): sha(path) for path in sorted(CONTENT.rglob('*'))
            if path.is_file() and not any(path.resolve().is_relative_to(root) for root in exclude)}
