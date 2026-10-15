"""CPU regressions for rejecting damaged/import-incompatible bundle contracts."""
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scientist_import_contract as subject


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = subject.load_bundle()
        cls.top = subject.read(subject.CONTRACT)
        cls.dense = subject.read(subject.EXPECTATIONS)

    def corrupted(self,path,mutate,pattern):
        value = copy.deepcopy(subject.read(path))
        mutate(value)
        original_read = subject.read
        with patch.object(subject,'read',side_effect=lambda p:value if Path(p) == path else original_read(p)):
            with self.assertRaisesRegex(ValueError,pattern):
                subject.load_bundle()

    def test_complete_coverage(self):
        self.assertEqual(len(self.bundle['clips']),13)
        self.assertEqual(len(self.bundle['props']),11)
        self.assertEqual(len(self.bundle['materials']),10)
        self.assertEqual(sum(len(v) for v in self.dense['clips'].values()),994)
        self.assertEqual(len(self.bundle['endpoints']),12)

    def test_reject_fbx_hash(self):
        self.corrupted(subject.CONTRACT,lambda d:d['animations'][0].update(source_fbx_sha256='0'*64),'Source hash changed')

    def test_reject_destination_escape(self):
        self.corrupted(subject.CONTRACT,lambda d:d['animations'][0].update(asset='/Game/OriginalAsset'),'Unexpected clip destination')

    def test_reject_source_escape(self):
        self.corrupted(subject.CONTRACT,lambda d:d['animations'][0].update(source_fbx='/tmp/outside.fbx'),'Source escapes')

    def test_reject_duration_drift(self):
        self.corrupted(subject.CONTRACT,lambda d:d['animations'][0].update(seconds=8.8),'duration mismatch')

    def test_reject_wrong_subcontract(self):
        self.corrupted(subject.CONTRACT,lambda d:d['animations'][0].update(expected_contract='art/characters/scientist_gesture/decision-branch-contract.json'),'Wrong clip expected contract')

    def test_reject_missing_prop(self):
        self.corrupted(subject.CONTRACT,lambda d:d['static_props'].pop(),'Expected 11 props')

    def test_reject_wrong_material_slot(self):
        self.corrupted(subject.CONTRACT,lambda d:d['static_props'][0]['material_slots'].append('M_Unreviewed'),'Invalid material slots')

    def test_reject_missing_dense_frame(self):
        self.corrupted(subject.EXPECTATIONS,lambda d:next(iter(d['clips'].values())).pop(),'Dense frame coverage')

    def test_reject_missing_bone(self):
        self.corrupted(subject.EXPECTATIONS,lambda d:next(iter(d['clips'].values()))[0]['bones'].pop('LeftHand'),'Dense bone set')

    def test_reject_coordinate_scale(self):
        self.corrupted(subject.EXPECTATIONS,lambda d:next(iter(d['clips'].values()))[0]['bones']['root'].update(scale=[100,100,100]),'Unexpected authored scale')

    def test_reject_native_position_drift(self):
        self.corrupted(subject.EXPECTATIONS,lambda d:next(iter(d['clips'].values()))[0]['bones']['LeftHand'].update(translation_cm=[0,0,0]),'Dense/published pose mismatch')

    def test_reject_endpoint_gap(self):
        clips = copy.deepcopy(self.dense['clips'])
        clips[subject.DEST+'/Animations/A_Scientist_SortLeft_Cm'][-1]['bones']['RightHand']['translation_cm'][0] += 1
        with self.assertRaisesRegex(ValueError,'Endpoint discontinuity'):
            subject.endpoint_checks(clips)

    def test_all_53_not_only_contact_bones(self):
        clips = copy.deepcopy(self.dense['clips'])
        clips[subject.DEST+'/Animations/A_Scientist_Unholster_Cm'][0]['bones']['LeftHandRing3']['translation_cm'][0] += 1
        with self.assertRaisesRegex(ValueError,'Endpoint discontinuity'):
            subject.endpoint_checks(clips)


if __name__ == '__main__':
    unittest.main()
