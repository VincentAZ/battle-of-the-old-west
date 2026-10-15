"""Single source of the Western presentation vocabulary.

Presentation only. Canonical card IDs, rules text in data files, commands,
saves and network payloads are never rewritten; the game translates visible
text at the display boundary (OldWestDisplay::Text) and a few fixed UI
literals are rewritten from the same table by apply_western_ui_literals.py.

Matching is a single left-to-right pass, longest phrase first, on whole words
(letters, digits and underscore are word characters), so a Western name is
never re-translated and bare IDs such as water_silo stay canonical. Entries
marked prose_only apply only to strings containing a space.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Western presentation plan, "Holdings: expansion set"; the last six are
# provisional names chosen here because the list leaves them unnamed.
BOOMTOWN = {
    'gunsmith': 'Gunsmith', 'jailhouse': 'Jailhouse', 'robbers_roost': 'Robbers Roost', 'timber_ram': 'Timber Ram',
    'smuggler_s_landing': "Smuggler's Landing", 'rockslide_ridge': 'Rockslide Ridge', 'bounty_office': 'Bounty Office',
    'packer_s_cabin': "Packer's Cabin", 'revival_tent': 'Revival Tent', 'courthouse': 'Courthouse',
    'army_surgeon_s_tent': "Army Surgeon's Tent", 'wagon_fort': 'Wagon Fort', 'free_homestead': 'Free Homestead',
    'coal_yard': 'Coal Yard', 'gallows': 'Gallows', 'pawn_shop': 'Pawn Shop', 'crimp_house': 'Crimp House',
    'wanted_poster_board': 'Wanted Poster Board', 'boot_hill': 'Boot Hill', 'boarding_house': 'Boarding House',
    'quaker_settlement': 'Quaker Settlement', 'chuckwagon': 'Chuckwagon', 'pony_express_station': 'Pony Express Station',
    'dance_hall': 'Dance Hall', 'apothecary': 'Apothecary', 'cattlemen_s_club': "Cattlemen's Club",
    'vigilance_committee': 'Vigilance Committee', 'post_office': 'Post Office', 'nitro_works': 'Nitro Works',
    'rustlers_corral': "Rustlers' Corral", 'horse_trader': 'Horse Trader', 'lookout_ridge': 'Lookout Ridge',
}
PROVISIONAL = {'vigilance_committee', 'post_office', 'nitro_works', 'rustlers_corral', 'horse_trader', 'lookout_ridge'}
TROUBLE = {
    'run_out_of_town': 'Run Out of Town', 'cannonade': 'Cannonade', 'hard_winter': 'Hard Winter', 'box_canyon': 'Box Canyon',
    'poker_night': 'Poker Night', 'prairie_fire': 'Prairie Fire', 'cholera': 'Cholera', 'ambush': 'Ambush',
    'curfew': 'Curfew', 'gold_rush': 'Gold Rush', 'stampede': 'Stampede', 'hip_flask': 'Hip Flask',
}
# (source, target) in lower case; Title and UPPER forms are generated.
# Phrases come first only for readability; matching is always longest-first.
GENERIC = [
    ('gain a punk', 'hire a drifter'), ('gains a punk', 'hires a drifter'), ('gain punks', 'hire drifters'),
    ('an event', 'a Trouble'), ('event queue', 'fuse line'), ('events', 'Trouble'), ('event', 'Trouble'),
    ('an injured', 'a wounded'), ('injured', 'wounded'), ('injures', 'wounds'), ('injure', 'wound'),
    ('takes damage', 'takes a hit'), ('enemy damage', 'enemy fire'), ('first damage', 'first hit'),
    ('damages', 'hits'), ('damage', 'hit'),
    ('restored', 'patched up'), ('restores', 'patches up'), ('restore', 'patch up'),
    ('raids', 'spooks the herd'), ('raid', 'spook the herd'),
    ('unprotected', 'exposed'), ('protected', 'covered'), ('protection', 'cover'), ('protecting', 'covering'),
    ('protects', 'covers'), ('protect', 'cover'),
    ('ruined', 'burned-out'), ('ruins', 'burned-out holdings'), ('ruin', 'burned out'),
    ('camps', 'holdings'), ('camp', 'holding'),
    ('people', 'crew'), ("person's", "crew member's"), ('persons', 'crew members'), ('person', 'crew member'),
    ('punks', 'drifters'), ('punk', 'drifter'),
    ('water', 'whiskey'), ('silo', 'flask'),
    ('junked', 'hocked'), ('junks', 'hocks'), ('junk', 'hock'),
    ('wasteland', 'territory'), ('crews', 'outfits'),
]
# Words that read the same either way stay out of the table entirely.
UNCHANGED_NAMES = {'Vigilante', 'Bounty Office'}
# Product names; Title and UPPER forms only, so paths such as launch_oldwest
# (underscore is a word character) are never touched.
APP_NAME = 'Battle of the Old West'
EXPANSION_NAME = 'Boomtown'
PRODUCT_NAMES = {'Cult of Chrome': EXPANSION_NAME}


def catalog():
    return {c['id']: c for c in json.loads((ROOT / 'game/data/cards.json').read_text())['cards']}


def crew_names():
    text = (ROOT / 'game/OldWest/Source/OldWestGame/Private/OldWestCrewCatalog.h').read_text()
    rows = re.findall(r'\{"([a-z_]+)", (\d+), "[^"]+", "([^"]+)"', text)
    names = {}
    for canonical, copy, name in rows:
        names.setdefault(canonical, {})[int(copy)] = name
    return names


def forms(source, target):
    """Title, UPPER and lower variants; the lower form is prose-only."""
    title = lambda s: s[:1].upper() + s[1:]
    return [(title(source), title(target), False), (source.upper(), target.upper(), False), (source, target, True)]


def table():
    import sys
    sys.path.insert(0, str(ROOT / 'scripts'))
    from holdings_roster import HOLDINGS
    cards = catalog()
    entries = {}

    def add(source, target, prose_only=False):
        if source in entries and entries[source][0] != target:
            raise ValueError(f'conflicting translation for {source!r}: {entries[source][0]!r} vs {target!r}')
        entries[source] = (target, prose_only)

    names = {}
    for cid, (_slug, western, *_rest) in HOLDINGS.items():
        names[cid] = western
    names.update(BOOMTOWN)
    names.update(TROUBLE)
    crew = crew_names()
    for cid, copies in crew.items():
        listed = [copies[k] for k in sorted(copies)]
        names.setdefault(cid, ' / '.join(listed))
    names['punk'] = 'Drifter'
    camps = [c for c in cards.values() if c['type'] == 'camp']
    assert all(c['id'] in names for c in camps), [c['id'] for c in camps if c['id'] not in names]
    assert all(c['id'] in names for c in cards.values() if c['type'] in ('event', 'resource', 'person')), \
        [c['id'] for c in cards.values() if c['id'] not in names]
    for cid, western in names.items():
        canonical = cards[cid]['name'] if cid in cards else 'Punk'
        if canonical in UNCHANGED_NAMES or canonical == western:
            continue
        add(canonical, western); add(canonical.upper(), western.upper())
    add('Karli', 'Quanah'); add('KARLI', 'QUANAH')
    # Indefinite articles follow the Western name ("an Obelisk" -> "a Land Office").
    vowel = lambda word: word[:1].lower() in 'aeiou'
    for cid, western in names.items():
        canonical = cards[cid]['name'] if cid in cards else 'Punk'
        if canonical in UNCHANGED_NAMES or canonical == western or vowel(canonical) == vowel(western):
            continue
        before, after = ('an', 'a') if vowel(canonical) else ('a', 'an')
        add(f'{before} {canonical}', f'{after} {western}')
        add(f'{before.capitalize()} {canonical}', f'{after.capitalize()} {western}')
        add(f'{before.upper()} {canonical.upper()}', f'{after.upper()} {western.upper()}')
    # Product names. The app is Battle of the Old West (the project owner, October 14,
    # 2026); the expansion holdings set is provisionally called Boomtown.
    for source, target in PRODUCT_NAMES.items():
        add(source, target); add(source.upper(), target.upper())
    # The action hub shares a name with the Command Post camp; UI literals for
    # the hub say Ledger directly, so the filter can map the camp name safely.
    for source, target in GENERIC:
        for s, t, prose in forms(source, target):
            if s in entries:
                continue
            add(s, t, prose)
    # Western names and crew identities map to themselves so a shorter
    # canonical word inside them (Gunner in Gatling Gunner) is never touched.
    protected = set(names.values()) | {n for c in crew.values() for n in c.values()}
    for name in protected:
        for variant in (name, name.upper()):
            if variant not in entries:
                entries[variant] = (variant, False)
    rows = sorted(entries.items(), key=lambda item: (-len(item[0]), item[0]))
    return [(s, t, p) for s, (t, p) in rows], names


WORD = re.compile(r'[A-Za-z0-9_]')


def translate(text, rows=None):
    """Python mirror of OldWestDisplay::Text, for literals and tests."""
    if rows is None:
        rows, _ = table()
    if text.startswith('{') or text.startswith('['):
        return text
    prose = ' ' in text
    out, i = [], 0
    while i < len(text):
        if i == 0 or not WORD.match(text[i - 1]):
            for source, target, prose_only in rows:
                if prose_only and not prose:
                    continue
                if text.startswith(source, i):
                    end = i + len(source)
                    if end == len(text) or not WORD.match(text[end]):
                        out.append(target); i = end
                        break
            else:
                out.append(text[i]); i += 1
            continue
        out.append(text[i]); i += 1
    return ''.join(out)


def c_string(value):
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def generate():
    rows, names = table()
    path = ROOT / 'game/OldWest/Source/OldWestGame/Private/OldWestWesternTerms.inl'
    body = '\n'.join(f'    {{{c_string(s)}, {c_string(t)}, {"true" if p else "false"}}},' for s, t, p in rows)
    path.write_text('// Generated by scripts/western_terms.py. Longest source first.\n' + body + '\n')
    (ROOT / 'game/data/western-terms.json').write_text(json.dumps(
        {'provisional_names': sorted(PROVISIONAL), 'card_names': names,
         'app_name': APP_NAME, 'expansion_name': EXPANSION_NAME,
         'rows': [{'from': s, 'to': t, 'prose_only': p} for s, t, p in rows]}, indent=2, ensure_ascii=False) + '\n')
    return rows


if __name__ == '__main__':
    rows = generate()
    print('WESTERN_TERMS', len(rows), 'rows')
    for sample in ['Damage an unprotected enemy camp', 'Discard a non-Silo card; gain a punk or 1 water',
                   'Use Cannon', 'Saloon', 'Adrenaline Lab', 'Gatling Gunner', 'Gunner', 'hip_flask',
                   'Destroy this camp and all people', 'YOUR EVENTS', 'Restore and ready one of your damaged people',
                   'Raiders', 'Play a card, use an ability, or visit the Ledger for all actions.']:
        print(f'{sample!r:60} -> {translate(sample, rows)!r}')
