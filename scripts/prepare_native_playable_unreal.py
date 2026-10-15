"""Import, retarget, and audit Lozen/Sarah in isolated playable asset folders.

Run with UnrealEditor-Cmd -run=pythonscript. The original preview assets and
selected game package remain intact; gameplay mapping is a separate step.
"""
import os
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for slug, name, source in [
    ('lozen', 'Lozen', 'art/western/native/lozen-cloth-v004'),
    ('sarah-winnemucca', 'Sarah', 'art/western/native/playable-v001/sarah-winnemucca'),
]:
    os.environ['OLDWEST_NATIVE_PREVIEW'] = slug
    os.environ['OLDWEST_NATIVE_SOURCE'] = str(ROOT / source)
    os.environ['OLDWEST_NATIVE_DEST'] = '/Game/Art/Western/' + name
    os.environ['OLDWEST_NATIVE_VERIFY_ONLY'] = '0'
    runpy.run_path(str(ROOT / 'scripts/import_native_preview_unreal.py'), run_name='__main__')
    runpy.run_path(str(ROOT / 'scripts/retarget_native_preview_unreal.py'), run_name='__main__')
