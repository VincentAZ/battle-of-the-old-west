#!/usr/bin/env python3
"""Audit retained native presentation timings without launching Unreal.

Reports observations and missing evidence. Renderer counters can lag physics;
this tool does not turn temporal correlation into a causal attribution.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path


def signature(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def distribution(values):
    values = sorted(value for value in values if value is not None)
    if not values:
        return {'count': 0}
    assert all(isinstance(value, (int, float)) and math.isfinite(value) and value >= 0 for value in values)
    def percentile(fraction):
        position = (len(values) - 1) * fraction
        lower, upper = math.floor(position), math.ceil(position)
        return values[lower] + (values[upper] - values[lower]) * (position - lower)
    return {'count': len(values), 'mean': sum(values)/len(values), 'p50': percentile(.5),
            'p95': percentile(.95), 'p99': percentile(.99), 'maximum': values[-1]}


def normalize(q):
    assert len(q) == 4 and all(math.isfinite(value) for value in q)
    length = math.sqrt(sum(value*value for value in q))
    assert length > 0
    return [value/length for value in q]


def body_motion(target):
    physics = target['physics']; pose = physics['pose_motion']; dt = pose['delta_seconds']
    assert pose['valid'] and pose['query_frame'] == pose['sample_frame'] == pose['previous_frame'] + 1
    assert math.isfinite(dt) and dt > 0 and len(pose['bodies']) == pose['body_count'] == 16
    assert len({body['bone'] for body in pose['bodies']}) == 16
    rows = []
    for body in pose['bodies']:
        previous, current = body['previous_com_cm'], body['current_com_cm']
        assert len(previous) == len(current) == 3 and all(math.isfinite(v) for v in previous+current)
        qa, qb = normalize(body['previous_rotation_xyzw']), normalize(body['current_rotation_xyzw'])
        # Relative quaternion inv(previous)*current. atan2 supplies an
        # independent reconstruction of the native abs-dot/acos calculation.
        a = [-value for value in qa[:3]]; b = qb[:3]
        cross = [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
        vector = [qa[3]*b[i]+qb[3]*a[i]+cross[i] for i in range(3)]
        scalar = qa[3]*qb[3]-sum(a[i]*b[i] for i in range(3))
        angle = math.degrees(2*math.atan2(math.sqrt(sum(value*value for value in vector)), abs(scalar)))
        linear, angular = math.dist(previous,current)/dt, angle/dt
        assert abs(linear-body['speed_cm_s']) < .001 and abs(angular-body['angular_speed_deg_s']) < .01
        rows.append({'bone':body['bone'],'linear_cm_s':linear,'angular_deg_s':angular})
    return {'target':target['target'],'sample_frame':pose['sample_frame'],'delta_seconds':dt,
            'independent_pair_verified':True,'maximum_pose_linear_cm_s':max(row['linear_cm_s'] for row in rows),
            'maximum_pose_angular_deg_s':max(row['angular_deg_s'] for row in rows),
            'fastest_angular_body':max(rows,key=lambda row:row['angular_deg_s']),
            'stored_maximum_linear_cm_s':physics['max_speed_cm_s'],
            'stored_maximum_angular_deg_s':physics['max_angular_speed_deg_s'],
            'ground_found':physics['ground_found'],'pelvis_ground_clearance_cm':physics['pelvis_ground_clearance_cm']}


def analyze(folder, allow_unprofiled=False):
    result_path = folder/'result.json'; result = json.loads(result_path.read_text())
    inputs = [result_path,Path(__file__).resolve()]
    for name in ('build.json','native-launches.json'):
        if (folder/name).is_file(): inputs.append(folder/name)
    lifecycle_path = folder/'lifecycle-performance.jsonl'
    lifecycle = []
    if lifecycle_path.is_file():
        inputs.append(lifecycle_path)
        lifecycle = [json.loads(line) for line in lifecycle_path.read_text().splitlines() if line]
    issues = []
    if not result.get('profile_renderer') and not allow_unprofiled:
        issues.append('Run does not record --profile-renderer; native/report timing evidence is incomplete.')
    if not lifecycle and not allow_unprofiled:
        issues.append('No retained lifecycle report-cost samples.')
    channels = ['game_active_ms','game_wait_ms','game_critical_path_ms','render_active_ms',
                'render_wait_ms','render_critical_path_ms','rhi_active_ms','gpu_ms','present_ms']
    frame_rows, shots, falls = [], [], []
    for completion in result.get('completed_falls',[]):
        key = (completion.get('match_id'),completion['sequence'])
        frames = completion.get('frame_performance',{}).get('samples',[])
        timing = completion.get('frame_timing',{})
        shot = {'match_id':key[0],'sequence':key[1],'kind':completion['kind'],'reason':completion['reason'],
                'elapsed_seconds':completion['elapsed'],'frame_timing':timing,'retained_native_frames':len(frames)}
        if frames:
            assert all(a['frame'] < b['frame'] for a,b in zip(frames,frames[1:])), key
            for frame in frames:
                assert math.isfinite(frame['frame_delta_ms']) and frame['frame_delta_ms'] >= 0
                assert 0 <= frame['estimated_physics_delta_ms'] <= frame['frame_delta_ms'] + .01
                frame_rows.append({'match_id':key[0],'sequence':key[1],'kind':completion['kind'],**frame})
            performance = completion['frame_performance']
            assert performance['total_shot_frames'] == timing['frames']
            assert len(frames) == min(performance['capacity'], timing['frames'])
            complete = performance['dropped_oldest_frames'] == 0
            shot['complete_per_shot_frame_series'] = complete
            shot['capped_frame_count'] = sum(f['frame_delta_ms'] > f['estimated_physics_delta_ms']+.01 for f in frames)
            shot['native_counter_distributions_ms'] = {channel:distribution(f.get(channel) for f in frames) for channel in channels}
            if complete:
                elapsed = sum(f['frame_delta_ms'] for f in frames)/1000
                physics = sum(f['estimated_physics_delta_ms'] for f in frames)/1000
                assert abs(elapsed-completion['elapsed']) < .002, (key,elapsed,completion['elapsed'])
                assert abs(physics-timing['estimated_physics_seconds']) < .002
                shot['independent_delta_sums_verified'] = True
                shot['estimated_submitted_physics_seconds'] = physics
                shot['estimated_physics_to_presentation_fraction'] = physics/elapsed if elapsed else None
            if frames and all('settling_required' in frame for frame in frames) and completion.get('waited_for_settling'):
                stable = 0. if complete else None
                resets = []
                late_failures = Counter()
                for frame in frames:
                    assert frame['settling_required'], (key, frame['frame'])
                    assert frame['all_ragdolls_settled'] == (not frame['settling_failure']), (key, frame['frame'])
                    if stable is not None:
                        expected = stable + frame['estimated_physics_delta_ms']/1000 if frame['all_ragdolls_settled'] else 0.
                        assert abs(expected-frame['stable_seconds']) < .002, (key, frame['frame'], expected, frame['stable_seconds'])
                        if stable > 0 and not frame['all_ragdolls_settled']:
                            resets.append({'frame':frame['frame'],'elapsed_seconds':frame['elapsed'],
                                           'previous_stable_seconds':stable,'reason':frame['settling_failure']})
                    stable = frame['stable_seconds']
                    if frame['elapsed'] >= 1.95 and frame['settling_failure']:
                        for reason in frame['settling_failure'].rstrip(';').split(';'):
                            late_failures[reason.split('=',1)[-1].split(':',1)[0]] += 1
                assert abs(stable-completion['stable_seconds']) < .002, key
                assert frames[-1]['all_ragdolls_settled'] == completion['all_ragdolls_settled'], key
                shot['settling_trace'] = {'stable_intervals_independently_reconstructed':complete,
                    'sample_count':len(frames),'maximum_stable_seconds':max(frame['stable_seconds'] for frame in frames),
                    'stable_interval_reset_count':len(resets),'late_failure_frame_counts':dict(late_failures),
                    'last_resets':resets[-20:]}
        elif result.get('profile_renderer') and completion.get('elapsed',0) > .1:
            issues.append(f'Shot {key} has no retained enabled native frame profile.')
        if completion.get('waited_for_settling') and completion['reason'] != 'skipped':
            fall = {**shot,'stable_seconds':completion['stable_seconds'],
                    'all_ragdolls_settled':completion['all_ragdolls_settled'],
                    'targets':[body_motion(target) for target in completion['targets'] if target.get('ragdoll')]}
            falls.append(fall)
        shots.append(shot)
    report_groups = {}
    for peer in sorted({row['peer'] for row in lifecycle}):
        rows = [row for row in lifecycle if row['peer']==peer]
        identities = [(row['match_id'],row['native_frame'],row['command_sequence']) for row in rows]
        assert len(identities)==len(set(identities)), f'Duplicate {peer} lifecycle measurements'
        fields = sorted({key for row in rows for key in row if key.endswith('_ms')})
        report_groups[peer] = {'sample_count':len(rows),'timings_ms':{field:distribution(row.get(field) for row in rows) for field in fields},
            'report_characters':distribution(row.get('report_characters') for row in rows),
            'largest_total_cost_reports':sorted(rows,key=lambda row:row['total_control_report_ms'],reverse=True)[:12]}
    captures = [{'match_id':row.get('match_id'),'sequence':row['sequence'],'kind':row['kind'],
                'requested_phase':row['requested_phase'],'before_seconds':row['before_seconds'],'after_seconds':row['after_seconds'],
                'image':row['image'],'actual_phase_bracket_valid':row['actual_phase_bracket_valid'],
                **row['external_capture_timing']} for row in result.get('captures',[]) if 'external_capture_timing' in row]
    summary = {'native_harness_passed':result.get('ok'), 'timing_evidence_issues':issues,
        'profile_requested':result.get('profile_renderer',False),'observed_shots':len(shots),'retained_native_frame_count':len(frame_rows),
        'fall_count':len(falls),'natural_fall_count':sum(f['reason']=='settled' for f in falls),
        'timeout_fall_count':sum(f['reason']=='timeout' for f in falls),
        'frame_delta_ms':distribution(f['frame_delta_ms'] for f in frame_rows),
        'estimated_physics_delta_ms':distribution(f['estimated_physics_delta_ms'] for f in frame_rows),
        'native_counter_distributions_ms':{channel:distribution(f.get(channel) for f in frame_rows) for channel in channels},
        'capture_latency_ms':distribution(c['request_to_complete_png_ms'] for c in captures)}
    return {'run':str(folder),'inputs':[signature(path) for path in inputs],'build':result.get('build'),
        'summary':summary,'falls':falls,'shots':shots,'lifecycle_reports':report_groups,
        'slowest_native_frames':sorted(frame_rows,key=lambda frame:frame['frame_delta_ms'],reverse=True)[:30],
        'slowest_external_captures':sorted(captures,key=lambda capture:capture['request_to_complete_png_ms'],reverse=True)[:20],
        'method':['Independently sum retained per-shot native deltas and compare with completion clock totals.',
                  'Reconstruct final16-body COM motion and shortest quaternion motion via relative-quaternion atan2.',
                  'Group lifecycle costs by their own recorded peer/frame/match/shot, not the later report carrying them.'],
        'limitations':['Engine CPU counters are the latest completed viewport counters; GPU timings may lag further. They are not synchronized to the current physics pair.',
            'Estimated physics delta is the configured per-frame submitted-time cap, not a measured solver-completion clock; it includes time before ragdoll handoff.',
            'Lifecycle total includes measured control/report construction, serialization and atomic write. Tiny profiler-record bookkeeping after the write is outside that interval.',
            'External screenshot latency includes command/report polling, rendering/readback, PNG encoding and file availability; it is not CPU-only capture cost.',
            'The profiler itself adds bounded observation and serialization work, whose measured report cost is retained. This is not a no-instrumentation performance benchmark.',
            'This analysis does not change thresholds, duration, physics parameters or assets, and does not infer a bottleneck solely from correlation.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--allow-unprofiled',action='store_true',help='Audit legacy pose evidence while explicitly reporting absent timing data')
    args=parser.parse_args();folder=args.run.resolve();output=args.output or folder/'performance-audit.json'
    report=analyze(folder,args.allow_unprofiled)
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['summary'],indent=2))
    if report['summary']['timing_evidence_issues']:raise SystemExit(1)

if __name__=='__main__':main()
