"""Check native capture completeness and assemble contact sheets for visual review.

A successful result proves capture integrity, not absence of clipping.
"""
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/western/native/lozen-cloth-v004'
run = json.loads((OUT/'unreal-run-frames.json').read_text())
assert run['ok'] and len(run['captures']) == 48
hashes = {}
for capture in run['captures']:
    path = OUT / capture['file']
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == capture['sha256']
    with Image.open(path) as image:
        assert image.size == (1280,720) == tuple(capture['size'])
    hashes[capture['file']] = digest
assert len(set(hashes.values())) >= 24, 'Unexpected repeated/static pose captures'
for group in ['walk-front', 'walk-side', 'walk-rear', 'MM']:
    files = sorted((OUT/'previews').glob('Unreal-'+group+'*.png'))
    assert len(files) == 12
    sheet = Image.new('RGB', (1800,1000), '#202020')
    for i, path in enumerate(files):
        with Image.open(path) as source:
            picture = source.crop((410,90,900,720))
            picture.thumbnail((290,450))
            x,y = (i%6)*300,(i//6)*500
            sheet.paste(picture,(x,y+25))
            ImageDraw.Draw(sheet).text((x+4,y+5),path.stem,fill='white')
    sheet.save(OUT/('Contact-'+group+'.png'))
(OUT/'capture-validation.json').write_text(json.dumps(dict(ok=True,
    captures=len(hashes), dimensions=[1280,720], files=hashes,
    visual_review_status='pending'),indent=2)+'\n')
