"""Import static public identity costumes with the shared importer."""
import os,json,runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'art/characters/identities'
os.environ['OLDWEST_VARIANT_SOURCE']=str(source)
os.environ['OLDWEST_VARIANT_DEST']='/Game/Art/Survivors/Identities'
variants=sorted((p.parent.name,json.loads(p.read_text())['name']) for p in source.glob('*/manifest.json'))
assert len(variants)==23
os.environ['OLDWEST_VARIANT_IDS']=json.dumps(variants)
runpy.run_path(str(ROOT/'scripts/import_survivor_variants.py'),run_name='__main__')
