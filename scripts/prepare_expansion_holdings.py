"""Initialize separate expansion review records and researched briefs.

Creates absent files only. Existing evidence and paid requests require explicit
versioned revisions; rerunning this script never silently rewrites them.
"""
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ['OLDWEST_HOLDINGS_SET'] = 'boomtown'
sys.path.insert(0, str(Path(__file__).resolve().parent))
from holdings_roster import HOLDINGS, REVIEW, ROOT, catalog, holding_record
from validate_holdings_history import SUFFIX


def create(path, data):
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def main():
    catalog()
    REVIEW.mkdir(parents=True, exist_ok=True)
    create(REVIEW / 'service-authorization.json', {
        'received_at': '2026-10-08',
        'user_message': 'ok, do 2–5 — expansion holdings, fuse line and Trouble props, regional battlefields, and the remaining presentation details.',
        'scope': '32 distinct sourced full-colour static expansion holdings, setting bases and playable review integration using the existing Mixar workflow.',
        'stages': ['reference', 'model'],
        'estimated_credits': {'per_holding': 54, 'total_32': 1728},
        'estimate_basis': 'Prior holdings workflow: 40-credit reference plus 14-credit model; current service pricing may differ.',
        'final_appearance_approval': False,
        'rigging_authorized': False,
        'game_review_integration_authorized': True,
        'mechanics_change_authorized': False,
    })
    create(REVIEW / 'external-service-approval.json', {
        'status': 'pending_user_reply',
        'destination': 'Mixar image and 3D generation services',
        'payload': 'Sourced art briefs and generated reference images',
        'requested_credit_cap': 1728,
        'reason': 'Automatic approval review rejected the initial four submissions pending explicit destination and spend approval.',
        'submitted_jobs': 0,
    })
    frozen = [ROOT / 'game/data/cards.json', ROOT / 'game/data/boomtown.verified.json']
    frozen += sorted((ROOT / 'game/OldWest/Source/OldWestGame/Private/Core').rglob('*'))
    create(REVIEW / 'mechanics-baseline.json', {
        'scope': 'Current working-tree authoritative core and catalogs before this presentation pass; not a git HEAD comparison.',
        'sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in frozen if p.is_file()},
    })
    batches = sorted((ROOT / 'research/expansion-holdings').glob('*-batch.json'))
    evidence = {}
    for path in batches:
        batch = json.loads(path.read_text())
        assert not set(batch) & set(evidence), 'Duplicate evidence slug across batches'
        evidence.update(batch)
    slugs = {row[0] for row in HOLDINGS.values()}
    assert set(evidence) <= slugs
    for card_id, (slug, *_rest) in HOLDINGS.items():
        create(REVIEW / slug / 'holding.json', holding_record(card_id))
        if slug in evidence:
            record = dict(evidence[slug])
            assert record['canonical_card_id'] == card_id
            record['render_brief'] += ' ' + SUFFIX
            create(REVIEW / slug / 'historical-evidence.json', record)
    print(f'EXPANSION_PREPARED {len(HOLDINGS)} holdings, {len(evidence)} sourced briefs; existing files preserved')


if __name__ == '__main__':
    main()
