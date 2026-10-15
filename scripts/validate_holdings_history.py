"""Check the historical evidence for every Holding before any paid rendering.

Run: python3 -I scripts/validate_holdings_history.py [--skip-network]

Confirms the evidence schema, the sourced-claim mapping, the full-colour render
style suffix, the 1865-1900 period policy and that each cited URL still
resolves. Passing this check is documentation completeness; it is not
historical approval of a rendered model, which requires inspecting the mesh.
"""
import argparse
import datetime
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from holdings_roster import COLOUR_PASS, HOLDINGS, REVIEW, catalog  # noqa: E402

# Art direction (the project owner, October 7, 2026): full colour, a fun historically accurate game
# that pops. Never ask a generator for muted, faded or desaturated colour; accuracy decides
# WHICH colours, not how strongly they read. Where the documented material really is grey
# (unpainted weathered wood), the colour comes from its documented neighbours and the base,
# never from invented paint.
SUFFIX = ('Grounded stylized realistic 3D Western game structure matching the existing natural-proportion '
          'crew and camp dioramas. Single isolated structure standing directly on the studio floor with no '
          'ground patch, terrain, base, plinth or floor disc under it; no surrounding town or landscape, no '
          'people, animals, vehicles or legible text. Full rich colour: every documented period paint, brick, '
          'stone, iron, canvas and timber colour described above at full natural saturation, crisp and '
          'readable as lively game art in warm golden daylight; light weathering that never washes colour '
          'out to gray or tan. Complete structure including roof and all sides, slightly elevated '
          'three-quarter front view, neutral light gray seamless studio background, bright clear daylight. '
          'No fire, smoke or animation.')
# The October 7 three-holding pilot (riverboat, homestead-cabin, saloon) was generated with
# this earlier wording of the same full-colour direction; it stays valid for those records.
PILOT_SUFFIX = ('Grounded stylized realistic 3D Western game structure matching the existing natural-proportion '
                'crew and camp dioramas. Single isolated structure standing directly on the studio floor with no '
                'ground patch, terrain, base, plinth or floor disc under it; no surrounding town or landscape, no '
                'people, animals, vehicles or legible text. True documented period colours and materials exactly as '
                'described above, at full natural saturation in warm daylight; restrained weathering that never '
                'washes the colours to gray. Complete structure including roof and all sides, slightly elevated '
                'three-quarter front view, neutral light gray seamless studio background, bright even daylight. '
                'No fire, smoke or animation.')
# RETIRED. The v001 suffix asked for "muted colors" and "a small flat patch of bare ground",
# which washed all 34 holdings to tan and baked the same slab under each. It is kept only so
# the v001 review record (what was actually sent and paid for) still validates. Never use it
# for new work.
RETIRED_V001_SUFFIX = ('Grounded stylized realistic 3D Western game structure matching the existing natural-proportion '
                       'crew and camp dioramas. Single isolated structure on a small flat patch of bare ground, no '
                       'surrounding town or landscape, no people, animals, vehicles or legible text. Matte natural '
                       'weathered wood, stone, adobe, canvas and iron, muted colors, restrained wear. Complete structure '
                       'including roof and all sides, slightly elevated three-quarter front view, neutral light gray '
                       'seamless studio background, soft even light. No pedestal, plinth, floor disc, fire, smoke or animation.')
ACCEPTED_SUFFIXES = (SUFFIX, PILOT_SUFFIX) if COLOUR_PASS else (RETIRED_V001_SUFFIX,)
# Sourced notice boards need period print and need not have a roof.
NOTICE_SUFFIX = SUFFIX.replace('or legible text.', 'or unsourced text.').replace(
    'including roof and all sides,', 'including all sides and any documented roof,')
LANDING_SUFFIX = SUFFIX.replace('people, animals, vehicles or legible text.',
    'people, animals, unrelated vehicles or legible text.').replace(
    'including roof and all sides,', 'including hull, deck, sides and underside,')
MAX_SOURCES = 10 if COLOUR_PASS else 4
REQUIRED = ('subject', 'canonical_card_id', 'identity_type', 'date_scope', 'location_scope',
            'documented_features', 'render_brief', 'history_lesson', 'sources', 'uncertainties')
BLOCKED_DOMAINS = ('wikipedia.org', 'wikimedia.org', 'pinterest.', 'facebook.com', 'reddit.com')


def fetch_status(url, agent='Mozilla/5.0 (X11; Linux x86_64) OldWestHistoryCheck/1.0'):
    request = urllib.request.Request(url, headers={
        'User-Agent': agent, 'Accept': 'text/html,application/pdf,*/*;q=0.8'})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return response.status, None
    except urllib.error.HTTPError as error:
        if error.code >= 500 and agent != 'Mozilla/5.0':
            return fetch_status(url, 'Mozilla/5.0')  # some proxies reject unfamiliar agents transiently
        return error.code, str(error.reason)
    except Exception as error:  # DNS, TLS, timeout
        return None, type(error).__name__ + ': ' + str(error)[:120]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-network', action='store_true')
    parser.add_argument('slugs', nargs='*')
    args = parser.parse_args()
    camps = catalog()
    report_path = REVIEW / 'history-validation.json'
    previous = json.loads(report_path.read_text()) if args.slugs and report_path.exists() else {}
    report = {'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'scope': 'evidence completeness and URL reachability; not historical approval of any mesh',
              'holdings': dict(previous.get('holdings', {}))}
    problems = []
    for card_id, (slug, name, *_rest) in HOLDINGS.items():
        if args.slugs and slug not in args.slugs:
            continue
        path = REVIEW / slug / 'historical-evidence.json'
        entry = {'file': str(path.relative_to(REVIEW.parent.parent.parent)), 'issues': [], 'sources': []}
        report['holdings'][slug] = entry
        if not path.is_file():
            entry['issues'].append('missing historical-evidence.json')
            problems.append(slug)
            continue
        try:
            evidence = json.loads(path.read_text())
        except json.JSONDecodeError as error:
            entry['issues'].append('invalid JSON: ' + str(error))
            problems.append(slug)
            continue
        entry['evidence_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        entry['network_checked'] = not args.skip_network
        for key in REQUIRED:
            if not evidence.get(key):
                entry['issues'].append('missing ' + key)
        if evidence.get('canonical_card_id') != card_id:
            entry['issues'].append('canonical_card_id must be ' + card_id)
        if evidence.get('subject', '').casefold() != name.casefold():
            entry['issues'].append(f'subject must be {name!r}')
        if evidence.get('identity_type') not in ('historical_building_type', 'documented_landform'):
            entry['issues'].append('identity_type must be historical_building_type or documented_landform')
        scope_head = re.sub(r'\([^)]*\)', '', str(evidence.get('date_scope', '')))
        years = [int(y) for y in re.findall(r'\b(1[89]\d\d)', scope_head)]
        if not years or any(y < 1860 or y > 1900 for y in years):
            entry['issues'].append('date_scope must state years within the 1865-1900 Western roster period')
        brief = str(evidence.get('render_brief', ''))
        suffixes = ACCEPTED_SUFFIXES
        if COLOUR_PASS and card_id == 'wanted_poster_board' and evidence.get('reconstructed_print'):
            suffixes += (NOTICE_SUFFIX,)
        if COLOUR_PASS and card_id == 'smuggler_s_landing' and evidence.get('watercraft_subject'):
            suffixes += (LANDING_SUFFIX,)
        suffix = next((x for x in suffixes if brief.rstrip().endswith(x)), None)
        if not suffix:
            entry['issues'].append('render_brief must end with the full-colour style suffix')
        specific = brief[:-len(suffix)] if suffix else brief
        words = len(specific.split())
        if not 60 <= words <= 220:
            entry['issues'].append(f'render_brief subject description has {words} words; expected 60-220')
        if re.search(r'\b(people|person|cowboy|cowboys|horse|horses|cattle)\b', specific, re.I) and \
                not re.search(r'\bno (people|animals)\b', specific, re.I):
            entry['notes'] = entry.get('notes', []) + ['brief mentions people or animals; confirm the subject is unpopulated']
        lesson = str(evidence.get('history_lesson', ''))
        sentences = [s for s in re.split(r'(?<![A-Z]\.)(?<=[.!?])\s+', lesson.strip()) if s]  # initials such as W. H. are not sentence ends
        if not 2 <= len(sentences) <= 4:
            entry['issues'].append(f'history_lesson has {len(sentences)} sentences; expected 2-4')
        if re.search(r'\b(this card|the card|ability|the player|opponent|water cost|raid icon)\b', lesson, re.I):
            entry['issues'].append('history_lesson must not describe game mechanics')
        sources = evidence.get('sources') or []
        if not 2 <= len(sources) <= MAX_SOURCES:
            entry['issues'].append(f'{len(sources)} sources; expected 2-{MAX_SOURCES}')
        for index, source in enumerate(sources, 1):
            record = {'index': index, 'url': source.get('url'), 'title': source.get('title')}
            entry['sources'].append(record)
            if not (source.get('url') and source.get('title') and source.get('supports')):
                entry['issues'].append(f'source S{index} needs url, title and supports')
                continue
            if any(domain in source['url'] for domain in BLOCKED_DOMAINS):
                entry['issues'].append(f'source S{index} uses a non-authoritative domain')
            if len(source['supports'].split()) < 6:
                entry['issues'].append(f'source S{index} supports statement is too short to name a claim')
            if not args.skip_network:
                status, error = fetch_status(source['url'])
                record['http_status'] = status
                if error:
                    record['error'] = error
                if status is None or status in (404, 410) or (status and status >= 500):
                    entry['issues'].append(f'source S{index} unreachable: {status} {error or ""}'.strip())
                elif status in (401, 403, 429):
                    entry['notes'] = entry.get('notes', []) + [f'source S{index} answered {status}; verify manually']
        claims = list(evidence.get('documented_features') or [])
        if COLOUR_PASS:
            colours = evidence.get('documented_colors') or []
            if not colours:
                entry['issues'].append('colour pass requires documented_colors')
            claims += colours
        for feature in claims:
            refs = [int(n) for n in re.findall(r'\[S(\d+)\]', feature)]
            if not refs:
                entry['issues'].append('documented feature lacks a [Sn] citation: ' + feature[:60])
            elif any(n < 1 or n > len(sources) for n in refs):
                entry['issues'].append('documented feature cites a missing source: ' + feature[:60])
        entry['ability_summary_checked'] = json.loads((REVIEW / slug / 'holding.json').read_text())['ability_summary']
        assert camps[card_id]['name']
        if entry['issues']:
            problems.append(slug)
    problems = [slug for slug, entry in report['holdings'].items() if entry['issues']]
    report['status'] = ('failed' if problems else 'passed' if len(report['holdings']) == len(HOLDINGS) else 'incomplete')
    report['holdings_checked'] = len(report['holdings'])
    report['holdings_with_issues'] = problems
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    for slug, entry in report['holdings'].items():
        flag = 'OK ' if not entry['issues'] else 'BAD'
        print(flag, slug, len(entry['sources']), 'sources', '; '.join(entry['issues'] + entry.get('notes', [])))
    print('HOLDINGS_HISTORY_VALIDATION', report['status'], len(problems), 'with issues', flush=True)
    return 0 if not problems else 1


if __name__ == '__main__':
    raise SystemExit(main())
