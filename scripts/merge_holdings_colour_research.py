"""Merge sourced colour research into review-v002 Holding evidence.

Run: python3 -I scripts/merge_holdings_colour_research.py RESEARCH.json [RESEARCH.json ...]

Each research file maps slug -> {new_sources, documented_colors, brief,
brief_changes, uncertainties, remove_v001_uncertainties_matching} and may carry
"_setting_ground" palettes. The v001 evidence stays the base record: its
features, sources, history lesson and still-valid uncertainties are kept; new
sources are appended (capped at 10 in all) and [R#] tags are renumbered to
their [S#] positions. The full-colour SUFFIX is appended to each brief. Holdings
already present in review-v002 are never overwritten.
"""
import datetime
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from holdings_roster import HOLDINGS, ROOT  # noqa: E402

V1 = ROOT / 'art/western/holdings/review-v001'
V2 = ROOT / 'art/western/holdings/review-v002'
PALETTES = ROOT / 'art/western/holdings/base-palettes.json'
BANNED = re.compile(r'\b(muted|faded|desaturated|washed[- ]out|drab)\b', re.I)
REQUEST = ("the project owner, Oct 7 2026: 'these are bland as hell ... what do they ACTUALLY look like with color?'; "
           "'I want full color and a fun historically accurate game that pops'; 'yup' to rolling out all 34")


def suffix():
    source = (ROOT / 'scripts/validate_holdings_history.py').read_text()
    start = source.index('SUFFIX = (') + len('SUFFIX = ')
    return eval(source[start:source.index('\n# The October 7 three-holding pilot')].strip())  # literal string tuple


def merge(slug, research, style, problems):
    directory = V2 / slug
    if (directory / 'historical-evidence.json').exists():
        return 'kept (already in v002)'
    evidence = json.loads((V1 / slug / 'historical-evidence.json').read_text())
    existing = len(evidence['sources'])
    new = research['new_sources']
    if existing + len(new) > 10:
        problems.append(f'{slug}: {existing}+{len(new)} sources exceeds 10')
        return 'failed'
    for source in new:
        if not (source.get('url') and source.get('title') and len(source.get('supports', '').split()) >= 6):
            problems.append(f'{slug}: incomplete new source {source.get("url")}')

    def renumber(text):
        def tag(match):
            n = int(match.group(1))
            if not 1 <= n <= len(new):
                problems.append(f'{slug}: [R{n}] has no new source')
            return f'[S{existing + n}]'
        result = re.sub(r'\[R(\d+)\]', tag, text)
        for n in re.findall(r'\[S(\d+)\]', text):
            if not 1 <= int(n) <= existing:
                problems.append(f'{slug}: [S{n}] is not a v001 source')
        return result

    # Uncited reconstruction notes are uncertainties, not documented colours.
    moved = [c for c in research['documented_colors']
             if not re.search(r'\[[RS]\d+\]', c) and c.upper().startswith(('RECONSTRUCTION', 'NOT DOCUMENTED'))]
    colours = [renumber(c) for c in research['documented_colors'] if c not in moved]
    if not colours or any(not re.search(r'\[S\d+\]', c) for c in colours):
        problems.append(f'{slug}: every documented colour needs a citation')
    brief = research['brief'].strip()
    words = len(brief.split())
    if not 60 <= words <= 220:
        problems.append(f'{slug}: brief has {words} words')
    if BANNED.search(brief):
        problems.append(f'{slug}: brief uses banned muted wording: {BANNED.search(brief).group(0)}')
    obsolete = research.get('remove_v001_uncertainties_matching', [])
    kept = [u for u in evidence['uncertainties'] if not any(k.lower() in u.lower() for k in obsolete)]
    evidence['sources'] = evidence['sources'] + [{k: s[k] for k in ('url', 'title', 'supports')} for s in new]
    evidence['documented_colors'] = colours
    evidence['uncertainties'] = kept + [renumber(u) for u in research['uncertainties']] + moved
    evidence['render_brief'] = brief + ' ' + style
    evidence['revision'] = {'from': f'review-v001/{slug}/historical-evidence.json', 'reason': REQUEST,
                            'brief_changes': research.get('brief_changes', ''),
                            'colour_research': 'sources fetched by the October 7, 2026 colour research batches'}
    evidence['evidence_prepared_at'] = datetime.date.today().isoformat()
    if any(p.startswith(slug + ':') for p in problems):
        return 'failed'
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copy2(V1 / slug / 'holding.json', directory / 'holding.json')
    (directory / 'historical-evidence.json').write_text(json.dumps(evidence, indent=1, ensure_ascii=False) + '\n')
    return f'written ({len(evidence["sources"])} sources, {words} words)'


def main():
    style = suffix()
    slugs = {slug for slug, *_ in HOLDINGS.values()}
    palettes = json.loads(PALETTES.read_text())
    problems = []
    for path in sys.argv[1:]:
        research = json.loads(Path(path).read_text())
        for slug, entry in research.items():
            if slug == '_setting_ground':
                for setting, ground in entry.items():
                    target = palettes['settings'][setting]
                    target['colors'].update({k: v for k, v in ground['colors_srgb'].items() if len(v) == 3})
                    target['sources'] = ground['sources']
                    target['description'] = ground['description']
                    target['uncertainties'] = ground.get('uncertainties', [])
                    print('palette', setting, 'updated from', Path(path).name)
                continue
            assert slug in slugs, slug
            print(slug, merge(slug, entry, style, problems))
    cited = [s for s, v in palettes['settings'].items() if v.get('sources')]
    palettes['status'] = 'cited settings: ' + ', '.join(sorted(cited))
    PALETTES.write_text(json.dumps(palettes, indent=1) + '\n')
    for problem in problems:
        print('PROBLEM', problem)
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
