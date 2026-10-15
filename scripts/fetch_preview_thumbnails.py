from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests
from PIL import Image, ImageOps

items = {'horse_trader':'mbIXjumlnEc', 'wanted_poster_board':'2vZEWJhhk9E', 'boot_hill':'ccQTuIKjXMQ', 'wagon_fort':'TDc_w16Chvk', 'lookout_ridge':'SDmP3O7ijNw', 'pawn_shop':'KDNA9RgsUpo', 'crimp_house':'wqauMpZve-I'}
folder=Path('research/raw/preview-thumbnails')
folder.mkdir(exist_ok=True)
def fetch(item):
    name, video=item
    url=f'https://i.ytimg.com/vi/{video}/sddefault.jpg'
    r=requests.get(url, timeout=25)
    if r.status_code!=200:
        url=f'https://i.ytimg.com/vi/{video}/hqdefault.jpg'
        r=requests.get(url, timeout=25)
    if r.status_code!=200: return name, r.status_code
    path=folder/f'{name}.jpg'
    path.write_bytes(r.content)
    return name, Image.open(path).size
with ThreadPoolExecutor(max_workers=4) as pool:
    for result in pool.map(fetch, items.items()): print(result)
