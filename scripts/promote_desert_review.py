"""Record successful desert package checks and select the reviewed local build."""
import hashlib
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'art/western/regions/desert-v001'
PACKAGE = ROOT/'dist/linux-development-desert-20261009'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenery',action='store_true',help='Select the dunes/cacti revision')
    args=parser.parse_args()
    OUT=ROOT/('art/western/regions/desert-v004' if args.scenery else 'art/western/regions/desert-v001')
    PACKAGE=ROOT/('dist/linux-development-desert-scenery-20261009-v3' if args.scenery else 'dist/linux-development-desert-20261009')
    result = json.loads((OUT/'runtime-packaged/result.json').read_text())
    assert result['ok'] and len(result['results']) == 3
    assert all(r['ok'] and r['authoritative_views_unchanged'] for r in result['results'])
    validation = next(PACKAGE.glob('logs/*/archive/validation.json'))
    validated = json.loads(validation.read_text())
    assert validated['ok']
    for name in ('/Game/Art/Western/Regions/Materials/M_Region_DesertGround',
                 '/Game/Art/Western/ExpansionHoldings/LandingTerrainFitV002/M_LandingTerrain_Desert'):
        assert name in validated['verified_required_packages']
    if args.scenery:
        assert json.loads((OUT/'geometry-validation.json').read_text())['ok']
        for mesh in ('DesertDuneV004_0','DesertDuneV004_1','DesertCactiV004'):
            assert '/Game/Art/Western/Regions/Meshes/SM_Region_'+mesh in validated['verified_required_packages']
    baseline = json.loads((ROOT/'art/western/holdings/expansion-review-v001/mechanics-baseline.json').read_text())['sha256']
    assert all(sha(ROOT/p) == h for p,h in baseline.items())
    captures = {}
    for region in (0,1,2):
        for p in (OUT/f'runtime-packaged/{region}/1600x900').glob('*.png'):
            captures[str(p.relative_to(ROOT))] = sha(p)
    assert len(captures) == 9
    current = ROOT/'dist/current'
    previous = os.readlink(current)
    report = dict(completed_utc=datetime.now(timezone.utc).isoformat(),
        package=str(PACKAGE.relative_to(ROOT)), previous_selected_package=previous,
        binary_sha256=sha(Path(validated['binary'])),
        regional_checks_sha256=sha(OUT/'runtime-packaged/result.json'),
        package_validation_sha256=sha(validation), captures=captures,
        unchanged_mechanics_files=len(baseline),
        appearance='Sonoran dunes and cacti; user test pending.' if args.scenery else 'First-pass warm desert replacing winter; user test pending.',
        prior_user_approvals={'pine':True,'river':True,'quote':'these are approved'},
        retained='Prior package, winter materials, and original bytes of 11 modified base-fit materials.',
        scope='Two terrain-fitted dunes, 11 saguaros, eight prickly-pear groups; original terrain/collider retained.' if args.scenery else 'Ground material and matching holding-base blends; existing terrain and rock geometry retained.',
        limitations='No exhaustive holding-placement or action lifecycle regression.',
        review_launcher='scripts/launch_desert_review.sh')
    (OUT/'promotion.json').write_text(json.dumps(report,indent=2)+'\n')
    temporary = ROOT/'dist/current-desert-promotion'
    assert not temporary.exists() and not temporary.is_symlink()
    temporary.symlink_to(PACKAGE.name)
    temporary.replace(current)
    print('DESERT_PACKAGE_SELECTED',PACKAGE.name)

if __name__ == '__main__':main()
