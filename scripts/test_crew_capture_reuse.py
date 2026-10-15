"""A new attack must never certify stale rigs, textures or unrelated poses."""
import json
from pathlib import Path
import tempfile
import unittest
from crew_capture_reuse import BASELINE, audit_reuse, unmodified_captures
from crew_unreal_contract import sha


class ReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.out = Path(self.temp.name)
        (self.out / BASELINE).mkdir()
        self.save('rig-validation.json', {'project_sha256': 'rig'})
        self.assets = {'rig_project_sha256': 'rig', 'rig_validation_sha256': sha(self.out/'rig-validation.json'),
                       'approved_source_sha256': 'source', 'files': {'Crew/Animations/RA_MM_Attack_01.uasset': 'before',
                       'Crew/Animations/RA_MM_Idle.uasset': 'idle', 'Crew/SK_Person.uasset': 'mesh', 'Crew/Textures/T_Base.uasset': 'texture'}}
        self.save(BASELINE+'/unreal-assets.json', self.assets)
        records = []
        for clip, count in [('MF_Unarmed_Walk_Fwd',12),('MM_Idle',4),('MM_HitReact_Front_Lgt_01',4),('MM_Attack_01',4)]:
            for index in range(count):
                name = f'{clip}-{index}.png'
                (self.out/name).write_bytes(name.encode())
                records.append({'file':name, 'clip':clip, 'sha256':sha(self.out/name),
                                'pose_error':{'translation_cm':0,'quaternion_error':0,'time_seconds':0}})
        self.save(BASELINE+'/unreal-pose-captures.json', {'ok':True,'component_pose_verified':True,
                  'existing_content_unchanged':True,'unreal_assets_sha256':sha(self.out/BASELINE/'unreal-assets.json'),
                  'rig_project_sha256':'rig','rig_validation_sha256':self.assets['rig_validation_sha256'],'captures':records})
        self.assets['files']['Crew/Animations/RA_MM_Attack_01.uasset'] = 'after'
        self.save('unreal-assets.json', self.assets)

    def save(self, path, value):
        (self.out/path).write_text(json.dumps(value))

    def tearDown(self):
        self.temp.cleanup()

    def test_only_attack_reuses_twenty(self):
        records, proof = unmodified_captures(self.out)
        self.assertEqual(len(records),20)
        audit_reuse(self.out, {'captures':records,'reused_capture_evidence':proof})

    def test_changed_mesh_texture_or_nonattack_animation_rejected(self):
        for key in ('Crew/SK_Person.uasset','Crew/Textures/T_Base.uasset', 'Crew/Animations/RA_MM_Idle.uasset'):
            old = self.assets['files'][key]
            self.assets['files'][key] = 'changed'
            self.save('unreal-assets.json', self.assets)
            with self.assertRaises(AssertionError): unmodified_captures(self.out)
            self.assets['files'][key] = old

    def test_changed_capture_rejected(self):
        (self.out/'MM_Idle-0.png').write_bytes(b'changed')
        with self.assertRaises(AssertionError): unmodified_captures(self.out)

    def test_changed_rig_rejected(self):
        self.save('rig-validation.json', {'project_sha256':'new-rig'})
        with self.assertRaises(AssertionError): unmodified_captures(self.out)


if __name__ == '__main__':
    unittest.main()
