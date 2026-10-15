#!/usr/bin/env python3
"""Packaging contract regressions. All Unreal/ELF tools are mocked; no game launches."""
import copy
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import package_oldwest as package

PROJECT = package.ROOT/'game/OldWest/OldWest.uproject'
RAW = (PROJECT.parent/package.SCIENTIST_DATA).read_bytes()
DATA = json.loads(RAW)


class ScientistPackageTests(unittest.TestCase):
    def test_current_data_declares_every_asset(self):
        inventory = package.scientist_data_inventory(PROJECT)
        required, _ = package.source_inventory(PROJECT, inventory)
        self.assertEqual((inventory['prop_count'], inventory['track_count'], inventory['frame_count']), (11, 7, 723))
        self.assertEqual(len(inventory['required_packages']), 19)
        self.assertTrue(set(inventory['required_packages']) <= set(required))
        self.assertEqual(package.ufs_dependency_errors(PROJECT, ['Content/Data/cards.json', package.SCIENTIST_DATA]), [])

    def test_missing_and_duplicate_declarations_fail(self):
        for mutation in ('missing_prop', 'duplicate_name', 'duplicate_asset', 'duplicate_ordinal', 'missing_track'):
            data = copy.deepcopy(DATA)
            if mutation == 'missing_prop': data['props'].pop()
            elif mutation == 'duplicate_name': data['props'][1]['name'] = data['props'][0]['name']
            elif mutation == 'duplicate_asset': data['props'][1]['asset'] = data['props'][0]['asset']
            elif mutation == 'duplicate_ordinal': data['props'][0]['sample_index'] = 0
            else: data['tracks'].pop('Holster')
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                package.scientist_data_schema(data)

    def test_unsafe_or_wrong_asset_paths_fail(self):
        for bad in ('/Game/Art/Survivors/ScientistAnalysis/Props/../Other',
                    '/Game/Art/Survivors/ScientistAnalysis/Props/SM_One.SM_One',
                    '/Game/Art/Survivors/Other/SM_One', '/Engine/BasicShapes/Cube'):
            data = copy.deepcopy(DATA); data['props'][0]['asset'] = bad
            with self.subTest(path=bad), self.assertRaises(ValueError):
                package.scientist_data_schema(data)
        data = copy.deepcopy(DATA); data['tracks']['Full']['asset'] = data['tracks']['Holster']['asset']
        with self.assertRaises(ValueError): package.scientist_data_schema(data)

    def test_schema_clock_and_frame_count_fail(self):
        for mutation in ('schema', 'rig', 'count', 'clock', 'nan'):
            data = copy.deepcopy(DATA)
            if mutation == 'schema': data['schema'] = 'unknown.v2'
            elif mutation == 'rig': data['native_bones'] = 53
            elif mutation == 'count': data['tracks']['Full']['frames'].pop()
            elif mutation == 'clock': data['tracks']['Full']['frames'][2]['time'] = .1
            else: data['tracks']['Full']['seconds'] = float('nan')
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                package.scientist_data_schema(data)

    def test_ufs_must_be_on_the_matching_declaration_not_a_comment(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)/'OldWest.uproject'
            module = project.parent/'Source/OldWestGame/OldWestGame.Build.cs'
            module.parent.mkdir(parents=True)
            module.write_text('RuntimeDependencies.Add("$(ProjectDir)/Content/Data/cards.json", StagedFileType.UFS);\n'
                '// RuntimeDependencies.Add("$(ProjectDir)/Content/Data/scientist-presentation.json", StagedFileType.UFS);\n'
                'RuntimeDependencies.Add("$(ProjectDir)/Content/Data/scientist-presentation.json", StagedFileType.NonUFS);\n')
            errors = package.ufs_dependency_errors(project, ['Content/Data/cards.json', package.SCIENTIST_DATA])
            self.assertEqual(len(errors), 1)
            self.assertIn('scientist-presentation.json', errors[0])

    def fake_validation(self, directory, *, legacy=False, include_data=True, mutate_data=False,
                        omit_package=False, wrong_data_directory=False):
        root = Path(directory)/'package'
        binary = root/'OldWest/Binaries/Linux/OldWestGame'
        binary.parent.mkdir(parents=True); binary.write_bytes(b'fake-ELF'); binary.chmod(0o700)
        paks = root/'OldWest/Content/Paks'; paks.mkdir(parents=True)
        for ext in ('pak', 'utoc', 'ucas'): (paks/('OldWest-Linux.'+ext)).write_bytes(b'test-container')
        logs = Path(directory)/'logs'; logs.mkdir()
        catalog = PROJECT.parent/'Content/Data/cards.json'
        scientist = package.scientist_data_inventory(PROJECT)
        plan = dict(catalog_sha256=package.digest(catalog), required_packages=[], cook_roots={}, bundled_files=[])
        if not legacy:
            plan.update(scientist_presentation=scientist, required_packages=scientist['required_packages'])
        calls = []
        def tool(argv, log, cwd, **kwargs):
            calls.append(argv)
            if argv[0] == 'readelf': return 'ELF64 X86-64'
            if argv[0] == 'ldd': return 'dependencies available'
            if '-List' in argv:
                return '"../../../OldWest/Content/Data/cards.json"\n' + (
                    '"../../../OldWest/Content/Data/scientist-presentation.json"' if include_data else '')
            csv_arg = next((a for a in argv if a.startswith('-Csv=')), None)
            if csv_arg:
                required = plan['required_packages'][:-1] if omit_package else plan['required_packages']
                Path(csv_arg.split('=', 1)[1]).write_text('PackageName\n'+'\n'.join(required)+'\n')
                return ''
            if '-Extract' in argv:
                alias = Path(argv[1])
                self.assertTrue(alias.is_symlink())
                self.assertEqual(alias.resolve(), paks/'OldWest-Linux.pak')
                self.assertTrue((alias.parent.parent/('input\\'+alias.name)).is_symlink())
                destination = Path(argv[argv.index('-Extract')+1])
                scientific = '-Filter=*scientist-presentation.json' in argv
                parent = destination/('Other' if scientific and wrong_data_directory else 'OldWest')/'Content/Data'
                parent.mkdir(parents=True)
                (parent/('scientist-presentation.json' if scientific else 'cards.json')).write_bytes(
                    RAW + (b' ' if mutate_data else b'') if scientific else catalog.read_bytes())
                return ''
            raise AssertionError(argv)
        args = SimpleNamespace(project=PROJECT, engine=Path(directory)/'engine')
        with patch.object(package, 'run_logged', side_effect=tool):
            result = package.validate(args, root, plan, logs)
        self.assertFalse(list(logs.glob('pak-extract-*')), 'Temporary extraction aliases leaked')
        return result, calls

    def test_packaged_data_is_extracted_and_verified_from_actual_pak_argument(self):
        with tempfile.TemporaryDirectory() as directory:
            result, calls = self.fake_validation(directory)
        self.assertTrue(result['scientist_presentation']['verified'])
        self.assertEqual(result['scientist_presentation']['status'], 'verified_from_pak')
        self.assertTrue(any('-Filter=*scientist-presentation.json' in call for call in calls))

    def test_old_recorded_plan_does_not_require_or_extract_new_data(self):
        with tempfile.TemporaryDirectory() as directory:
            result, calls = self.fake_validation(directory, legacy=True, include_data=False)
        self.assertTrue(result['ok'])
        self.assertFalse(result['scientist_presentation']['verified'])
        self.assertEqual(result['scientist_presentation']['status'], 'not_required_by_legacy_plan')
        self.assertFalse(any('-Filter=*scientist-presentation.json' in call for call in calls))

    def test_missing_packaged_scientist_json_fails(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(ValueError, 'could not be extracted'):
            self.fake_validation(directory, include_data=False)

    def test_one_byte_change_in_packaged_json_fails(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(ValueError, 'build-start SHA'):
            self.fake_validation(directory, mutate_data=True)

    def test_json_under_wrong_runtime_directory_fails(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(ValueError, 'could not be extracted'):
            self.fake_validation(directory, wrong_data_directory=True)

    def test_missing_declared_cooked_asset_fails(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(ValueError, 'Required cooked packages are absent'):
            self.fake_validation(directory, omit_package=True)

    def test_invalid_new_plan_cannot_downgrade_to_legacy(self):
        with self.assertRaisesRegex(ValueError, 'no valid source SHA'):
            package.verify_extracted_scientist({'scientist_presentation': None}, [])

    def test_existing_extract_directory_cannot_supply_stale_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            logs = Path(directory); (logs/'scientist-extract-0').mkdir()
            with patch.object(package, 'run_logged') as tool, self.assertRaises(FileExistsError):
                package.extract_pak_json(Path('UnrealPak'), Path('file.pak'), logs, logs, 0,
                                         'prospector', 'scientist-presentation.json', 'OldWest')
            tool.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
