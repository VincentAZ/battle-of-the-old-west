"""CPU-only comparison of observed Prospector frames against accepted source data.

Inputs are the root legal-action harness's scientist-samples.jsonl, immutable
native imported 30 Hz bone readback, and independently authored prop contracts.
No Unreal launch, private game state, playback changes, or evidence overwrite.
"""
import argparse
import bisect
import collections
import hashlib
import json
import math
from pathlib import Path

from scientist_import_contract import BASE, ROOT, CONTRACT, EXPECTATIONS, read, require, sha

AUDIT = BASE/'native-complete-audits/readback-01.json'
HIERARCHY = ROOT/'art/characters/survivor_variants/deformation-v3/native-reference-audit.json'
LANDMARKS = BASE/'playback-stage/contact-auditor/skin-landmarks-v1.json'
SOLES = BASE/'playback-stage/ground-probe-stage/sole-landmarks-v2.json'
BONES = ('root','Hips','Head','LeftHand','RightHand','LeftFoot','RightFoot',
         'LeftHandIndex1','LeftHandPinky1','RightHandIndex1','RightHandPinky1')
TRACKS = ('Full','Holster','Unholster','WorkHold','SortLeft','SortRight','SkipRecover')
DEST = '/Game/Art/Survivors/ScientistAnalysis/Animations/A_Scientist_'


def add(a,b): return [x+y for x,y in zip(a,b)]
def sub(a,b): return [x-y for x,y in zip(a,b)]
def mul(a,b): return [x*y for x,y in zip(a,b)]
def scale(a,b): return [x*b for x in a]
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def norm(a): return math.sqrt(dot(a,a))
def unit(a):
    require(norm(a)>1e-12,'Zero vector/quaternion')
    return scale(a,1/norm(a))
def lerp(a,b,t): return add(scale(a,1-t),scale(b,t))
def cross(a,b): return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def conj(q): return [-q[0],-q[1],-q[2],q[3]]
def qmul(a,b):
    xyz=add(add(scale(b[:3],a[3]),scale(a[:3],b[3])),cross(a[:3],b[:3]))
    return xyz+[a[3]*b[3]-dot(a[:3],b[:3])]
def rotate(q,p): return add(p,scale(cross(q[:3],add(cross(q[:3],p),scale(p,q[3]))),2))
def qinterp(a,b,t,slerp=False):
    if dot(a,b)<0: b=scale(b,-1)
    cosine=max(-1.,min(1.,dot(a,b)))
    if not slerp or cosine>.9995: return unit(lerp(a,b,t))
    angle=math.acos(cosine)
    return unit(add(scale(a,math.sin((1-t)*angle)/math.sin(angle)),scale(b,math.sin(t*angle)/math.sin(angle))))


def transform(row):
    p=row.get('position',row.get('translation_cm'))
    q=row.get('quaternion_xyzw',row.get('rotation_xyzw'))
    s=row.get('scale',[1.,1.,1.])
    require(p is not None and q is not None and len(p)==3 and len(q)==4 and len(s)==3,'Malformed transform')
    require(all(isinstance(x,(int,float)) and math.isfinite(x) for x in (*p,*q,*s)),'Nonfinite transform')
    require(abs(norm(q)-1)<.001 and min(s)>0,'Invalid rotation/scale')
    return (p,unit(q),s)


IDENTITY=([0.,0.,0.],[0.,0.,0.,1.],[1.,1.,1.])
def point(t,p): return add(t[0],rotate(t[1],mul(t[2],p)))
def compose(parent,child):
    return point(parent,child[0]),unit(qmul(parent[1],child[1])),mul(parent[2],child[2])
def relative(parent,child):
    return (mul(rotate(conj(parent[1]),sub(child[0],parent[0])),[1/x for x in parent[2]]),
            unit(qmul(conj(parent[1]),child[1])),[a/b for a,b in zip(child[2],parent[2])])
def blend(a,b,t,slerp=False): return lerp(a[0],b[0],t),qinterp(a[1],b[1],t,slerp),lerp(a[2],b[2],t)
def distance(a,b):
    return (math.dist(a[0],b[0]),math.degrees(2*math.acos(min(1.,abs(dot(a[1],b[1]))))),max(abs(x-y) for x,y in zip(a[2],b[2])))
def asset(name): return DEST+name+'_Cm'


class Reference:
    def __init__(self):
        audit=read(AUDIT)
        require(audit['ok'] and audit['mode']=='readback' and audit['original_assets_unchanged'],'Native readback not accepted')
        pose_path=Path(audit['dense_native_pose_report']['path'])
        require(sha(pose_path)==audit['dense_native_pose_report']['sha256'],'Native readback pose hash changed')
        require(sha(CONTRACT)==audit['complete_contract_sha256'],'Accepted contract changed')
        require(sha(EXPECTATIONS)==audit['dense_expectations_sha256'],'CPU dense expectations changed')
        require(sha(HIERARCHY)==audit['native_reference_audit_sha256'],'Native reference skeleton changed')
        self.provenance={str(p):sha(p) for p in (AUDIT,pose_path,CONTRACT,HIERARCHY,EXPECTATIONS,LANDMARKS)}
        self.parent={r['name']:r['parent'] for r in read(HIERARCHY)['reference']['bones']}
        require(len(self.parent)==54,'Expected 54 native bones')
        raw=read(pose_path)
        self.poses={}
        self.times={}
        for name in TRACKS:
            rows=raw[asset(name)]
            self.times[name]=[r['seconds'] for r in rows]
            require(all(abs(t-i/30)<1e-6 for i,t in enumerate(self.times[name])),'Native 30 Hz sampling mismatch',name)
            local=[]
            for r in rows:
                component={n:transform(v) for n,v in r['bones'].items()}
                require(set(component)==set(self.parent),'Native bone identities changed')
                local.append({n:relative(component[self.parent[n]],v) if self.parent[n] in component else v for n,v in component.items()})
            self.poses[name]=local
        del raw
        core_path=BASE/'candidate-v11/runtime-integration-contract.json'
        branch_path=BASE/'decision-branch-contract.json'
        holster_path=BASE/'holster-v3/runtime-integration-contract.json'
        for p in (core_path,branch_path,holster_path):
            require(sha(p)==audit['source_provenance'][str(p)],'Authored source contract changed',p)
            self.provenance[str(p)]=sha(p)
        core,branches,holster=map(read,(core_path,branch_path,holster_path))
        self.published={'Full':core['dense_expected_native_samples']}
        self.published.update({r['name']:r['dense_expected_native_samples'] for r in branches['branch_sources']})
        self.published.update(holster['dense_expected_native_samples'])
        self.initial={r['pivot_name']:transform(r['initial_body_relative_transform']) for r in core['props']}
        self.initial['RifleHolster_Receiver']=transform(holster['prop']['body_relative_transform'])
        self.parked=transform(holster['dense_expected_native_samples']['Holster'][-1]['rifle_body_relative'])
        self.landmarks=read(LANDMARKS)
        self.soles=read(SOLES)
        self.provenance[str(SOLES)]=sha(SOLES)
        for p,h in self.landmarks['provenance'].items():
            require(sha(p)==h,'Landmark source or installed body changed',p)
            self.provenance[p]=h
        source=read(EXPECTATIONS)['reference']
        self.palm_local={}
        for side in ('Left','Right'):
            hand=transform(source[side+'Hand']['component_rest'])
            index=transform(source[side+'HandIndex1']['component_rest'])[0]
            pinky=transform(source[side+'HandPinky1']['component_rest'])[0]
            palm=lerp(hand[0],lerp(index,pinky,.5),.5)
            self.palm_local[side]=relative(hand,(palm,IDENTITY[1],IDENTITY[2]))[0]

    def bracket(self,name,seconds):
        times=self.times[name]
        require(math.isfinite(seconds) and -.00001<=seconds<=times[-1]+.00001,'Observed time outside accepted clip',name,seconds)
        seconds=max(0.,min(seconds,times[-1]))
        a=max(0,min(len(times)-1,bisect.bisect_right(times,seconds)-1));b=min(a+1,len(times)-1)
        return a,b,(seconds-times[a])/(times[b]-times[a]) if b!=a else 0.

    def pose(self,name,seconds):
        a,b,t=self.bracket(name,seconds)
        local={n:blend(self.poses[name][a][n],self.poses[name][b][n],t) for n in self.parent}
        result={}
        def build(n):
            if n not in result:
                p=self.parent[n]
                result[n]=compose(build(p),local[n]) if p in local else local[n]
            return result[n]
        for n in local: build(n)
        return result

    def prop_track(self,name,seconds):
        a,b,t=self.bracket(name,seconds)
        first,last=self.published[name][a],self.published[name][b]
        result=dict(self.initial)
        for n,v in first.get('props',{}).items():
            result[n]=blend(transform(v),transform(last['props'][n]),t,True)
        return result

    def expected_props(self,phase,name,seconds,selected):
        if phase in ('recover','unholster','complete'):
            result=self.prop_track('Full',seconds if phase=='recover' else 9.)
            if selected in (0,1,2):
                branch={0:'SortLeft',1:'Full',2:'SortRight'}[selected]
                final=self.prop_track(branch,184/30 if branch=='Full' else 2.)
                for n in result:
                    if n.startswith('AnonymousSalvageSample_'): result[n]=final[n]
            elif phase=='recover': raise ValueError('Recover without an accepted selection')
            elif selected==-1 or selected==-2:
                result=self.prop_track('SkipRecover',86/30)
            return result
        return self.prop_track(name,seconds)

    def rifle(self,name,seconds):
        if name not in ('Holster','Unholster'): return self.parked
        a,b,t=self.bracket(name,seconds)
        return blend(transform(self.published[name][a]['rifle_body_relative']),transform(self.published[name][b]['rifle_body_relative']),t,True)

    def palm(self,pose,side):
        wrist=pose[side+'Hand'][0]; middle=pose[side+'HandMiddle1'][0]; nextjoint=pose[side+'HandMiddle2'][0]
        along=unit(sub(middle,wrist)); bend=sub(nextjoint,middle)
        inward=unit(sub(bend,scale(along,dot(bend,along))))
        return add(lerp(wrist,middle,.58),scale(inward,.9))


class Auditor:
    def __init__(self,reference):
        self.ref=reference
        self.failures=[];self.failure_count=0;self.metrics={};self.rows=[]
        self.scenes={};self.coverage=collections.Counter();self.previous={};self.checked=0
        self.ground=[]

    def check(self,condition,label,**values):
        if not condition:
            self.failure_count+=1
            if len(self.failures)<80:self.failures.append(dict(row=self.checked,check=label,**values))

    def measure(self,label,value,limit,**context):
        if label not in self.metrics or value>self.metrics[label]['maximum']:
            self.metrics[label]={'maximum':value,'limit':limit,'row':self.checked,**context}
        self.check(math.isfinite(value) and value<=limit,label,value=value,limit=limit,**context)

    def compare(self,label,actual,expected,cm=.12,degrees=.2,**context):
        p,q,s=distance(actual,expected)
        self.measure(label+'_cm',p,cm,**context);self.measure(label+'_degrees',q,degrees,**context)
        self.measure(label+'_scale',s,.0005,**context)

    def observe(self,row):
        self.checked+=1
        p=row['playback'];phase=p['phase'];name=p['clip'];seconds=p['clip_seconds'];selected=p['selected_index']
        key=(p['match_id'],p['analysis_sequence'],p['performer_id'],p['performer_side'])
        self.check(bool(key[0]) and key[1]>0,'public_scene_identity')
        self.check(not p['error'],'playback_error',error=p['error'])
        archived=not p['active']
        manual=p['last_sample_unit_manual'] if archived else p['unit_manual']
        self.check(manual is not None,'manual_sample_present')
        if manual is None:return
        actual_phase=manual['phase']; self.coverage[(str(key),phase)]+=1
        if key not in self.scenes:self.scenes[key]={'phases':set(),'selected':set(),'frames':set(),'times':collections.defaultdict(list),'entry_full_pose_unverified':0}
        scene=self.scenes[key];scene['phases'].add(phase);scene['selected'].add(selected)
        scene['frames'].add(manual['sample_frame']);scene['times'][phase].append(seconds)
        self.check(manual['owned'],'sample_manual_owner_present')
        self.check(manual['sample_frame']==manual['body_bone_frame'],'same_frame_bone_evaluation',sample=manual['sample_frame'],bones=manual['body_bone_frame'])
        self.check(isinstance(manual['body_bone_revision'],int) and manual['body_bone_revision']>0,'bone_revision_present')
        self.measure('sample_clock_seconds',abs(seconds-manual['sample_seconds']),1e-5)
        self.check('OldWestManualAnimInstance' in manual['animation_instance'],'manual_animation_instance')
        self.check(manual['animation_asset'].split('.')[0]==asset(name)==p['clip_asset'].split('.')[0],'exact_clip_asset')
        self.check(not manual['animation_playing'] and manual['animation_rate']==0 and not manual['body_tick_enabled'],'single_manual_clock')
        self.check(not manual['dead'] and not manual['ragdoll'],'living_manual_performer')
        if key in self.previous:
            previous=self.previous[key]
            self.check(manual['sample_frame']>=previous[0] and p['sample_calls']>=previous[1],'monotonic_sample_identity')
            if manual['sample_frame']>previous[0]:self.check(manual['body_bone_revision']!=previous[2],'fresh_bone_revision')
        self.previous[key]=(manual['sample_frame'],p['sample_calls'],manual['body_bone_revision'])
        if archived:
            self.check(p['live_prop_count']==0 and p['retained_props_after_cleanup'] and not p['manual_pose_owned'],'cleanup_live_props_and_owner')
            self.check(not p['unit_manual']['owned'],'ordinary_unit_owner_restored')
            if p['complete'] and not p['unit_manual']['dead'] and not p['unit_manual']['ragdoll']:
                self.check('OldWestManualAnimInstance' not in p['unit_manual']['animation_instance'],'ordinary_animation_instance_restored')
        else:
            self.check(p['live_prop_count']==11 and not p['retained_props_after_cleanup'] and p['manual_pose_owned'],'eleven_live_props')
            self.check(phase==actual_phase,'sample_phase_identity',phase=phase,sample_phase=actual_phase)
        # Complete retains the final unholster sample; cancelled snapshots retain
        # their own last phase and must not be relabelled as successful return.
        phase=actual_phase if archived else phase
        mapping={'entry_blend':('Holster',0.),'holster':('Holster',0.),'inspect':('Full',0.),
                 'work_hold':('WorkHold',0.),'sort_left':('SortLeft',0.),'sort_middle':('Full',134/30),
                 'sort_right':('SortRight',0.),'recover':('Full',184/30),'skip_recover':('SkipRecover',0.),
                 'no_choice_recover':('SkipRecover',0.),'unholster':('Unholster',0.)}
        track,offset=mapping[phase]
        self.check(name==track,'phase_clip_contract',phase=phase,clip=name)
        if not archived:
            expected_seconds=0. if phase=='entry_blend' else p['phase_seconds']+offset
            self.measure('phase_clock_seconds',abs(seconds-expected_seconds),1e-5)
        contexts=[v for v in row['analysis'].get('active',[])+row['analysis'].get('history',[])
                  if v['analysis_sequence']==p['analysis_sequence']]
        self.check(len(contexts)==1,'one_public_analysis_context')
        context=contexts[0] if len(contexts)==1 else None
        if context:
            self.check(context['source']==p['performer_id'] and context['player']==p['performer_side'],'public_performer_identity')
            if selected>=-1:
                self.check(context['accepted'] and selected==(-1 if context['selection']=='skip' else context['reveal_index']),
                           'accepted_branch_identity')
        body=transform(manual['body']);rifle=transform(manual['weapon'])
        self.compare('body_snapshot_consistency',transform(p['last_sample_body'] if archived else p['body']),body,.02,.02)
        self.compare('rifle_snapshot_consistency',transform(p['last_sample_rifle'] if archived else p['rifle']),rifle,.02,.02)
        expected=self.ref.pose(name,seconds)
        self.check(set(manual['bones'])==set(BONES),'exact_eleven_bones')
        entry=phase=='entry_blend' and manual['entry_alpha']<.999999
        if entry:scene['entry_full_pose_unverified']+=1
        observed={n:transform(manual['bones'][n]['body_relative']) for n in BONES}
        observed_world={n:transform(manual['bones'][n]['world']) for n in BONES}
        for n in BONES:
            self.compare('bone_world_composition',observed_world[n],compose(body,observed[n]),.025,.025,bone=n)
            if not entry:
                self.compare('native_bone_local',observed[n],expected[n],bone=n)
                self.compare('native_bone_world',observed_world[n],compose(body,expected[n]),cm=.15,bone=n)
        if 'ground_probe' in manual:
            probe=manual['ground_probe']
            self.check(probe['read_only'] and probe['source_mesh_matches'],'ground_probe_exact_source_mesh')
            self.check(probe['source_landmarks_sha256']==sha(SOLES),'ground_probe_exact_source_vertices')
            self.check(probe['sample_frame']==manual['sample_frame']==probe['bone_frame']
                       and probe['query_frame']>=probe['sample_frame'],'ground_probe_sample_identity')
            known={(r['side'],r['object'],r['vertex']):r for r in self.ref.soles['points']}
            actual={(r['side'],r['source_object'],r['source_vertex']):r for r in probe['points']}
            self.check(len(actual)==len(probe['points'])==12 and set(actual)==set(known),'ground_probe_twelve_actual_vertices')
            sides=collections.defaultdict(list)
            for key,probe_point in actual.items():
                source_point=known[key];w=source_point['weights'][0]
                self.check(probe_point['bone_valid'] and probe_point['bone']==w['bone'],'ground_probe_actual_foot_bone')
                sole=point(observed_world[w['bone']],w['bone_local_cm'])
                self.measure('reported_source_sole_world_cm',math.dist(probe_point['sole_world'],sole),.01)
                self.measure('source_sole_trace_start_cm',math.dist(probe_point['trace_start'],add(sole,[0,0,150.])),.01)
                self.measure('source_sole_trace_end_cm',math.dist(probe_point['trace_end'],sub(sole,[0,0,150.])),.01)
                if probe_point['hit']:
                    height=sole[2]-probe_point['ground_world'][2]
                    self.measure('sole_reported_clearance_difference_cm',abs(height-probe_point['vertical_clearance_cm']),.01)
                    self.measure('sole_reported_normal_clearance_difference_cm',
                        abs(dot(sub(sole,probe_point['ground_world']),probe_point['normal'])-probe_point['normal_clearance_cm']),.01)
                    sides[key[0]].append({'clearance_cm':height,'surface_mesh':probe_point['surface_mesh'],
                                         'normal_z':probe_point['normal'][2]})
            for side,points in sides.items():
                terrain=[r for r in points if r['surface_mesh']=='/Game/Art/WaterDepotV2/Meshes/SM_ContinuousTerrain.SM_ContinuousTerrain']
                self.ground.append({'input_row':self.checked,'phase':phase,'clip_seconds':seconds,'side':side,
                    'sample_frame':probe['sample_frame'],'query_frame':probe['query_frame'],'hit_points':len(points),
                    'terrain_points':len(terrain),'surface_meshes':sorted({r['surface_mesh'] for r in points}),
                    'terrain_clearance_min_cm':min((r['clearance_cm'] for r in terrain),default=None),
                    'terrain_clearance_max_cm':max((r['clearance_cm'] for r in terrain),default=None)})
        if not entry:
            for side in ('Left','Right'):
                self.measure('native_palm_world_cm',math.dist(manual[side.lower()+'_palm_world'],point(body,self.ref.palm(expected,side))),.15,side=side)
            for landmark in self.ref.landmarks['points']:
                actual=[0.,0.,0.];wanted=[0.,0.,0.]
                for w in landmark['weights']:
                    actual=add(actual,scale(point(observed_world[w['bone']],w['bone_local_cm']),w['weight']))
                    wanted=add(wanted,scale(point(compose(body,expected[w['bone']]),w['bone_local_cm']),w['weight']))
                self.measure('source_skin_landmark_world_cm',math.dist(actual,wanted),.15,vertex=landmark['vertex'],side=landmark['side'])
        expected_props=self.ref.expected_props(phase,name,seconds,selected)
        props={v['name']:v for v in p['props']}
        self.check(len(p['props'])==len(props)==11 and set(props)==set(expected_props),'exact_eleven_prop_identities')
        for n,v in props.items():
            if context and v['sample_index']>=0:
                reveals={r['reveal_index']:r['target'] for r in context['reveals']}
                self.check(v['public_handle']==reveals.get(v['sample_index'],0)
                           and v['visible']==(v['sample_index'] in reveals),'public_sample_identity_and_visibility',prop=n)
            self.compare('prop_authored_local',transform(v['local']),expected_props[n],.025,.025,prop=n)
            self.compare('prop_authored_world',transform(v['world']),compose(body,expected_props[n]),.03,.03,prop=n)
            self.compare('prop_world_composition',transform(v['world']),compose(body,transform(v['local'])),.025,.025,prop=n)
        expected_rifle=self.ref.rifle(name,seconds)
        if not entry:self.compare('rifle_authored_body_relative',relative(body,rifle),expected_rifle,.03,.03)
        grip=point(rifle,[-1.8,-1.,-.7])
        self.measure('reported_grip_world_cm',math.dist(grip,manual['right_grip_world']),.01)
        gap=math.dist(grip,manual['right_palm_world'])
        self.measure('reported_grip_gap_difference_cm',abs(gap-manual['right_contact_gap_cm']),.01)
        held=phase=='entry_blend' or phase=='holster' and seconds<=64/30 or phase=='unholster' and seconds>=26/30
        self.check(held==manual['rifle_held']==manual['right_contact_required']==p['rifle_held'],'authored_rifle_hold_timing')
        if held:self.measure('held_right_palm_gap_cm',gap,.2)
        contacts={}
        for side in ('Left','Right'):
            palm=point(observed_world[side+'Hand'],self.ref.palm_local[side])
            expected_palm=point(compose(body,expected[side+'Hand']),self.ref.palm_local[side])
            prop='HandScanner_GripAnchor' if side=='Right' else 'AnonymousSalvageSample_'+str(selected+1) if selected in (0,1,2) else None
            if prop:
                # Authored hand anchor is intentionally distinct from the
                # runtime rifle palm. Retain actual offsets instead of asserting
                # that every released/approaching hand touches every prop.
                actual_offset=relative(transform(props[prop]['world']),(palm,IDENTITY[1],IDENTITY[2]))[0]
                wanted_offset=relative(compose(body,expected_props[prop]),(expected_palm,IDENTITY[1],IDENTITY[2]))[0]
                if not entry:self.measure('authored_hand_prop_offset_cm',math.dist(actual_offset,wanted_offset),.15,side=side,prop=prop)
                contacts[side]={'prop':prop,'authored_hand_anchor_world':palm,'prop_local_offset_cm':actual_offset}
        self.rows.append({'input_row':self.checked,'scene':list(key),'phase':phase,'archived':archived,'clip':name,'clip_seconds':seconds,
                          'sample_frame':manual['sample_frame'],'body_bone_revision':manual['body_bone_revision'],
                          'entry_full_pose_unverified':entry,'rifle_held':held,'actual_rifle_gap_cm':gap,'hand_contacts':contacts})

    def report(self):
        scenes=[]
        for key,s in self.scenes.items():
            scenes.append({'identity':list(key),'observed_phases':sorted(s['phases']),'observed_decisions':sorted(s['selected']),
                           'unique_manual_frames':len(s['frames']),'entry_blend_frames_without_full_expected_pose':s['entry_full_pose_unverified'],
                           'phase_observations':{p:{'count':len(t),'minimum_clip_seconds':min(t),'maximum_clip_seconds':max(t)} for p,t in s['times'].items()}})
        return {'schema':'oldwest.scientist.native-contact-audit.v1','ok':self.checked>0 and self.failure_count==0,
                'status':'observed-frame numerical comparison only','input_rows':self.checked,'compared_rows':len(self.rows),
                'failures_count':self.failure_count,'failures':self.failures,'maxima':self.metrics,'scenes':scenes,
                'ground_probe':{'observed_foot_samples':len(self.ground),
                    'stationary_work':{side:{'samples':len(v),
                        'minimum_sampled_sole_clearance_cm':min((r['terrain_clearance_min_cm'] for r in v),default=None),
                        'maximum_sampled_sole_clearance_cm':max((r['terrain_clearance_max_cm'] for r in v),default=None),
                        'all_six_points_hit_terrain':all(r['terrain_points']==6 for r in v)}
                        for side in ('Left','Right') for v in [[r for r in self.ground if r['side']==side and r['terrain_points']>0
                            and r['phase'] in ('inspect','work_hold','sort_left','sort_middle','sort_right','recover')]]},
                    'coverage':'Only explicit source-vertex queries; body/terrain correctness and whole sole contact are not inferred from pose agreement.'},
                'reference_provenance':self.ref.provenance,'auditor_sha256':sha(__file__),
                'methods':{'bones':'Native 30 Hz component poses converted to local, normalized shortest quaternion lerp, then parent-first FK.',
                           'props':'Independent accepted authoring contracts; position lerp and quaternion slerp, exact selected branch endpoints retained through Recover/Unholster.',
                           'skin':'32 actual exported source hand-skin vertices reconstructed by complete observed-bone LBS weights.',
                           'tick':'Manual sample_frame equals actual bone-transform frame; revision and sample identity checked for observed progression.'},
                'limitations':['Coverage is only the enumerated observed frames; no unobserved phase, endpoint or branch is claimed.',
                               'Entry blending prior 54-bone pose is not recorded; partial entry poses have internal transform/contact checks only.',
                               'No GPU vertex readback, cloth/collision test, finger-tip coverage, screenshots or visual-quality acceptance.',
                               'Native 30 Hz resampling approximates compressed codec interpolation between samples; fixed tolerances remain explicit.',
                               'Manual/body frame identity proves synchronous bone evaluation, not the time a screenshot was painted.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('samples',type=Path,nargs='+')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--rows-output',type=Path,help='Optional per-observed-frame contact points; report itself is bounded.')
    parser.add_argument('--brackets',type=Path,nargs='*',help='Optional complete capture brackets for actual Unit mesh and same-frame identity.')
    parser.add_argument('--scenario-results',type=Path,nargs='*',help='Optional retained completion from root legal-branch result.json files.')
    args=parser.parse_args()
    require(not args.output.exists(),'Preserve previous report',args.output)
    require(not args.rows_output or not args.rows_output.exists(),'Preserve previous per-frame evidence')
    ref=Reference();audit=Auditor(ref);inputs=[]
    for path in args.samples:
        # Read once: a live writer may append later, but cannot change the exact
        # byte prefix and row count actually compared by this invocation.
        data=path.read_bytes()
        inputs.append({'path':str(path.resolve()),'sha256':hashlib.sha256(data).hexdigest(),'bytes_observed':len(data)})
        for number,line in enumerate(data.decode().splitlines(),1):
            if not line.strip():continue
            try:audit.observe(json.loads(line))
            except (ValueError,KeyError,TypeError,IndexError,ZeroDivisionError) as error:
                audit.check(False,'malformed_or_unverifiable_observation',file=str(path),line=number,error=str(error))
    completions=[]
    for path in args.scenario_results or []:
        result=read(path);final=result['scientist_final']
        audit.observe({'playback':final['playback'],'analysis':{'active':[],'history':[final]}})
        completions.append({'path':str(path),'sha256':sha(path),'completion_reason':final['completion_reason']})
    brackets=[]
    for path in args.brackets or []:
        data=read(path)
        for when in ('before','after'):
            state=data[when]['cinematic']
            for p in state['scientist_analysis']['playbacks']:
                units=[u for u in state['units'] if u['id']==p['performer_id'] and u['side']==p['performer_side']]
                audit.check(len(units)==1,'capture_actual_performer',file=str(path),when=when)
                if len(units)!=1:continue
                u=units[0];m=u['manual_presentation'];pm=p['unit_manual']
                audit.check(u['card_id']=='prospector' and u['visual_mesh']=='/Game/Art/Survivors/Variants/SKM_Prospector_Cm.SKM_Prospector_Cm',
                            'capture_actual_landmark_mesh_identity',file=str(path),mesh=u['visual_mesh'])
                audit.check(m['sample_frame']==pm['sample_frame'] and m['body_bone_revision']==pm['body_bone_revision'],
                            'capture_actual_unit_sample_identity',file=str(path),when=when)
                brackets.append({'path':str(path),'sha256':sha(path),'when':when,'phase':p['phase'],
                                 'sample_frame':m['sample_frame'],'visual_mesh':u['visual_mesh']})
    report=audit.report();report['inputs']=inputs
    report['capture_mesh_identity']=brackets
    report['retained_completions']=completions
    report['capture_mesh_identity_verified']=bool(brackets) and not any(f['check'].startswith('capture_') for f in audit.failures)
    report['observed_input_files_unchanged_at_finish']=all(sha(p['path'])==p['sha256'] for p in inputs)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    if args.rows_output:
        args.rows_output.parent.mkdir(parents=True,exist_ok=True)
        args.rows_output.write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in audit.rows))
    print(json.dumps({'ok':report['ok'],'rows':audit.checked,'failures':audit.failure_count,'output':str(args.output)}))
    return 0 if report['ok'] else 1


if __name__=='__main__':raise SystemExit(main())
