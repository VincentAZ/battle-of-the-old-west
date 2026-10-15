"""Inventory installed template character assets without changing the UE project."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
ENGINE = Path.home() / 'Applications/UnrealEngine-5.8.2'
OUT = ROOT / 'art/characters'
PACKS = {
    'characters': ('Templates/TemplateResources/High/Characters/Content', 'Characters'),
    'weapons': ('Templates/TemplateResources/Standard/Weapons/Content', 'Weapons'),
}


def inventory():
    OUT.mkdir(parents=True, exist_ok=True)
    result = {'engine_root': str(ENGINE), 'engine_version': '5.8.2', 'packs': {}}
    all_destinations = set()
    for name, (relative, mount) in PACKS.items():
        source = ENGINE / relative
        records = []
        for p in sorted(source.rglob('*.uasset')):
            data = p.read_bytes()
            refs = sorted({s.decode('ascii') for s in re.findall(rb'/Game/[A-Za-z0-9_/-]+', data)})
            destination = f'/Game/{mount}/{p.relative_to(source).with_suffix("").as_posix()}'
            all_destinations.add(destination)
            records.append({'source': str(p), 'package': destination, 'bytes': len(data),
                            'sha256': hashlib.sha256(data).hexdigest(), 'game_references': refs})
        result['packs'][name] = {'source_content': str(source), 'project_subdirectory': mount,
                                 'asset_count': len(records), 'assets': records}
    for pack in result['packs'].values():
        pack['references_outside_inventoried_packs'] = sorted({ref for row in pack['assets']
            for ref in row['game_references'] if ref not in all_destinations})
    (OUT / 'unreal-template-assets.json').write_text(json.dumps(result, indent=2) + '\n')
    for name, pack in result['packs'].items():
        print(name, pack['asset_count'], 'assets', 'external refs', pack['references_outside_inventoried_packs'])


if __name__ == '__main__':
    inventory()
