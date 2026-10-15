#!/usr/bin/env python3
"""Audit native collision notifications against retained ragdoll identities and poses.

Events are the engine's dispatched collision summaries, not every solver
manifold point. Self contacts may be reported in both body directions.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path


def signature(path):
    return {'path':str(path.resolve()), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def magnitude(vector):
    assert len(vector)==3 and all(math.isfinite(v) for v in vector)
    return math.sqrt(sum(v*v for v in vector))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path)
    parser.add_argument('--late-after',type=float,default=2.,help='Seconds since physical handoff, not cinematic start')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    assert math.isfinite(args.late_after) and args.late_after>=0
    folder=args.run.resolve()
    native=json.loads((folder/'result.json').read_text())
    assert native.get('record_contacts'), 'Run did not request collision recording'
    path=folder/'ragdoll-contacts.jsonl'
    assert path.resolve()==Path(native['contact_report']).resolve()
    groups=defaultdict(list)
    with path.open() as source:
        for line in source:
            row=json.loads(line)
            fall_id=row['fall_id']
            assert isinstance(fall_id,int) and fall_id>0
            assert row['event_index']==len(groups[fall_id]), 'Missing, repeated or reordered contact records'
            assert row['contacts'], 'Engine event has no reported contact points'
            assert math.isfinite(row['seconds_since_ragdoll']) and row['seconds_since_ragdoll']>=0
            if groups[fall_id]:
                previous=groups[fall_id][-1]
                assert row['dispatch_frame']>=previous['dispatch_frame']
                assert row['seconds_since_ragdoll']>=previous['seconds_since_ragdoll']
                assert (row['target'],row['card_id'],row['actor'])==(previous['target'],previous['card_id'],previous['actor'])
            for key in ('normal_impulse_native','friction_impulse_native','body_delta_velocity_cm_s','other_body_delta_velocity_cm_s'):
                magnitude(row[key])
            for point in row['contacts']:
                magnitude(point['position_cm']);magnitude(point['normal_toward_body'])
                assert math.isfinite(point['penetration_cm'])
            groups[fall_id].append(row)
    assert groups, 'No collision events were recorded'

    identities={}
    poses=defaultdict(dict)
    completions={}
    expected_counts=defaultdict(int)

    def observe(match,sequence,target,elapsed,physics,completion=None):
        recording=physics.get('contact_recording',{})
        assert recording.get('enabled') and recording['fall_id']>0
        fall_id=recording['fall_id']
        identity={'match_id':match,'sequence':sequence,'target':target}
        assert identities.setdefault(fall_id,identity)==identity, 'One contact ID identifies multiple falls'
        expected_counts[fall_id]=max(expected_counts[fall_id],recording['events_written'])
        if completion:
            completions[fall_id]={**completion,'query_frame':physics.get('pose_motion',{}).get('query_frame')}
        pose=physics.get('pose_motion',{})
        if pose.get('valid'):
            frame=pose['sample_frame']
            poses[fall_id][frame]={'frame':frame,'cinematic_elapsed_seconds':elapsed,
                'bodies':{b['bone']:{'linear_cm_s':b['speed_cm_s'],'angular_deg_s':b['angular_speed_deg_s']}
                          for b in pose['bodies']}}

    for row in json.loads((folder/'observations.json').read_text()):
        c=row['cinematic']
        for t in [c,*c.get('simultaneous_targets',[])]:
            if t.get('ragdoll'):
                observe(row['match_id'],c['sequence'],t['target'],c['elapsed'],t['physics'])
    for c in native['completed_falls']:
        for t in c['targets']:
            if t.get('ragdoll'):
                observe(c['match_id'],c['sequence'],t['target'],c['elapsed'],t['physics'],
                        {k:c[k] for k in ('reason','elapsed','stable_seconds')})

    # A failure capture/audio export can outlive the harness assertion while
    # the real game finishes another queued fall. Preserve that final public
    # history without counting it as a harness-validated completion.
    supplemental=[]
    final_state=folder/'a.json'
    if final_state.exists():
        supplemental.append(final_state)
        final=json.loads(final_state.read_text())
        for c in final.get('cinematic',{}).get('completion_history',[]):
            for t in c['targets']:
                if not t.get('ragdoll'):continue
                recording=(t.get('physics') or {}).get('contact_recording') or {}
                if not recording.get('enabled') or recording['fall_id'] in completions:continue
                observe(c['match_id'],c['sequence'],t['target'],c['elapsed'],t['physics'],
                        {**{k:c[k] for k in ('reason','elapsed','stable_seconds')},
                         'supplemental_after_harness_assertion':True})

    issues=[]
    for fall_id,count in expected_counts.items():
        if len(groups.get(fall_id,[]))<count:
            issues.append(f'Fall {fall_id}: file has fewer events than its native counter ({count})')
    falls=[]
    for fall_id,rows in groups.items():
        if fall_id not in identities:
            issues.append(f'Fall {fall_id}: no retained public cinematic identity')
        else:
            assert rows[0]['target']==identities[fall_id]['target']
        completed_frame=completions.get(fall_id,{}).get('query_frame')
        in_shot=[r for r in rows if completed_frame is None or r['dispatch_frame']<=completed_frame]
        late=[r for r in in_shot if r['seconds_since_ragdoll']>=args.late_after]
        pairs=defaultdict(list)
        frames=defaultdict(list)
        for row in in_shot:
            frames[row['dispatch_frame']].append(row)
        for row in late:
            pairs[(row['bone'],row['other_bone'],row['other_component'],row['self_contact'])].append(row)
        pair_summaries=[]
        for (bone,other,component,self_contact),events in pairs.items():
            pair_summaries.append({'bone':bone,'other_bone':other,'other_component':component,'self_contact':self_contact,
                'late_event_count':len(events),'first_seconds_since_ragdoll':events[0]['seconds_since_ragdoll'],
                'last_seconds_since_ragdoll':events[-1]['seconds_since_ragdoll'],
                'minimum_signed_phi_cm':min(p['penetration_cm'] for r in events for p in r['contacts']),
                'maximum_reported_overlap_cm':max(0.,-min(p['penetration_cm'] for r in events for p in r['contacts'])),
                'maximum_normal_impulse_native_magnitude':max(magnitude(r['normal_impulse_native']) for r in events),
                'maximum_friction_impulse_native_magnitude':max(magnitude(r['friction_impulse_native']) for r in events)})
        motion=[]
        for frame,pose in poses.get(fall_id,{}).items():
            events=frames.get(frame,[])
            if not events or events[0]['seconds_since_ragdoll']<args.late_after:continue
            fastest=max(pose['bodies'],key=lambda bone:pose['bodies'][bone]['angular_deg_s'])
            relevant=[r for r in events if r['bone']==fastest or (r['self_contact'] and r['other_bone']==fastest)]
            motion.append({'frame':frame,'cinematic_elapsed_seconds':pose['cinematic_elapsed_seconds'],
                'fastest_rotating_bone':fastest,**pose['bodies'][fastest],
                'contacts_in_same_dispatch_frame':[{'event_index':r['event_index'],'bone':r['bone'],
                    'other_bone':r['other_bone'],'other_component':r['other_component'],
                    'minimum_signed_phi_cm':min(p['penetration_cm'] for p in r['contacts'])} for r in relevant]})
        falls.append({'fall_id':fall_id,**identities.get(fall_id,{}),'card_id':rows[0]['card_id'],
            'completion':completions.get(fall_id),'event_count':len(rows),'maximum_native_counter':expected_counts.get(fall_id),
            'events_after_completion_query_frame':len(rows)-len(in_shot),
            'distinct_dispatch_frames':len(frames),'late_event_count':len(late),
            'late_directed_pairs':sorted(pair_summaries,key=lambda p:p['late_event_count'],reverse=True),
            'sampled_pose_contacts':motion})
    report={'ok':not issues,'issues':issues,'native_harness_passed':native['ok'],
        'late_after_physical_handoff_seconds':args.late_after,'event_count':sum(map(len,groups.values())),
        'fall_count':len(falls),'falls':falls,
        'inputs':[signature(p) for p in (path,folder/'result.json',folder/'observations.json',folder/'build.json',Path(__file__),*supplemental)],
        'contact_distance_convention':'The native penetration_cm field preserves ContactPenetration, populated from Chaos GetPhi: negative overlap, positive separation.',
        'limitations':['Engine collision notifications omit zero-impulse contacts and do not enumerate every solver manifold point.',
            'Impulse vectors and contact normals are preserved as dispatched by the engine, including its ordering conventions.',
            'Self contacts can appear twice, once per body; directed counts and impulse magnitudes must not be summed into net force.',
            'Dispatch frames are game-thread notification frames, not an assertion of solver-substep timestamps.',
            'A contact in the same dispatch frame as a pose sample is correlation, not proof that it caused the motion.',
            'Collision capture and screenshots add diagnostic overhead; no damping, geometry, solver or settling overrides are applied.']}
    destination=args.output or folder/'contact-audit.json'
    destination.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('ok','issues','native_harness_passed','event_count','fall_count')},indent=2))
    raise SystemExit(0 if report['ok'] else 1)


if __name__=='__main__':
    main()
