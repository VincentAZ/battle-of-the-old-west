"""Download CC0 Poly Haven assets using their published, checksummed manifests."""
import concurrent.futures
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'art/library/polyhaven'
LIB.mkdir(parents=True, exist_ok=True)
ASSETS = ['rusty_metal_sheet', 'concrete_wall_007', 'dirt_aerial_03',
          'dirt', 'rust_coarse_01', 'rock_07', 'coast_rocks_05',
          'kloppenheim_06_puresky', 'qwantani_sunset_puresky']

def metadata(aid):
    path = LIB / (aid + '.json')
    if not path.exists():
        html = subprocess.check_output(['curl', '-fsSL', '--max-time', '30',
                                        'https://polyhaven.com/a/' + aid]).decode()
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
        assert match, aid
        path.write_text(json.dumps(json.loads(match.group(1)), indent=2))
    return json.loads(path.read_text())['props']['pageProps']

jobs, manifest = [], {}
for aid in ASSETS:
    data = metadata(aid)
    files = data['files']
    item = {'source': 'https://polyhaven.com/a/' + aid, 'license': 'CC0-1.0',
            'authors': data['data'].get('authors'), 'files': {}}
    def add(key, record, relative=None):
        path = LIB / aid / (relative or Path(urlparse(record['url']).path).name)
        jobs.append((path, record))
        item['files'][key] = dict(path=str(path.relative_to(ROOT)),
                                  url=record['url'], md5=record['md5'], size=record['size'])
    if 'gltf' in files:
        rec = files['gltf']['4k']['gltf']
        add('gltf', rec)
        for rel, sub in rec.get('include', {}).items():
            add(rel, sub, rel)
        # Dedicated DX normal maps for Unreal, GL maps for Blender.
        add('nor_dx', files['nor_dx']['4k']['jpg'])
    elif 'hdri' in files:
        add('hdri', files['hdri']['4k']['hdr'])
    else:
        for key in ['Diffuse', 'nor_gl', 'nor_dx', 'Rough', 'rough', 'Metal', 'metal', 'Displacement', 'disp']:
            if key not in files: continue
            formats = files[key].get('4k', {})
            fmt = 'jpg' if 'jpg' in formats else 'png' if 'png' in formats else 'exr'
            if fmt in formats: add(key, formats[fmt])
    manifest[aid] = item

def download(job):
    path, rec = job
    if path.exists() and hashlib.md5(path.read_bytes()).hexdigest() == rec['md5']:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.part')
    subprocess.run(['curl', '-fLsS', '--retry', '2', '--max-time', '180',
                    '-o', str(temp), rec['url']], check=True)
    assert hashlib.md5(temp.read_bytes()).hexdigest() == rec['md5'], str(path)
    temp.replace(path)
    print('VERIFIED', path.name, rec['size'], flush=True)

with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    list(pool.map(download, jobs))
(LIB / 'manifest.json').write_text(json.dumps(manifest, indent=2))
print('COMPLETE', len(jobs), 'files', sum(r['size'] for _, r in jobs), 'bytes')
