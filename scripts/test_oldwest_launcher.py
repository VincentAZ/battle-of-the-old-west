#!/usr/bin/env python3
"""Launch the repository's default package and verify its actual process image."""
import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from native_launch import stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets

ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--expected-package',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    expected=args.expected_package.resolve()/'OldWest/Binaries/Linux/OldWestGame'
    report=out/'game.json';control=out/'game.control.json'
    env={k:v for k,v in os.environ.items() if k not in {'OLDWEST_PACKAGE_DIR','OLDWEST_PACKAGE_ROOT','OLDWEST_BINARY','OLDWEST_PROJECT_NAME','OLDWEST_TARGET_NAME'}}
    console=(out/'console.log').open('w')
    process=subprocess.Popen([str(ROOT/'scripts/launch_battle_of_the_old_west.sh'),'-RenderOffscreen','-windowed','-ForceRes','-ResX=1280','-ResY=720',
        '-OldWestLifecycleTest','-OldWestVisualTest',f'-OldWestLifecycleReport={report}',f'-OldWestLifecycleControl={control}',
        f'-OldWestProfileRoot={out}/profiles',f'-GameUserSettingsINI={out}/settings.ini',f'-abslog={out}/game.log',
        '-nosound','-unattended','-nosplash','-NoLiveCoding','-stdout'],cwd=ROOT,env=env,stdout=console,stderr=subprocess.STDOUT,start_new_session=True)
    def read():
        try:return json.loads(report.read_text())
        except (FileNotFoundError,json.JSONDecodeError):return {}
    def wait(test,seconds=60):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            value=test()
            if value:return value
            assert process.poll() is None,f'Unexpected exit {process.returncode}'
            time.sleep(.1)
        raise AssertionError('Timed out waiting for native launcher state')
    def command(sequence,action,**kw):
        temp=control.with_suffix('.tmp');temp.write_text(json.dumps(dict(sequence=sequence,action=action,**kw)));temp.replace(control)
    try:
        wait(lambda:read().get('snapshot',{}).get('hosted') is False)
        actual=Path(f'/proc/{process.pid}/exe').resolve()
        assert actual==expected,(actual,expected)
        digest=hashlib.sha256(actual.read_bytes()).hexdigest()
        screenshot=out/'menu.png';command(1,'screenshot',filename=str(screenshot))
        wait(lambda:screenshot.exists() and screenshot.read_bytes().endswith(b'IEND\xaeB`\x82'))
        command(2,'quit');process.wait(timeout=30);assert process.returncode==0
        result=dict(ok=True,package_directory=str(args.expected_package.resolve()),actual_executable=str(actual),sha256=digest,screenshot=str(screenshot),checks=[
            'Repository launcher without package overrides selects the candidate executable',
            'Native menu renders and normal Quit exits with code zero'],runtime_assets=assert_runtime_assets([out/'game.log']))
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    finally:stop_owned_process_groups([process],[console])
if __name__=='__main__':main()
