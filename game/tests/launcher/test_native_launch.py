"""Launcher routing regressions; these stubs do not validate Unreal runtime."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'scripts'))
from native_launch import game_net_driver_ports, resolve_native_launch


class NativeLaunchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='oldwest-launcher-test-')
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.project = ROOT/'game/OldWest/OldWest.uproject'
        self.editor = Path('/test/UnrealEditor')

    def package(self, name='relocated game with spaces'):
        root = self.folder/name
        (root/'OldWest/Binaries/Linux').mkdir(parents=True)
        return root

    def launcher(self, root):
        script = root/'launch_battle_of_the_old_west.sh'
        script.write_text('#!/usr/bin/env python3\nimport os,sys,json\n'
            'print(json.dumps({"argv":sys.argv[1:],"cwd":os.getcwd(),'
            '"override":os.getenv("OLDWEST_BINARY"),"sentinel":os.getenv("OLDWEST_TEST_SENTINEL")}))\n')
        script.chmod(0o755)
        return script

    def test_editor_command_and_cwd_unchanged(self):
        launch = resolve_native_launch(self.editor, self.project, editor_directory=ROOT)
        self.assertEqual(launch.argv, [str(self.editor), str(self.project)])
        self.assertEqual(launch.cwd, ROOT)
        self.assertIsNone(launch.env)
        self.assertIsNone(launch.package_root)

    def test_relocated_bundled_launcher_executes_from_isolated_directory(self):
        root = self.package()
        script = self.launcher(root)
        run = self.folder/'isolated run with spaces'
        run.mkdir()
        with patch.dict(os.environ, {'OLDWEST_BINARY': '/wrong/binary', 'OLDWEST_PACKAGE_DIR': '/wrong/package',
                                    'OLDWEST_TEST_SENTINEL': 'preserved'}):
            launch = resolve_native_launch(self.editor, self.project, root, run_directory=run)
        result = subprocess.run(launch.argv+['argument with spaces'], cwd=launch.cwd, env=launch.env,
                                text=True, stdout=subprocess.PIPE, check=True)
        observed = json.loads(result.stdout)
        self.assertEqual(launch.argv[0], str(script))
        self.assertEqual(observed['argv'], ['--package-dir', str(root), '--', 'argument with spaces'])
        self.assertEqual(observed['cwd'], str(run))
        self.assertIsNone(observed['override'])
        self.assertEqual(observed['sentinel'], 'preserved')

    def test_archive_parent_discovers_linux_package(self):
        root = self.package('archive/Linux')
        self.launcher(root)
        launch = resolve_native_launch(self.editor, self.project, root.parent)
        self.assertEqual(launch.package_root, root)
        self.assertEqual(launch.cwd, root)

    def test_missing_bundled_launcher_cannot_fall_back_to_repo(self):
        root = self.package()
        with self.assertRaisesRegex(FileNotFoundError, 'source-tree fallback is disabled'):
            resolve_native_launch(self.editor, self.project, root)

    def test_nonexecutable_launcher_rejected(self):
        root = self.package()
        script = self.launcher(root)
        script.chmod(0o644)
        with self.assertRaises(PermissionError):
            resolve_native_launch(self.editor, self.project, root)

    def test_external_launcher_symlink_rejected(self):
        root = self.package()
        external = self.folder/'external.sh'
        external.write_text('#!/bin/sh\nexit 0\n')
        external.chmod(0o755)
        (root/'launch_battle_of_the_old_west.sh').symlink_to(external)
        with self.assertRaisesRegex(ValueError, 'outside its package'):
            resolve_native_launch(self.editor, self.project, root)

    def test_trace_and_other_driver_listeners_do_not_signal_readiness(self):
        trace = 'LogTrace: Display: Control listening on port 19471\n'
        other = 'LogNet: Name:BeaconNetDriver Def:GameNetDriver IpNetDriver listening on port 19471\n'
        game = '[time]LogNet: Name:GameNetDriver Def:GameNetDriver IpNetDriver_0 IpNetDriver listening on port 19471\n'
        self.assertEqual(game_net_driver_ports(trace+other), [])
        self.assertEqual(game_net_driver_ports(trace+other+game), [19471])


if __name__ == '__main__':
    unittest.main()
