"""Pure-Python validation of the complete, reviewed Prospector import bundle.

No Unreal import, subprocess, or Content mutation. Shared by the CPU extractor
and the coordinated editor importer; failures are explicit even with python -O.
"""
import hashlib
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'art/characters/scientist_gesture'
DEST = '/Game/Art/Survivors/ScientistAnalysis'
CONTRACT = BASE / 'complete-candidate-contract.json'
EXPECTATIONS = BASE / 'import-expectations-v1.json'


def require(condition, *message):
    if not condition:
        raise ValueError(' '.join(str(x) for x in message))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def source_path(value):
    path = Path(value)
    path = (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    require(path.is_relative_to(BASE.resolve()), 'Source escapes Prospector authoring directory:', path)
    require(path.is_file(), 'Missing source:', path)
    return path


def read(path):
    return json.loads(Path(path).read_text())


def check_transform(value, label):
    p, q, s = (value[k] for k in ('translation_cm', 'rotation_xyzw', 'scale'))
    require(len(p) == 3 and len(q) == 4 and len(s) == 3, 'Malformed transform', label)
    require(all(math.isfinite(x) for x in (*p, *q, *s)), 'Nonfinite transform', label)
    require(abs(sum(x*x for x in q)-1) < .0001, 'Nonunit quaternion', label)
    require(max(abs(x-1) for x in s) < .001, 'Unexpected authored scale', label)


def difference(a, b):
    qa, qb = a['rotation_xyzw'], b['rotation_xyzw']
    norm = math.sqrt(sum(x*x for x in qa)*sum(x*x for x in qb))
    require(norm > 0, 'Zero quaternion')
    cosine = min(1., abs(sum(x*y for x, y in zip(qa, qb)))/norm)
    return math.dist(a['translation_cm'], b['translation_cm']), math.degrees(2*math.acos(cosine))


def endpoint_checks(clips, position_limit=.01, angle_limit=.1):
    """Same contract used on CPU expectations and independently imported poses."""
    def pose(name, frame):
        return next(r['bones'] for r in clips[DEST+'/Animations/A_Scientist_'+name+'_Cm'] if r['frame'] == frame)
    pairs = [('Holster',91,'Full',1), ('Unholster',1,'Full',271),
             ('Holster',1,'Unholster',91), ('Full',1,'Full',271),
             ('WorkHold',1,'Full',135), ('WorkHold',61,'Full',135),
             ('SortLeft',1,'Full',135), ('SortLeft',61,'Full',185),
             ('SortRight',1,'Full',135), ('SortRight',61,'Full',185),
             ('SkipRecover',1,'Full',135), ('SkipRecover',87,'Full',271)]
    rows = []
    for a, af, b, bf in pairs:
        pa, pb = pose(a,af), pose(b,bf)
        require(set(pa) == set(pb), 'Endpoint bone identities differ')
        errors = [difference(pa[n],pb[n]) for n in pa]
        cm, degrees = max(x[0] for x in errors), max(x[1] for x in errors)
        require(cm < position_limit and degrees < angle_limit, 'Endpoint discontinuity',a,af,b,bf,cm,degrees)
        rows.append(dict(a=[a,af], b=[b,bf], bones=len(pa), maximum_position_cm=cm, maximum_angle_degrees=degrees))
    return rows


def load_bundle(expectations=True):
    bundle = read(CONTRACT)
    require(bundle['animation_file_count'] == len(bundle['animations']) == 13, 'Expected 13 clips')
    require(bundle['static_prop_count'] == len(bundle['static_props']) == 11, 'Expected 11 props')
    provenance = {str(CONTRACT): sha(CONTRACT)}

    def tracked(path, expected=None):
        path = source_path(path)
        digest = sha(path)
        require(expected is None or digest == expected, 'Source hash changed:', path)
        provenance[str(path)] = digest
        return path

    contracts = {}
    for row in bundle['contracts']:
        path = tracked(row['path'], row['sha256'])
        contracts[str(path)] = read(path)
    core_path = BASE / 'candidate-v11/runtime-integration-contract.json'
    core = contracts[str(core_path)]
    branch = contracts[str(BASE / 'decision-branch-contract.json')]
    holster = contracts[str(BASE / 'holster-v3/runtime-integration-contract.json')]
    manifest_path = tracked(core_path.parent/'manifest.json', core['source_manifest_sha256'])
    manifest = read(manifest_path)
    core_blend = tracked(core_path.parent/'Scientist_Analysis_Candidate.blend', core['source_blend_sha256'])
    require(manifest['blend_sha256'] == sha(core_blend), 'Core manifest blend mismatch')
    require(manifest['rig_bones'] == 53 and manifest['expected_native_bones'] == 54
            and manifest['rig_reference_unchanged'] and manifest['protected_source_and_native_assets_unchanged'], 'Core rig preservation')
    core_review = read(tracked(core_path.parent/'manual-review.json'))
    require(core_review['accepted_for_native_candidate_import'] is True, 'Core CPU review not accepted')
    require(core_review['source_blend_sha256'] == sha(core_blend)
            and core_review['contract_sha256'] == sha(core_path), 'Core review provenance')
    tracked(core_path.parent/'skin-contact-audit.json', core_review['skin_audit_sha256'])
    branch_review = read(tracked(BASE/'decision-branch-manual-review.json'))
    require(branch_review['status'] == 'CPU_decision_branch_candidates_accepted_for_native_candidate_validation', 'Branch review not accepted')
    holster_review = read(tracked(BASE/'holster-v3/manual-review.json'))
    require(holster_review['accepted_for_native_candidate_validation'] is True
            and holster_review['original_assets_unchanged'], 'Holster CPU review not accepted')
    hblend = tracked(holster['source_blend'], holster['source_blend_sha256'])
    require(holster_review['source_blend_sha256'] == sha(hblend), 'Holster review provenance')
    tracked(hblend.parent/'manifest.json')
    tracked(BASE/'holster-reference/native-reference.json')
    by_asset = {}
    for clip in core['clips']:
        by_asset[clip['asset']] = dict(frames=clip['source_frames'], blend=str(core_blend),
            published=core['dense_expected_native_samples'], fixed_feet=True, source_hash=clip['source_fbx_sha256'], contract=str(core_path))
    require(branch['core_contract_sha256'] == sha(core_path), 'Branch core contract mismatch')
    for clip in branch['branch_sources']:
        path = tracked(clip['source_manifest'], clip['source_manifest_sha256'])
        data = read(path)
        blend = tracked(data['blend'], clip['blend_sha256'])
        require(data['bones'] == 53 and data['expected_native_bones'] == 54
                and data['protected_source_and_native_assets_unchanged'], 'Branch rig preservation')
        matches = [r for r in branch_review['branches'] if r['name'] == clip['name']]
        require(len(matches) == 1 and matches[0]['blend_sha256'] == sha(blend), 'Branch review provenance')
        audit = read(tracked(path.parent/'skin-contact-audit.json'))
        require(audit['source_sha256'] == sha(blend) and audit['all_authored_30hz_frames'] and audit['source_unchanged'], 'Branch audit provenance')
        by_asset[clip['animation_asset']] = dict(frames=clip['frames'], blend=str(blend),
            published=clip['dense_expected_native_samples'], fixed_feet=True, source_hash=clip['source_fbx_sha256'], contract=str(BASE/'decision-branch-contract.json'))
    for clip in holster['clips']:
        name = Path(clip['path']).stem.removeprefix('A_Scientist_').removesuffix('_Cm')
        blend = tracked(hblend.parent/f'Scientist_{name}_Candidate.blend')
        by_asset[clip['asset']] = dict(frames=clip['frames'], blend=str(blend),
            published=holster['dense_expected_native_samples'][name], fixed_feet=False, source_hash=clip['sha256'], contract=str(BASE/'holster-v3/runtime-integration-contract.json'))
    require(len(by_asset) == 13, 'Duplicate or missing clip definitions')
    clips = []
    for row in bundle['animations']:
        path = tracked(row['source_fbx'], row['source_fbx_sha256'])
        require(re.fullmatch(r'A_Scientist_[A-Za-z]+_Cm', path.stem), 'Unexpected clip name')
        require(row['asset'] == DEST+'/Animations/'+path.stem, 'Unexpected clip destination')
        item = by_asset.pop(row['asset'])
        require(str(source_path(row['expected_contract'])) == item['contract'], 'Wrong clip expected contract',path)
        require(item['source_hash'] == row['source_fbx_sha256'], 'Clip/subcontract hash mismatch')
        first, last = item['frames']
        require(first >= 1 and last > first and abs(row['seconds']-(last-first)/30) < 1e-9, 'Clip duration mismatch', path)
        samples = {v.get('source_frame', v.get('frame')): v for v in item['published']}
        require(all(frame in samples for frame in range(first, last+1)), 'Missing dense authored frame', path)
        for frame in range(first,last+1):
            sample = samples[frame]
            for name,transform in sample['bones'].items():
                check_transform(transform,(path,frame,name))
            if 'props' in sample:
                require(set(sample['props']) == {p['pivot_name'] for p in core['props']}, 'Dense prop identities differ',path,frame)
                for name,transform in sample['props'].items():
                    check_transform(transform,(path,frame,name))
            else:
                check_transform(sample['rifle_body_relative'],(path,frame,'rifle'))
        clips.append(dict(row, **{k:v for k,v in item.items() if k != 'published'},
                          source_fbx=str(path), published={f:samples[f] for f in range(first,last+1)}))
    require(not by_asset, 'Unlisted clip')
    props = []
    for row in bundle['static_props']:
        name = row['asset'].rsplit('/',1)[1]
        require(re.fullmatch(r'SM_[A-Za-z][A-Za-z0-9_]*_Cm', name), 'Unexpected prop name', name)
        require(row['asset'] == DEST+'/Props/'+name, 'Unexpected prop destination')
        path = tracked(row.get('source_fbx', str(core_path.parent/(name+'.fbx'))),
                       row.get('source_fbx_sha256', row.get('sha256')))
        slots = row['material_slots']
        require(slots and len(set(slots)) == len(slots) and set(slots) <= set(manifest['materials']), 'Invalid material slots', name)
        check_transform(row.get('initial_body_relative_transform',row.get('body_relative_transform')), name)
        props.append(dict(row, source_fbx=str(path), source_fbx_sha256=sha(path)))
    require(len({p['asset'] for p in props}) == 11, 'Duplicate prop')
    for data in manifest['materials'].values():
        require(len(data['base_color']) == 3 and all(math.isfinite(x) and 0 <= x <= 1 for x in data['base_color']), 'Invalid base color')
        require(all(math.isfinite(data[k]) and 0 <= data[k] <= 1 for k in ('roughness','metallic')), 'Invalid material scalar')
        require(math.isfinite(data['emission']) and data['emission'] >= 0, 'Invalid emission')
    result = dict(clips=clips, props=props, materials=manifest['materials'], provenance=provenance,
                  core=core, branch=branch, holster=holster)
    if expectations:
        dense = read(EXPECTATIONS)
        require(dense['complete_contract_sha256'] == sha(CONTRACT), 'Stale dense complete contract')
        require(dense['provenance'] == provenance, 'Stale dense source provenance')
        require(len(dense['bone_names']) == len(set(dense['bone_names'])) == 53, 'Expected exact 53 authored bones')
        require(set(dense['clips']) == {c['asset'] for c in clips}, 'Dense clip set mismatch')
        for clip in clips:
            rows = dense['clips'][clip['asset']]
            require([s['frame'] for s in rows] == list(range(clip['frames'][0],clip['frames'][1]+1)), 'Dense frame coverage', clip['asset'])
            for row in rows:
                require(set(row['bones']) == set(dense['bone_names']), 'Dense bone set mismatch')
                for name, transform in row['bones'].items():
                    check_transform(transform, name)
                    if name in clip['published'][row['frame']]['bones']:
                        cm, degrees = difference(transform, clip['published'][row['frame']]['bones'][name])
                        require(cm < .01 and degrees < .1, 'Dense/published pose mismatch',clip['asset'],row['frame'],name,cm,degrees)
        require(set(dense['props']) == {p['asset'] for p in props}, 'Dense prop set mismatch')
        result['endpoints'] = endpoint_checks(dense['clips'])
        result['dense'] = dense
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--without-dense', action='store_true')
    args = parser.parse_args()
    result = load_bundle(not args.without_dense)
    print(json.dumps({'status':'CPU_preflight_pass_native_unverified','clips':len(result['clips']),
                      'props':len(result['props']),'materials':len(result['materials']),
                      'source_files_hashed':len(result['provenance']),
                      'authored_frame_checks':sum(c['frames'][1]-c['frames'][0]+1 for c in result['clips'])}))
