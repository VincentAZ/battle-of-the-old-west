"""Validate coverage and provenance of the Crew historical audit, not its truth."""
import json
from pathlib import Path
from urllib.parse import urlparse

from build_crew_review import ROOT, ROSTER


def main():
    directory = ROOT / 'research/crew-history-audit'
    records = {}
    for path in sorted(directory.glob('audit-*.json')):
        for record in json.loads(path.read_text()):
            slug = record['slug']
            assert slug not in records, f'Duplicate audit: {slug}'
            for field in ('identity_type', 'date_scope', 'location_scope', 'historical_basis', 'history_lesson', 'sources', 'decision'):
                assert record.get(field), f'{slug}: missing {field}'
            assert record['decision'] in {'retain', 'revise'}, slug
            assert isinstance(record['issues'], list), slug
            for source in record['sources']:
                assert source.get('title') and source.get('supports'), (slug, source)
                assert urlparse(source['url']).scheme in {'https', 'http'}, (slug, source)
            if record['decision'] == 'revise':
                assert record.get('revision_brief'), f'{slug}: revision lacks a brief'
            records[slug] = record
    expected = set(sum(ROSTER.values(), []))
    assert set(records) == expected, {'missing': sorted(expected - records.keys()),
                                      'unexpected': sorted(records.keys() - expected)}
    report = {
        'status': 'documentation_coverage_passed',
        'characters': len(records),
        'sourced_history_lessons': sum(bool(r['history_lesson']) for r in records.values()),
        'initial_revision_decisions': sorted(s for s, r in records.items() if r['decision'] == 'revise'),
        'unique_source_urls': len({s['url'] for r in records.values() for s in r['sources']}),
        'historical_accuracy_certified': False,
        'note': 'Coverage validation verifies records and links are present. It does not authenticate claims, costumes, or likenesses; read the evidence and outstanding issues.',
        'new_animation_authorized': False,
    }
    (directory / 'coverage-validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
