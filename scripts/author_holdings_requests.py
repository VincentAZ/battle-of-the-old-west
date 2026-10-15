"""Write the Mixar reference and model requests for each Holding from its evidence.

Run: python3 -I scripts/author_holdings_requests.py [slugs...]

Requests are only written when absent, so completed paid jobs are never
re-fingerprinted. The reference prompt is the sourced render brief itself.
"""
import json
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from holdings_roster import HOLDINGS, REVIEW  # noqa: E402


def write_if_absent(path, value):
    if path.exists():
        return 'kept'
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return 'written'


def main():
    slugs = sys.argv[1:]
    validation = json.loads((REVIEW / 'history-validation.json').read_text())
    # A pilot validates a subset; each holding needs its own clean, checked entry.
    assert validation['status'] == 'passed' or slugs, 'Validate the historical evidence first'
    for card_id, (slug, *_rest) in HOLDINGS.items():
        if slugs and slug not in slugs:
            continue
        directory = REVIEW / slug
        evidence = json.loads((directory / 'historical-evidence.json').read_text())
        assert evidence['canonical_card_id'] == card_id and slug in validation['holdings'] and not validation['holdings'][slug]['issues']
        assert validation['holdings'][slug].get('evidence_sha256') == hashlib.sha256(
            (directory / 'historical-evidence.json').read_bytes()).hexdigest(), 'Evidence changed; validate it again'
        reference = {
            'service': 'image_gen', 'model': 'flash-3-1',
            'params': {'style': '3d_render', 'aspect_ratio': '4:3', 'number_of_images': 1},
            'historical_evidence': 'historical-evidence.json',
            'prompt': evidence['render_brief'],
        }
        model = {
            'service': 'model_3d', 'model': 'tripo-v31', 'image': 'reference.png',
            'params': {'pbr': True, 'texture': True, 'face_limit': 24000, 'texture_quality': 'detailed'},
            'historical_evidence': 'historical-evidence.json',
        }
        print(slug, 'reference', write_if_absent(directory / 'reference-request.json', reference),
              'model', write_if_absent(directory / 'model-request.json', model))


if __name__ == '__main__':
    main()
