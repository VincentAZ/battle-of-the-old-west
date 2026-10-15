"""Coordinated v3 import with an immutable rollback copy and exact write scope.

Only run after root grants the native commandlet lane. No runtime source edits.
Canonical 18 variant assets may change; every other Survivor asset is guarded.
A fresh verify_survivor_variants.py process must pass before render validation.
"""
import hashlib
import json
import os
import runpy
import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'art/characters/survivor_variants/deformation-v3'
CONTENT=ROOT/'game/OldWest/Content/Art/Survivors'
DEST=CONTENT/'Variants'
NAMES=('Prospector','Gatling Gunner','Bounty Hunter')
ALLOWED={DEST/('SKM_'+name+'_Cm.uasset') for name in NAMES}
ALLOWED|={DEST/'Materials'/('M_'+name+'_Outfit.uasset') for name in NAMES}
ALLOWED|={DEST/'Textures'/('T_'+name+'_Outfit_'+channel+'.uasset') for name in NAMES for channel in ('BaseColor','Normal','Roughness','Metallic')}
assert len(ALLOWED)==18

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inventory():return {str(p):sha(p) for p in CONTENT.rglob('*.uasset')}

review=json.loads((SOURCE/'deformation-preflight/manual-review.json').read_text())
assert review['status']=='bounded_CPU_deformation_preflight_passed_native_review_pending'
assert review['reviewed_image_count']==12 and review['bone_matrices_identical_to_original_studies']
assert {p for p in DEST.rglob('*.uasset')}==ALLOWED,'Unexpected current variant asset scope'
assert all(p.is_file() for p in ALLOWED)
for name in NAMES:
 spec=json.loads((SOURCE/name.lower()/'manifest.json').read_text())
 assert spec['rig_bones']==53 and spec['original_rig_unchanged']
 assert sha(SOURCE/name.lower()/(name+'_Cm.fbx'))==spec['fbx_sha256']
 assert all(sha(Path(t['path']))==t['sha256'] for t in spec['textures'].values())

stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
backup=SOURCE/'native-import-backups'/stamp
backup.mkdir(parents=True,exist_ok=False)
before=inventory()
# Preserve the complete current native survivor family. This includes the
# canonical18 rollback assets, original skeleton/materials and current clips.
# Original authored source is retained independently, and also hash-guarded.
for path,digest in before.items():
 source=Path(path);target=backup/'native'/source.relative_to(CONTENT)
 target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
 assert sha(target)==digest
art_paths=[ROOT/'art/characters/oldwest_survivor/Survivor_A.blend']
for name in NAMES:
 folder=ROOT/'art/characters/survivor_variants'/name.lower()
 art_paths.extend([folder/(name+'.blend'),folder/(name+'_Cm.fbx'),folder/'manifest.json'])
 art_paths.extend((folder/'textures').glob('*.png'))
original_art={str(p):sha(p) for p in art_paths}
for path,digest in original_art.items():
 source=Path(path);target=backup/'authored'/source.relative_to(ROOT/'art')
 target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
 assert sha(target)==digest
manifest={'status':'backup_verified_before_import','created_utc':stamp,'source':str(SOURCE),'allowed_native_mutations':sorted(map(str,ALLOWED)),
          'native_before_sha256':before,'authored_original_sha256':original_art,'rollback_root':str(backup),
          'rollback_policy':'Only when Unreal processes are closed: copy backup/native/Variants over Content/Art/Survivors/Variants; verify SHA values. Original-family files must not change during this import.'}
(backup/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
report={'ok':False,'status':'importing','backup':str(backup),'backup_manifest_sha256':sha(backup/'manifest.json'),'allowed_native_asset_count':18}
try:
 os.environ['OLDWEST_VARIANT_SOURCE']=str(SOURCE)
 runpy.run_path(str(ROOT/'scripts/import_survivor_variants.py'),run_name='__main__')
 after=inventory();assert set(after)==set(before),'Import created or removed an unplanned Survivor asset'
 unexpected=[p for p in before if Path(p) not in ALLOWED and before[p]!=after[p]]
 assert not unexpected,('Import modified protected Survivor assets',unexpected)
 assert all(sha(Path(p))==digest for p,digest in original_art.items()),'Authored original files changed'
 changed=[p for p in before if before[p]!=after[p]]
 assert {str(p) for p in ALLOWED if p.parent==DEST}<=set(changed),'A canonical mesh was not replaced'
 report.update(ok=True,status='import_saved_fresh_process_audit_pending',native_after_sha256=after,changed_native_paths=changed,
               protected_native_unchanged=True,original_art_unchanged=True)
except Exception as error:
 report.update(error=f'{type(error).__name__}: {error}',traceback=traceback.format_exc(),status='failed_backup_retained_not_promoted')
 raise
finally:
 (SOURCE/'coordinated-import.json').write_text(json.dumps(report,indent=2)+'\n')
 print('DEFORMATION_V3_COORDINATED_IMPORT',json.dumps({'ok':report['ok'],'backup':str(backup),'status':report['status']}),flush=True)
