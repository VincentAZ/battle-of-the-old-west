"""Adversarial CPU checks; synthetic telemetry is never native-play evidence."""
import copy
import json
import math
import unittest

import audit_scientist_native_contacts as A


def json_transform(t):
    return {'position':list(t[0]),'quaternion_xyzw':list(t[1]),'scale':list(t[2])}


class ContactAuditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref=A.Reference()
        cls.raw=A.read(A.AUDIT)
        cls.raw=A.read(cls.raw['dense_native_pose_report']['path'])

    def fixture(self,phase='inspect',seconds=3.,selected=-2):
        names={'inspect':'Full','holster':'Holster','sort_left':'SortLeft','sort_middle':'Full',
               'sort_right':'SortRight','recover':'Full','skip_recover':'SkipRecover','unholster':'Unholster','work_hold':'WorkHold'}
        name=names[phase]
        # Positive fixtures use independently retained actual imported 30 Hz
        # component samples, not the auditor's interpolation implementation.
        source=self.raw[A.asset(name)][round(seconds*30)]['bones']
        pose={n:A.transform(v) for n,v in source.items()}
        angle=.73;body=([120.,-640.,17.],[0.,0.,math.sin(angle/2),math.cos(angle/2)],[1.,1.,1.])
        local_rifle=self.ref.rifle(name,seconds);rifle=A.compose(body,local_rifle)
        held=phase=='holster' and seconds<=64/30 or phase=='unholster' and seconds>=26/30
        palm=A.point(body,self.ref.palm(pose,'Right'));grip=A.point(rifle,[-1.8,-1.,-.7])
        manual={'owned':True,'phase':phase,'rifle_held':held,'sample_frame':100,'sample_seconds':seconds,
                'entry_alpha':1.,'body_bone_frame':100,'body_bone_revision':102,'body_tick_enabled':False,
                'animation_instance':'OldWestManualAnimInstance','animation_asset':A.asset(name)+'.A_Scientist_'+name+'_Cm',
                'animation_playing':False,'animation_rate':0.,'dead':False,'ragdoll':False,
                'body':json_transform(body),'weapon':json_transform(rifle),
                'right_palm_world':palm,'left_palm_world':A.point(body,self.ref.palm(pose,'Left')),
                'right_grip_world':grip,'right_contact_gap_cm':math.dist(palm,grip),'right_contact_required':held,
                'bones':{n:{'body_relative':json_transform(pose[n]),'world':json_transform(A.compose(body,pose[n]))} for n in A.BONES}}
        props=self.ref.expected_props(phase,name,seconds,selected)
        props=[{'name':n,'local':json_transform(t),'world':json_transform(A.compose(body,t)),'visible':True,
                'sample_index':int(n[-1])-1 if n.startswith('AnonymousSalvageSample_') else -1,
                'public_handle':200+int(n[-1]) if n.startswith('AnonymousSalvageSample_') else 0} for n,t in props.items()]
        p={'active':True,'complete':False,'phase':phase,'clip':name,'clip_seconds':seconds,'selected_index':selected,
           'match_id':'synthetic-never-native','analysis_sequence':24,'performer_id':81,'performer_side':0,'sample_calls':1,
           'error':'','unit_manual':manual,'clip_asset':manual['animation_asset'],'live_prop_count':11,
           'retained_props_after_cleanup':False,'manual_pose_owned':True,'body':json_transform(body),
           'rifle':json_transform(rifle),'rifle_held':held,'props':props,
           'phase_seconds':seconds-({'sort_middle':134/30,'recover':184/30}.get(phase,0.))}
        context={'analysis_sequence':24,'source':81,'player':0,'accepted':selected>=-1,
                 'selection':'skip' if selected==-1 else 'selected','reveal_index':selected,
                 'reveals':[{'reveal_index':i,'target':201+i} for i in range(3)]}
        return {'playback':p,'analysis':{'active':[context],'history':[]}}

    def audit(self,rows):
        audit=A.Auditor(self.ref)
        for row in rows:audit.observe(row)
        return audit.report()

    def test_actual_readback_integer_frames(self):
        for phase,time,choice in [('inspect',3.,-2),('work_hold',1.,-2),('holster',1.,-2),
            ('sort_left',1.,0),('sort_middle',5.,1),('sort_right',1.,2),('skip_recover',2.,-1),
            ('recover',7.,0),('recover',7.,1),('recover',7.,2),('unholster',2.,0),('unholster',2.,2),('unholster',2.,-1)]:
            with self.subTest(phase=phase,choice=choice):
                report=self.audit([self.fixture(phase,time,choice)])
                self.assertTrue(report['ok'],report['failures'][:3])

    def test_local_fk_interpolation_not_component_lerp(self):
        # A right-angle rotation at a parent moves a unit child on an arc.
        parent=A.blend(A.IDENTITY,([0,0,0],[0,0,1,0],[1,1,1]),.5)
        child=A.compose(parent,([1,0,0],[0,0,0,1],[1,1,1]))
        self.assertLess(math.dist(child[0],[0,1,0]),1e-12)
        self.assertGreater(math.dist(child[0],A.lerp([1,0,0],[-1,0,0],.5)),.99)

    def test_quaternion_sign_and_body_composition(self):
        row=self.fixture()
        for bone in row['playback']['unit_manual']['bones'].values():
            bone['world']['quaternion_xyzw']=[-q for q in bone['world']['quaternion_xyzw']]
        self.assertTrue(self.audit([row])['ok'])

    def test_rejects_wrong_bone_pose(self):
        row=self.fixture();row['playback']['unit_manual']['bones']['LeftHand']['body_relative']['position'][0]+=3
        self.assertFalse(self.audit([row])['ok'])

    def test_rejects_stale_evaluated_frame(self):
        row=self.fixture();row['playback']['unit_manual']['body_bone_frame']-=1
        self.assertFalse(self.audit([row])['ok'])

    def test_rejects_stale_revision_on_new_frame(self):
        a=self.fixture();b=copy.deepcopy(a);m=b['playback']['unit_manual'];m['sample_frame']+=1;m['body_bone_frame']+=1
        b['playback']['sample_calls']+=1
        self.assertFalse(self.audit([a,b])['ok'])

    def test_rejects_world_local_mismatch(self):
        row=self.fixture();row['playback']['props'][0]['world']['position'][2]+=1
        self.assertFalse(self.audit([row])['ok'])

    def test_rejects_middle_sample_replayed_during_left_recover(self):
        row=self.fixture('recover',7.,0);body=A.transform(row['playback']['body'])
        wrong=self.ref.prop_track('Full',7.)
        for prop in row['playback']['props']:
            if prop['name'].startswith('AnonymousSalvageSample_'):
                prop['local']=json_transform(wrong[prop['name']]);prop['world']=json_transform(A.compose(body,wrong[prop['name']]))
        self.assertFalse(self.audit([row])['ok'])

    def test_rejects_unholster_selection_reset(self):
        row=self.fixture('unholster',2.,2);body=A.transform(row['playback']['body'])
        for prop in row['playback']['props']:
            if prop['name'].startswith('AnonymousSalvageSample_'):
                prop['local']=json_transform(self.ref.initial[prop['name']]);prop['world']=json_transform(A.compose(body,self.ref.initial[prop['name']]))
        self.assertFalse(self.audit([row])['ok'])

    def test_rejects_wrong_public_sample_identity(self):
        row=self.fixture();row['playback']['props'][-2]['public_handle']=999
        self.assertFalse(self.audit([row])['ok'])

    def test_rejects_reported_grip_tautology(self):
        row=self.fixture('holster',1.);m=row['playback']['unit_manual']
        m['right_contact_gap_cm']=0.;m['right_grip_world']=[0,0,0]
        self.assertFalse(self.audit([row])['ok'])

    def test_rejects_wrong_phase_track(self):
        row=self.fixture();row['playback']['phase']='work_hold';row['playback']['unit_manual']['phase']='work_hold'
        self.assertFalse(self.audit([row])['ok'])

    def test_empty_evidence_is_not_pass(self):
        self.assertFalse(self.audit([])['ok'])

    def ground_fixture(self):
        row=self.fixture();manual=row['playback']['unit_manual'];points=[]
        for p in self.ref.soles['points']:
            w=p['weights'][0];sole=A.point(A.transform(manual['bones'][w['bone']]['world']),w['bone_local_cm'])
            points.append({'side':p['side'],'source_object':p['object'],'source_vertex':p['vertex'],
                'bone':w['bone'],'bone_valid':True,'sole_world':sole,'trace_start':A.add(sole,[0,0,150.]),
                'trace_end':A.sub(sole,[0,0,150.]),'hit':True,'ground_world':A.sub(sole,[0,0,1.]),
                'normal':[0,0,1.],'vertical_clearance_cm':1.,'normal_clearance_cm':1.,
                'surface_mesh':'/Game/Art/WaterDepotV2/Meshes/SM_ContinuousTerrain.SM_ContinuousTerrain'})
        manual['ground_probe']={'read_only':True,'source_mesh_matches':True,'source_landmarks_sha256':A.sha(A.SOLES),
            'sample_frame':100,'bone_frame':100,'query_frame':101,'points':points}
        return row

    def test_actual_sole_landmarks_and_reported_trace_distances(self):
        row=self.ground_fixture();report=self.audit([row])
        self.assertTrue(report['ok'],report['failures'])
        self.assertEqual(report['ground_probe']['stationary_work']['Left']['minimum_sampled_sole_clearance_cm'],1.)
        row['playback']['unit_manual']['ground_probe']['points'][0]['vertical_clearance_cm']=0.
        self.assertFalse(self.audit([row])['ok'])

    def test_obstacle_hit_is_not_claimed_as_terrain(self):
        row=self.ground_fixture()
        for p in row['playback']['unit_manual']['ground_probe']['points']:p['surface_mesh']='/Game/Props/Box.Box'
        report=self.audit([row])
        self.assertTrue(report['ok']) # Correct telemetry; terrain coverage remains explicitly absent.
        self.assertEqual(report['ground_probe']['stationary_work']['Left']['samples'],0)
        self.assertIsNone(report['ground_probe']['stationary_work']['Left']['minimum_sampled_sole_clearance_cm'])


if __name__=='__main__':unittest.main()
