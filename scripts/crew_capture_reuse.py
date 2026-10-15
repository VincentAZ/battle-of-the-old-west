"""Reuse pose evidence only when every non-attack asset is byte-identical."""
import copy
import json
from crew_unreal_contract import sha

BASELINE = 'attack-gesture-baseline-v001'


def unmodified_captures(out):
    baseline = out / BASELINE
    old_capture = baseline / 'unreal-pose-captures.json'
    old_assets = baseline / 'unreal-assets.json'
    capture = json.loads(old_capture.read_text())
    before = json.loads(old_assets.read_text())
    after = json.loads((out / 'unreal-assets.json').read_text())
    rig = json.loads((out / 'rig-validation.json').read_text())
    assert capture['ok'] and capture['component_pose_verified'] and capture['existing_content_unchanged']
    assert capture['unreal_assets_sha256'] == sha(old_assets)
    assert capture['rig_project_sha256'] == before['rig_project_sha256'] == after['rig_project_sha256'] == rig['project_sha256']
    assert capture['rig_validation_sha256'] == before['rig_validation_sha256'] == after['rig_validation_sha256'] == sha(out / 'rig-validation.json')
    assert before['approved_source_sha256'] == after['approved_source_sha256']
    assert set(before['files']) == set(after['files'])
    changed = [p for p in before['files'] if before['files'][p] != after['files'][p]]
    assert len(changed) == 1 and changed[0].endswith('/Animations/RA_MM_Attack_01.uasset'), 'Reuse requires an attack-only asset change'
    records = [copy.deepcopy(r) for r in capture['captures'] if r['clip'] != 'MM_Attack_01']
    assert len(capture['captures']) == 24 and len(records) == 20
    assert len({r['file'] for r in records}) == 20
    assert {c: sum(r['clip'] == c for r in records) for c in ('MF_Unarmed_Walk_Fwd', 'MM_Idle', 'MM_HitReact_Front_Lgt_01')} == {'MF_Unarmed_Walk_Fwd': 12, 'MM_Idle': 4, 'MM_HitReact_Front_Lgt_01': 4}
    for record in records:
        path = (out / record['file']).resolve()
        assert path.is_relative_to(out.resolve()) and sha(path) == record['sha256']
        error = record['pose_error']
        assert error['translation_cm'] < .025 and error['quaternion_error'] < .002 and error['time_seconds'] < .0001
    proof = {'baseline_directory': BASELINE, 'capture_manifest_sha256': sha(old_capture),
             'assets_manifest_sha256': sha(old_assets), 'unchanged_capture_count': 20,
             'changed_asset': changed[0], 'basis': 'identical rig, mesh, material, textures and non-attack animation packages'}
    return records, proof


def audit_reuse(out, report):
    if 'reused_capture_evidence' not in report:
        return
    records, proof = unmodified_captures(out)
    assert report['reused_capture_evidence'] == proof
    current = {r['file']: r for r in report['captures']}
    assert all(current.get(r['file']) == r for r in records), 'Reused pose evidence changed'
