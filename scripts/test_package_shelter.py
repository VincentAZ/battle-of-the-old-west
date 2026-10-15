#!/usr/bin/env python3
"""CPU-only shelter inventory regressions; no Unreal process or Content writes."""
import json
from pathlib import Path
import tempfile
import unittest

import package_oldwest as package


class ShelterPackageTests(unittest.TestCase):
    def test_exact_exported_eleven_packages_are_declared(self):
        contract = json.loads((package.ROOT/'art/camps/realism/shelter-study/export-contract-v2.json').read_text())
        expected = {'/Game/Art/Camps/ShelterStudy/Meshes/'+s['name'] for s in contract['assets']}
        self.assertEqual(len(expected),11)
        self.assertEqual(len(package.SHELTER_PACKAGES),11)
        self.assertEqual(set(package.SHELTER_PACKAGES),expected)

    def test_missing_source_mesh_remains_a_required_package(self):
        with tempfile.TemporaryDirectory(prefix='oldwest-shelter-inventory-') as directory:
            project = Path(directory)/'OldWest.uproject'
            project.write_text('{}')
            missing = package.SHELTER_PACKAGES[-1]
            for asset in package.SHELTER_PACKAGES[:-1]:
                path = project.parent/'Content'/(asset.removeprefix('/Game/')+'.uasset')
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(b'CPU fixture only')
            required,_ = package.source_inventory(project,{'required_packages':[]})
            self.assertIn(missing,required)
            absent = [asset for asset in package.SHELTER_PACKAGES if not
                (project.parent/'Content'/(asset.removeprefix('/Game/')+'.uasset')).exists()]
            self.assertEqual(absent,[missing])
            self.assertTrue(set(package.SHELTER_PACKAGES) <= set(required))

    def test_all_unimported_sources_are_still_required(self):
        with tempfile.TemporaryDirectory(prefix='oldwest-shelter-empty-') as directory:
            required,_ = package.source_inventory(Path(directory)/'OldWest.uproject',{'required_packages':[]})
            self.assertTrue(set(package.SHELTER_PACKAGES) <= set(required))
            self.assertEqual(len(required),len(set(required)))


if __name__ == '__main__':
    unittest.main(verbosity=2)
