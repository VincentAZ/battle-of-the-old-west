"""Lay out unretouched static mesh renders for inspection and all-copy review."""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from build_crew_review import ROOT, OUT, ROSTER, EXISTING, VIEWS


def directory(slug):
    revisions = OUT / 'historical-revisions.json'
    paths = json.loads(revisions.read_text()) if revisions.exists() else {}
    if slug in paths:
        return ROOT / paths[slug]
    return (ROOT / 'art/western/native/review-v001' if slug in EXISTING else OUT) / slug


def sheet(items, destination, columns, width, height, title):
    rows = (len(items) + columns - 1) // columns
    canvas = Image.new('RGB', (columns * width, rows * (height + 64) + 56), '#191c20')
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 17)
    heading = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 22)
    draw.text((14, 12), title, font=heading, fill='#e7e3da')
    for n, (path, label, subtitle) in enumerate(items):
        image = Image.open(path).convert('RGB')
        image.thumbnail((width, height), Image.Resampling.LANCZOS)
        x, y = n % columns * width, 56 + n // columns * (height + 64)
        canvas.paste(image, (x + (width - image.width) // 2, y + (height - image.height) // 2))
        draw.text((x + 12, y + height + 4), label, font=font, fill='#e7e3da')
        draw.text((x + 12, y + height + 29), subtitle, font=font, fill='#b8b8b8')
    canvas.save(destination, quality=94)
    print(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--slugs', nargs='+')
    parser.add_argument('--overview', action='store_true')
    args = parser.parse_args()
    if args.slugs:
        for slug in args.slugs:
            base = directory(slug)
            manifest = json.loads((base / 'review/manifest.json').read_text())
            assert {p['view'] for p in manifest['previews']} == VIEWS
            items = [(base / 'review' / p['file'], p['view'], 'Actual static mesh render') for p in manifest['previews']]
            sheet(items, base / 'review/inspection-sheet.jpg', 4, 640, 480, manifest['character']['display_name'])
    if args.overview:
        items = []
        cards = {c['id']: c['name'] for c in json.loads((ROOT / 'game/data/cards.json').read_text())['cards']}
        for card, slugs in ROSTER.items():
            for n, slug in enumerate(slugs, 1):
                base = directory(slug)
                manifest = json.loads((base / 'review/manifest.json').read_text())
                image = base / 'review/previews/three-quarter.png'
                assert image.is_file() and manifest['animations'] == [] and not manifest['rigged']
                items.append((image, manifest['character']['display_name'], f'{cards[card]} · copy {n}'))
        assert len(items) == 46
        for start in range(0, 46, 12):
            number = start // 12 + 1
            sheet(items[start:start + 12], OUT / f'Crew-Static-Contact-{number:02}.jpg', 4, 440, 330,
                  f'Western Crew · static models · copies {start + 1}–{min(start + 12, 46)} of 46')


if __name__ == '__main__':
    main()
