"""Import and retarget the two preview-only figures, leaving gameplay untouched."""
import os, runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for slug in ['lozen','sarah-winnemucca']:
    os.environ['OLDWEST_NATIVE_PREVIEW']=slug
    runpy.run_path(str(ROOT/'scripts/import_native_preview_unreal.py'),run_name='__main__')
    runpy.run_path(str(ROOT/'scripts/retarget_native_preview_unreal.py'),run_name='__main__')
