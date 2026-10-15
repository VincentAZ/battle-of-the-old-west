"""Regression checks against three previously inspected and accepted Native rigs."""
import json
from pathlib import Path
import random
import unittest
from crew_rig_mapping import infer_mapping, canonical_parents
ROOT=Path(__file__).resolve().parents[1]
FIXTURES=[ROOT/'art/western/native/quanah-game-v001', ROOT/'art/western/native/trio-animation-v001/lozen', ROOT/'art/western/native/trio-animation-v001/sarah-winnemucca']

class CrewMappingTest(unittest.TestCase):
    def test_matches_inspected_anatomy_without_names_order_or_unit_scale(self):
        for directory in FIXTURES:
            with self.subTest(character=directory.name):
                bones=json.loads((directory/'guide-bones.json').read_text())
                expected=json.loads((directory/'rig-validation.json').read_text())['bone_mapping']
                rename={b['name']:f'opaque_joint_{i:03d}' for i,b in enumerate(reversed(bones))}
                expected={rename[n]:v for n,v in expected.items()}
                for bone in bones:
                    bone['name']=rename[bone['name']]
                    bone['parent']=rename.get(bone['parent'])
                    for key in ('head','tail'):
                        bone[key]=[v*1.83+offset for v,offset in zip(bone[key],(-.75,.2,.1))]
                random.Random(27).shuffle(bones)
                self.assertEqual(infer_mapping(bones),expected)

    def test_ambiguous_finger_topology_fails(self):
        bones=json.loads((FIXTURES[0]/'guide-bones.json').read_text())
        bones=[b for b in bones if b['name']!='bone_43']
        with self.assertRaises(AssertionError):infer_mapping(bones)

    def test_target_hierarchy_has_all_53_bones_and_no_cycles(self):
        parents=canonical_parents()
        self.assertEqual(len(parents)+1,53)
        for name in parents:
            seen=set()
            while name!='root':
                self.assertNotIn(name,seen)
                seen.add(name);name=parents[name]

if __name__=='__main__':unittest.main()
