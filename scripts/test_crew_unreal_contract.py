"""Import gates reject tampered assets and unsafe destinations without Unreal."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import crew_unreal_contract as contract


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.base = self.root/'art/western/crew/playable-v001'
        self.base.mkdir(parents=True)
        self.patches = [patch.object(contract, 'ROOT', self.root), patch.object(contract, 'BASE', self.base)]
        for p in self.patches:
            p.start()
        self.records = {}
        for i, slug in enumerate(sorted(contract.NATIVE) + ['person-'+str(n) for n in range(43)]):
            source = self.root/'art/western'/slug/'review.blend'
            source.parent.mkdir()
            source.write_bytes(('approved-'+slug).encode())
            self.records[slug] = {'path': str(source.relative_to(self.root)), 'sha256': contract.sha(source),
                                 'asset_name': 'Person'+str(i), 'copies': [{'canonical_card_id': 'card'+str(i), 'copy': 1}]}
        self.manifest = {'characters': self.records, 'approval': 'art/western/crew/approval.json',
                         'reuse_existing_playable': sorted(contract.NATIVE)}
        self.write_manifest()
        self.slug = 'person-0'
        record = self.records[self.slug]
        self.out = self.base/self.slug
        exports = self.out/'exports'
        exports.mkdir(parents=True)
        name = record['asset_name']
        project = self.out/(name+'-Rigged.blend')
        project.write_bytes(b'rigged')
        for filename in ['SK_'+name+'.fbx'] + ['T_'+name+'_'+c+'.png' for c in ('BaseColor', 'ORM', 'Normal')]:
            (exports/filename).write_bytes(filename.encode())
        self.validation = {'status': 'passed', 'source_project_sha256': record['sha256'], 'project_sha256': contract.sha(project),
                           'files': {p.name: contract.sha(p) for p in exports.iterdir()}, 'bind_pose_max_error_m': 0,
                           'maximum_vertex_influences': 4, 'source_geometry_uv_sha256': 'geometry', 'freeze_bones': sorted(contract.FINGER_BONES)}
        self.write_validation()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def write_manifest(self):
        (self.base/'manifest.json').write_text(json.dumps(self.manifest))
        (self.root/self.manifest['approval']).write_text(json.dumps({'projects': self.records,
            'rigging_authorized': True, 'animation_and_game_integration_authorized': True}))

    def write_validation(self):
        (self.out/'rig-validation.json').write_text(json.dumps(self.validation))

    def test_valid_import_and_native_refusal(self):
        self.assertTrue(contract.character(self.slug)['dest'].startswith('/Game/Art/Western/Crew/'))
        with self.assertRaisesRegex(AssertionError, 'Native'):
            contract.character('lozen')

    def test_modified_approved_source_rejected(self):
        (self.root/self.records[self.slug]['path']).write_bytes(b'modified')
        with self.assertRaisesRegex(AssertionError, 'Approved source changed'):
            contract.load_manifest()

    def test_duplicate_destination_and_copy_rejected(self):
        other = 'person-1'
        self.records[other]['asset_name'] = self.records[self.slug]['asset_name']
        self.write_manifest()
        with self.assertRaisesRegex(AssertionError, 'Duplicate destination'):
            contract.load_manifest()
        self.records[other]['asset_name'] = 'UniqueName'
        self.records[other]['copies'] = copy.deepcopy(self.records[self.slug]['copies'])
        self.write_manifest()
        with self.assertRaisesRegex(AssertionError, 'Reused physical copy'):
            contract.load_manifest()

    def test_tampered_export_and_path_escape_rejected(self):
        filename = next(iter(self.validation['files']))
        (self.out/'exports'/filename).write_bytes(b'tampered')
        with self.assertRaisesRegex(AssertionError, 'Export checksum mismatch'):
            contract.character(self.slug)
        self.validation['files'] = {'../escape': 'hash', **self.validation['files']}
        self.write_validation()
        with self.assertRaisesRegex(AssertionError, 'basename'):
            contract.character(self.slug)

    def test_unpassed_or_different_source_rig_rejected(self):
        self.validation['status'] = 'pending'
        self.write_validation()
        with self.assertRaisesRegex(AssertionError, 'has not passed'):
            contract.character(self.slug)
        self.validation['status'] = 'passed'
        self.validation['source_project_sha256'] = 'unapproved'
        self.write_validation()
        with self.assertRaisesRegex(AssertionError, 'unapproved source'):
            contract.character(self.slug)

    def test_missing_finger_policy_rejected(self):
        self.validation['freeze_bones'] = []
        self.write_validation()
        with self.assertRaisesRegex(AssertionError, 'bind-finger policy'):
            contract.character(self.slug)

    def test_invalid_bind_pose_rejected(self):
        self.validation['bind_pose_max_error_m'] = 1
        self.write_validation()
        with self.assertRaisesRegex(AssertionError, 'Bind pose'):
            contract.character(self.slug)


if __name__ == '__main__':
    unittest.main()
