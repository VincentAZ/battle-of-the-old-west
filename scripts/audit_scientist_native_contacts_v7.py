"""Read-only v7 contact audit; original full-bundle auditor remains unchanged.

The two corrected clips use fresh imported v7 poses. The other eleven clips,
all props, rifle curves, skin landmarks, physics and tolerances retain their
original references. Never treat an asset path alone as a version identifier.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import audit_scientist_native_contacts as base

STAGE = base.BASE/'holster-v7'
READBACK = STAGE/'native-readback-01.json'
MANIFEST = STAGE/'bundle/manifest.json'
INSTALL = STAGE/'runtime-provenance-install-01.json'
NAMES = ('Holster', 'Unholster')


def resolved(path):
    p = Path(path)
    return p if p.is_absolute() else base.ROOT/p


def verified(spec):
    p = resolved(spec['path'])
    base.require(base.sha(p) == spec['sha256'], 'Reference hash changed', p)
    return p


def local_rows(rows, parents):
    result = []
    for row in rows:
        component = {n: base.transform(t) for n, t in row['bones'].items()}
        base.require(set(component) == set(parents), 'Exact 54 bone identities required')
        result.append({n: base.relative(component[parents[n]], t) if parents[n] in component else t
                       for n, t in component.items()})
    return result


def quarter_pose(local, quarter, parents):
    a = min(quarter//4, 90); b = min(a+1, 90); alpha = quarter/4-a
    mixed = {n: base.blend(local[a][n], local[b][n], alpha) for n in parents}
    result = {}
    def build(n):
        if n not in result:
            p = parents[n]
            result[n] = base.compose(build(p), mixed[n]) if p in mixed else mixed[n]
        return result[n]
    for n in parents:
        build(n)
    return result


class V7Reference(base.Reference):
    def __init__(self):
        super().__init__()
        manifest = base.read(MANIFEST)
        complete_path = verified(manifest['complete_contract'])
        dense_path = verified(manifest['expectations'])
        runtime_path = verified(manifest['runtime_provenance_update'])
        complete, dense, runtime = map(base.read, (complete_path, dense_path, runtime_path))
        base.require(complete['animation_file_count'] == 13 and complete['static_prop_count'] == 11,
                     'Complete bundle count changed')
        base.require(verified(complete['replaces_complete_contract']) == base.CONTRACT,
                     'Wrong original full-bundle reference')
        base.require(dense['complete_contract_sha256'] == runtime['complete_contract_sha256'] == base.sha(complete_path),
                     'v7 dense/runtime contract provenance differs')
        for spec in complete['contracts']:
            p = verified(spec); self.provenance[str(p)] = base.sha(p)
        for p, h in dense['provenance'].items():
            base.require(base.sha(p) == h, 'Fresh source expectation provenance changed', p)
            self.provenance[p] = h
        old_complete, old_dense = base.read(base.CONTRACT), base.read(base.EXPECTATIONS)
        changed = {base.asset(n) for n in NAMES}
        base.require(complete['static_props'] == old_complete['static_props'] and dense['props'] == old_dense['props'],
                     'An unchanged prop reference was replaced')
        base.require(set(dense['clips']) == set(old_dense['clips']), 'Clip identity set changed')
        for asset, rows in old_dense['clips'].items():
            if asset not in changed:
                base.require(dense['clips'][asset] == rows, 'Unrelated clip expectation changed', asset)
        base.require([r for r in complete['animations'] if r['asset'] not in changed] ==
                     [r for r in old_complete['animations'] if r['asset'] not in changed],
                     'Unrelated animation contract changed')
        original_runtime = base.read(STAGE/'bundle/protected-live-inputs/scientist-presentation.json')
        comparable = copy.deepcopy(runtime)
        comparable['complete_contract_sha256'] = original_runtime['complete_contract_sha256']
        base.require(comparable == original_runtime, 'Runtime props, rifle curves or playback timing changed')

        audit = base.read(READBACK)
        base.require(audit['ok'] and audit['mode'] == 'readback' and audit['protected_inputs_unchanged']
                     and audit['changed_inputs'] == [] and audit['unexpected_changes'] == [],
                     'v7 fresh readback was not immutable and accepted')
        import_path = verified(audit['import_report']); imported = base.read(import_path)
        base.require(imported['ok'] and imported['mode'] == 'import' and imported['protected_inputs_unchanged']
                     and imported['saved_animation_sha256'] == audit['saved_animation_sha256'],
                     'v7 saved animation identity differs between import and readback')
        for p, h in audit['source_provenance'].items():
            base.require(base.sha(p) == h, 'Selective importer source provenance changed', p)
            self.provenance[p] = h
        replacement_path = STAGE/'runtime-integration-contract.json'
        replacement = base.read(replacement_path)
        base.require(audit['source_provenance'][str(replacement_path)] == base.sha(replacement_path),
                     'Readback did not use v7 source contract')
        base.require({r['asset'] for r in audit['animations']} == changed and len(audit['animations']) == 2,
                     'Expected exactly two readback clips')
        pose_path = verified(audit['dense_native_pose_report']); native = base.read(pose_path)
        base.require(set(native) == changed, 'Readback contains a wrong clip')
        self.overlay_checks = []
        for name in NAMES:
            asset = base.asset(name); rows = native[asset]
            base.require(len(rows) == 361, 'Incomplete quarter-frame native readback', name)
            for i, row in enumerate(rows):
                base.require(abs(row['seconds']-i/120) < 1e-7 and abs(row['frame']-(1+i/4)) < 1e-7,
                             'Nonuniform quarter-frame readback clock', name, i)
                base.require(set(row['bones']) == set(self.parent), 'Native bone identities changed', name, i)
            expected = dense['clips'][asset]
            published = replacement['dense_expected_native_samples'][name]
            base.require(len(expected) == len(published) == 91, 'Source clip must retain 91 keys', name)
            source_rows = []
            for i, (e, p) in enumerate(zip(expected, published)):
                base.require(e['bones'] == p['bones'] and e['frame'] == p['frame'] == i+1
                             and abs(e['seconds']-i/30) < 1e-7, 'Saved-blend expectation differs from contract', name, i)
                base.require(set(e['bones']) == set(self.parent)-{'Survivor_Rig'}, 'Expected 53 authored bones')
                source_rows.append({'bones':dict(e['bones'], Survivor_Rig={
                    'translation_cm':[0,0,0], 'rotation_xyzw':[0,0,0,1], 'scale':[1,1,1]})})
                # Only bone poses change. Receiver, rifle/contact state and
                # every other published channel must remain byte-equivalent.
                base.require({k:v for k,v in p.items() if k != 'bones'} ==
                             {k:v for k,v in self.published[name][i].items() if k != 'bones'},
                             'Non-bone authoring track changed', name, i)
            source_local = local_rows(source_rows, self.parent)
            integer = rows[::4]
            # Keep the 30 Hz clock used by 91-row prop/rifle tracks. Using all
            # 361 keys here would silently index the wrong prop sample.
            self.times[name] = [r['seconds'] for r in integer]
            self.poses[name] = local_rows(integer, self.parent)
            maxima = [0.,0.,0.]
            resampling = [0.,0.,0.]
            for i, row in enumerate(rows):
                wanted = quarter_pose(source_local, i, self.parent)
                reconstructed = self.pose(name, row['seconds'])
                for n, t in row['bones'].items():
                    actual = base.transform(t)
                    errors = base.distance(actual, wanted[n])
                    approximation = base.distance(actual, reconstructed[n])
                    maxima = [max(a,b) for a,b in zip(maxima, errors)]
                    resampling = [max(a,b) for a,b in zip(resampling, approximation)]
                    base.require(errors[0] <= .12 and errors[1] <= .2 and errors[2] <= .0005,
                                 'Native v7 pose differs from independently saved source', name, i, n, errors)
                    base.require(approximation[0] <= .12 and approximation[1] <= .2 and approximation[2] <= .0005,
                                 '30 Hz native reconstruction exceeds existing tolerance', name, i, n, approximation)
            self.overlay_checks.append({'clip':name,'native_samples':361,'bones_per_sample':54,
                'runtime_reference_keys':91,'source_maximum_cm_degrees_scale':maxima,
                'native_30hz_reconstruction_maximum_cm_degrees_scale':resampling})
        for p in (MANIFEST, complete_path, dense_path, runtime_path, READBACK, import_path, pose_path):
            self.provenance[str(p)] = base.sha(p)
        self.saved_animation_sha256 = audit['saved_animation_sha256']
        self.runtime_path = runtime_path


def install_evidence(ref, path):
    record = base.read(path)
    base.require(record['ok'] and record['semantic_changes'] == ['complete_contract_sha256'], 'Runtime metadata install failed')
    base.require(resolved(record['native_readback']) == READBACK and verified(record['complete_contract']) ==
                 STAGE/'bundle/complete-candidate-contract.json', 'Runtime install references another bundle')
    base.require(record['after_sha256'] == base.sha(ref.runtime_path), 'Wrong installed runtime metadata hash')
    artifacts = dict(ref.saved_animation_sha256)
    artifacts['Content/Data/scientist-presentation.json'] = record['after_sha256']
    return {'install_record':{'path':str(path),'sha256':base.sha(path)},
        'expected_project_artifacts':artifacts,
        'current_artifacts':[{ 'path':str(base.ROOT/'game/OldWest'/p), 'sha256':base.sha(base.ROOT/'game/OldWest'/p),
            'matches_expected':base.sha(base.ROOT/'game/OldWest'/p) == h} for p,h in artifacts.items()],
        'scope':'Import/readback and metadata-install records plus read-only hashes at audit time. '
                'This is not a prelaunch snapshot and does not independently prove their load time in a previous process.'}


def prelaunch_evidence(ref, path):
    data = path.read_bytes(); record = json.loads(data)
    base.require(record['schema'] == 'oldwest.root-native-inputs.v1', 'Wrong prelaunch schema')
    values = record['input_sha256']
    base.require(values and all(Path(p).is_absolute() and len(h) == 64 and
        all(c in '0123456789abcdef' for c in h) for p,h in values.items()), 'Malformed prelaunch fingerprints')
    expected = {str(base.ROOT/'game/OldWest'/p):h for p,h in ref.saved_animation_sha256.items()}
    expected[str(base.ROOT/'game/OldWest/Content/Data/scientist-presentation.json')] = base.sha(ref.runtime_path)
    missing_or_wrong = [p for p,h in expected.items() if values.get(p) != h]
    changes = []
    for p,h in values.items():
        current = base.sha(p) if Path(p).is_file() else None
        if current != h:
            changes.append({'path':p,'prelaunch_sha256':h,'current_sha256':current})
    return {'path':str(path.resolve()),'sha256':hashlib.sha256(data).hexdigest(),
        'captured_utc':record['captured_utc'],'recorded_timing':record['timing'],
        'fingerprints_compared':len(values),'expected_v7_artifacts':expected,
        'missing_or_wrong_v7_artifacts':missing_or_wrong,'changed_inputs':changes,
        'ok':not changes and not missing_or_wrong,
        'scope':'Exact recorded prelaunch fingerprints compared to current files; the timestamp and launch ordering are root-recorded evidence.'}


def check_immutable_inputs(audit, inputs):
    changed = [r['path'] for r in inputs if not Path(r['path']).is_file() or base.sha(r['path']) != r['sha256']]
    audit.check(not changed,'observed_input_files_unchanged_at_finish',changed_files=changed)
    return not changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('samples',type=Path,nargs='+')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--rows-output',type=Path)
    parser.add_argument('--brackets',type=Path,nargs='*')
    parser.add_argument('--scenario-results',type=Path,nargs='*')
    parser.add_argument('--runtime-install-report',type=Path,default=INSTALL)
    parser.add_argument('--prelaunch-manifest',type=Path,
                        help='Optional root-native-inputs.v1 fingerprints; when supplied, exact unchanged identity is required for PASS.')
    args = parser.parse_args()
    base.require(not args.output.exists(), 'Preserve previous report', args.output)
    base.require(not args.rows_output or not args.rows_output.exists(), 'Preserve per-frame evidence')
    ref = V7Reference(); audit = base.Auditor(ref); inputs = []; brackets = []; completions = []
    all_evidence = []; scenarios = []
    def read_evidence(path):
        data = path.read_bytes()
        all_evidence.append({'path':str(path.resolve()),'sha256':hashlib.sha256(data).hexdigest()})
        return json.loads(data)
    for path in args.samples:
        data = path.read_bytes()
        inputs.append({'path':str(path.resolve()),'sha256':hashlib.sha256(data).hexdigest(),'bytes_observed':len(data)})
        all_evidence.append(inputs[-1])
        for number, line in enumerate(data.decode().splitlines(),1):
            if not line.strip(): continue
            try: audit.observe(json.loads(line))
            except (ValueError,KeyError,TypeError,IndexError,ZeroDivisionError) as error:
                audit.check(False,'malformed_or_unverifiable_observation',file=str(path),line=number,error=str(error))
    for path in args.scenario_results or []:
        result = read_evidence(path); final = result['scientist_final']
        scenarios.append({'path':str(path),'sha256':all_evidence[-1]['sha256'],'ok':result['ok'],
            'failure':result.get('failure'),'owned_process_cleanup_complete':result.get('owned_process_cleanup_complete'),
            'completion_present':final is not None,'recorded_build':result['build']})
        if final is None:
            continue  # Retain partial observed-frame evidence without inventing a completion.
        audit.observe({'playback':final['playback'],'analysis':{'active':[],'history':[final]}})
        completions.append({'path':str(path),'sha256':all_evidence[-1]['sha256'],'completion_reason':final['completion_reason'],
                            'recorded_build':result['build']})
    for path in args.brackets or []:
        data = read_evidence(path)
        for when in ('before','after'):
            state = data[when]['cinematic']
            for p in state['scientist_analysis']['playbacks']:
                units = [u for u in state['units'] if u['id'] == p['performer_id'] and u['side'] == p['performer_side']]
                audit.check(len(units) == 1,'capture_actual_performer',file=str(path),when=when)
                if len(units) != 1: continue
                u = units[0]; m = u['manual_presentation']; pm = p['unit_manual']
                audit.check(u['card_id'] == 'prospector' and u['visual_mesh'] ==
                    '/Game/Art/Survivors/Variants/SKM_Prospector_Cm.SKM_Prospector_Cm',
                    'capture_actual_landmark_mesh_identity',file=str(path),mesh=u['visual_mesh'])
                audit.check(m['sample_frame'] == pm['sample_frame'] and m['body_bone_revision'] == pm['body_bone_revision'],
                            'capture_actual_unit_sample_identity',file=str(path),when=when)
                brackets.append({'path':str(path),'sha256':all_evidence[-1]['sha256'],'when':when,'phase':p['phase'],
                    'sample_frame':m['sample_frame'],'visual_mesh':u['visual_mesh']})
    linkage = install_evidence(ref, args.runtime_install_report)
    prelaunch = prelaunch_evidence(ref,args.prelaunch_manifest) if args.prelaunch_manifest else None
    if prelaunch:
        audit.check(prelaunch['ok'],'prelaunch_artifact_identity_unchanged',
            changed_inputs=prelaunch['changed_inputs'],missing_or_wrong_v7_artifacts=prelaunch['missing_or_wrong_v7_artifacts'])
        all_evidence.append({'path':prelaunch['path'],'sha256':prelaunch['sha256']})
    immutable = check_immutable_inputs(audit,all_evidence)
    report = audit.report()
    report.update(schema='oldwest.scientist.native-contact-audit.v7', inputs=inputs, capture_mesh_identity=brackets,
        retained_completions=completions, corrected_reference_checks=ref.overlay_checks,
        recorded_scenario_results=scenarios,prelaunch_artifact_linkage=prelaunch,
        installed_artifact_linkage=linkage, adapter_sha256=base.sha(__file__),
        capture_mesh_identity_verified=bool(brackets) and not any(f['check'].startswith('capture_') for f in audit.failures),
        observed_input_files_unchanged_at_finish=immutable,evidence_files=all_evidence)
    report['limitations'].append(prelaunch['scope'] if prelaunch else linkage['scope'])
    if any(not s['completion_present'] for s in scenarios):
        report['limitations'].append('A supplied scenario ended before completion; this report evaluates only its observed frames and does not mark its gameplay/UI scenario passed.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    if args.rows_output:
        args.rows_output.parent.mkdir(parents=True,exist_ok=True)
        args.rows_output.write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in audit.rows))
    print(json.dumps({'ok':report['ok'],'rows':audit.checked,'failures':audit.failure_count,'output':str(args.output)}))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
