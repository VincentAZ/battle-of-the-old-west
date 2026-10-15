"""Download public research pages and linked card photographs for local verification."""
import concurrent.futures
import html
import json
from pathlib import Path
from html.parser import HTMLParser
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research' / 'raw'
class Images(HTMLParser):
    def __init__(self):
        super().__init__(); self.images = []; self.anchor = ''
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'a': self.anchor = a.get('href','')
        if tag == 'img' and ('googleusercontent.com' in a.get('src','') or 'bp.blogspot.com' in a.get('src','')):
            url = self.anchor if ('googleusercontent.com' in self.anchor or 'bp.blogspot.com' in self.anchor) else a['src']
            if url.startswith('//'): url = 'https:' + url
            self.images.append({'url': html.unescape(url), 'alt': a.get('alt','')})
    def handle_endtag(self, tag):
        if tag == 'a': self.anchor = ''

def download(item):
    name, url = item
    r = requests.get(url, timeout=40)
    r.raise_for_status()
    path = OUT / name
    path.write_bytes(r.content)
    return {'file': str(path.relative_to(ROOT)), 'url': r.url, 'bytes': len(r.content)}

if __name__ == '__main__':
    urls = {
      'base-blog': 'https://elvisdontteachyouplayingboardgames.blogspot.com/2022/03/oldwest-card-game-review.html',
      'expansion-blog': 'https://elvisdontteachyouplayingboardgames.blogspot.com/2025/07/oldwest-cult-of-chrome-expansion-review.html',
    }
    manifest=[]; jobs=[]
    for label,url in urls.items():
        item=download((label+'.html',url)); manifest.append(item)
        parser=Images(); parser.feed((ROOT/item['file']).read_text())
        for n,im in enumerate(parser.images):
            # The original size is available through each photograph's public link.
            jobs.append((label+'-%02d.jpg'%n,im['url']))
            manifest.append({'file':'research/raw/'+jobs[-1][0],**im})
    (OUT/'image-manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False))
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for item in pool.map(download,jobs):
            print(item['file'],item['bytes'])
    (OUT/'image-manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False))
