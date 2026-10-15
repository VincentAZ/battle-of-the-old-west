"""Label and encode the actual Unreal-rendered preview frames; no interpolation."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PLAYABLE = os.environ.get('OLDWEST_NATIVE_PLAYABLE') == '1'
OUT = ROOT / ('art/western/native/playable-v001/trio-review' if PLAYABLE else 'art/western/native/trio-animation-v001')
render = json.loads((OUT / 'render.json').read_text())
assert render['ok'] and render['written_frames'] == 288 and not render['errors']
frames = [OUT / 'frames' / f'Trio.{i:04d}.png' for i in range(288)]
assert all(p.is_file() for p in frames)
font = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
filters = ['drawbox=x=0:y=900:w=iw:h=180:color=0x171411@0.90:t=fill']
for name, nation, center in [
    ('Quanah Parker', 'Comanche | 1870s', 340),
    ('Lozen', 'Chiricahua Apache | 1880s', 960),
    ('Sarah Winnemucca', 'Northern Paiute | 1870s', 1580),
]:
    for text, y, size, color in [(name, 927, 34, 'white'), (nation, 974, 22, '0xd7c6ab')]:
        filters.append(f"drawtext=fontfile={font}:text='{text}':x={center}-tw/2:y={y}:fontsize={size}:fontcolor={color}")
filters.append(f"drawtext=fontfile={font}:text='UNREAL ENGINE  |  ANIMATION PREVIEW':x=(w-tw)/2:y=1030:fontsize=18:fontcolor=0xb9a990")
video = OUT / 'Native-Trio-Unreal-Animation.mp4'
subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'warning', '-y', '-framerate', '24',
    '-i', str(OUT / 'frames/Trio.%04d.png'), '-vf', ','.join(filters), '-c:v', 'libx264',
    '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
    '-an', str(video)], check=True)
probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams',
    '-show_format', '-of', 'json', str(video)]))
stream = probe['streams'][0]
assert (stream['width'], stream['height'], stream['nb_frames']) == (1920, 1080, '288')
assert float(probe['format']['duration']) == 12
report = dict(ok=True, file=video.name, sha256=hashlib.sha256(video.read_bytes()).hexdigest(),
    width=1920, height=1080, frames=288, fps=24, seconds=12,
    source='Native Unreal Movie Render Queue frames; text labels added with ffmpeg',
    visual_review_status='pending',
    limitations=[] if PLAYABLE else ['Lozen skirt intersects the forward leg in portions of the walking cycle; preview requires weight/cloth refinement before integration.'])
(OUT / 'video-validation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
