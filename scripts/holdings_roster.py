"""Western Holdings roster for the 34 revised base camps.

Presentation-only mapping from the canonical camp IDs to the Western names in
Feedback/WESTERN_REBRAND.md ("Holdings: base camps"). Canonical IDs, card text,
costs and mechanics are never changed by this module. Footprints are game
presentation scale for the review stage, not claims about historical size.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# review-v002 is the full-colour pass requested on October 7, 2026 and is the default.
# review-v001 (retired muted pass) is a read-only record: OLDWEST_HOLDINGS_REVIEW=review-v001
# only to audit it, never to generate.
HOLDINGS_SET = os.environ.get('OLDWEST_HOLDINGS_SET', 'base')
if HOLDINGS_SET not in ('base', 'boomtown'):
    raise ValueError('OLDWEST_HOLDINGS_SET must be base or boomtown')
DEFAULT_REVIEW = 'expansion-review-v001' if HOLDINGS_SET == 'boomtown' else 'review-v002'
REVIEW = ROOT / 'art/western/holdings' / os.environ.get('OLDWEST_HOLDINGS_REVIEW', DEFAULT_REVIEW)
if HOLDINGS_SET == 'boomtown' and not REVIEW.name.startswith('expansion-review-'):
    raise ValueError('Expansion work must use an expansion-review-* directory to preserve base sources')
COLOUR_PASS = REVIEW.name != 'review-v001'

# canonical_card_id: (slug, western name, setting, footprint_m, brief rationale from the rebrand list)
HOLDINGS = {
    'saloon': ('dance_hall', 'Saloon', 'Town', 5.5, 'Whiskey gets a wounded man up for one more fight.'),
    'livery_barn': ('livery-barn', 'Livery Barn', 'Town', 6.0, 'Drifters bunk in the hayloft.'),
    'hot_springs': ('hot-springs', 'Hot Springs', 'Mountains', 5.0, 'One soak and he is back on his feet.'),
    'silver_mine': ('silver-mine', 'Silver Mine', 'Mountains', 5.5, 'The mine pays out, but it costs a miner.'),
    'logging_camp': ('logging-camp', 'Logging Camp', 'Timber', 6.0, 'Cuts its own timber to rebuild everything else.'),
    'stockyards': ('stockyards', 'Stockyards', 'Rail', 6.0, 'The pens feed the stampede and draw drifters.'),
    'army_fort': ('army-fort', 'Army Fort', 'Range', 6.5, 'The gun’s recoil shakes its own walls.'),
    'dynamite_shack': ('dynamite-shack', 'Dynamite Shack', 'Mountains', 4.0, 'The charge reaches past cover; the thrower does not come back.'),
    'bunkhouse': ('bunkhouse', 'Bunkhouse', 'Range', 5.5, 'The more drifters bunk there, the cheaper the muscle.'),
    'roundup_corral': ('roundup-corral', 'Roundup Corral', 'Range', 6.0, 'Cut a man out and put him where you want him.'),
    'cattle_ranch': ('cattle-ranch', 'Cattle Ranch', 'Range', 6.0, 'Its herd is the stampede.'),
    'riverboat': ('riverboat', 'Riverboat', 'River', 6.5, 'The one property that travels.'),
    'railroad_work_camp': ('railroad-work-camp', 'Railroad Work Camp', 'Rail', 6.0, 'A man is lost laying track, but the line gets fixed.'),
    'toll_bridge': ('toll-bridge', 'Toll Bridge', 'River', 6.5, 'Pay the toll or pay another way.'),
    'undertaker': ('undertaker', 'Undertaker', 'Town', 4.5, 'You inherit what was in his pockets.'),
    'bordello': ('bordello', 'Bordello', 'Town', 5.5, 'A busy night loosens tongues.'),
    'trading_post': ('trading-post', 'Trading Post', 'River', 5.5, 'Cheaper to outfit men here.'),
    'land_office': ('land-office', 'Land Office', 'Town', 4.5, 'File the last claim and the territory is yours.'),
    'telegraph_office': ('telegraph-office', 'Telegraph Office', 'Rail', 4.5, 'News speeds up every scheme, your rival’s too.'),
    'stagecoach_station': ('stagecoach-station', 'Stagecoach Station', 'Range', 5.5, 'Send riders out or tend the ones coming in.'),
    'railroad_depot': ('railroad-depot', 'Railroad Depot', 'Rail', 6.5, 'Gunmen step off the train shooting.'),
    'homestead_cabin': ('homestead-cabin', 'Homestead Cabin', 'Range', 4.5, 'The more you have lost, the harder it fights.'),
    'gatling_emplacement': ('gatling-emplacement', 'Gatling Emplacement', 'Range', 4.5, 'Plain firepower.'),
    'powder_magazine': ('powder-magazine', 'Powder Magazine', 'Mountains', 4.5, 'Blow it and everyone goes with it.'),
    'church_bell_tower': ('church-bell-tower', 'Church Bell Tower', 'Town', 5.0, 'One clean shot from the tower while the town holds its breath.'),
    'salvage_yard': ('salvage-yard', 'Salvage Yard', 'Rail', 5.5, 'Hock a card for a drifter or a drink.'),
    'artillery_battery': ('artillery-battery', 'Artillery Battery', 'Mountains', 5.5, 'Shells lobbed over the ridge; they decide what takes it.'),
    'general_store': ('general-store', 'General Store', 'Town', 5.5, 'Browse the shelves, keep what you need.'),
    'bare_knuckle_ring': ('bare-knuckle-ring', 'Bare-Knuckle Ring', 'Town', 5.0, 'One of yours fights one of theirs to the finish.'),
    'breaking_pen': ('breaking-pen', 'Breaking Pen', 'Range', 5.5, 'Greenhorns get broken in like broncs.'),
    'barn_raising': ('barn-raising', 'Barn Raising', 'Range', 6.0, 'When new hands arrive, everyone pitches in to rebuild.'),
    'rodeo_grounds': ('rodeo-grounds', 'Rodeo Grounds', 'Range', 6.0, 'Riders get hurt and herds get spooked.'),
    'freight_warehouse': ('freight-warehouse', 'Freight Warehouse', 'Rail', 6.5, 'Goods move out when the other side leaves a gap.'),
    'mountain_hideout': ('mountain-hideout', 'Mountain Hideout', 'Mountains', 5.5, 'The lookout fires whenever anything moves below.'),
}

# Rows the rebrand list marked "verify"; the actual catalog text is recorded so
# the chosen name can be judged against the real ability during review.
VERIFY_ROWS = {'livery_barn', 'stockyards', 'roundup_corral', 'toll_bridge', 'salvage_yard',
               'bare_knuckle_ring', 'breaking_pen', 'rodeo_grounds', 'freight_warehouse'}

if HOLDINGS_SET == 'boomtown':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from expansion_holdings_roster import HOLDINGS, MAPPING_REVIEW, PROVISIONAL_NAMES
    VERIFY_ROWS = set(MAPPING_REVIEW) | PROVISIONAL_NAMES


def catalog():
    cards = json.loads((ROOT / 'game/data/cards.json').read_text())['cards']
    camps = {c['id']: c for c in cards if c['type'] == 'camp'
             and (c.get('set') == HOLDINGS_SET if HOLDINGS_SET != 'base' else not c.get('set'))}
    count = 32 if HOLDINGS_SET == 'boomtown' else 34
    assert len(camps) == count and set(camps) == set(HOLDINGS), 'Holdings roster differs from the canonical camp set'
    assert len({v[0] for v in HOLDINGS.values()}) == count, 'Slugs must be unique'
    assert len({v[1].casefold() for v in HOLDINGS.values()}) == count, 'Western names must be unique'
    return camps


def ability_summary(card):
    parts = []
    if card.get('trait'):
        parts.append('Trait: ' + card['trait'])
    for ability in card.get('abilities', []):
        parts.append(f"Cost {ability['cost']}: {ability['effect']}")
    return ' | '.join(parts)


def holding_record(card_id):
    camps = catalog()
    slug, name, setting, footprint, rationale = HOLDINGS[card_id]
    card = camps[card_id]
    return {
        'slug': slug,
        'display_name': name,
        'canonical_card_id': card_id,
        'canonical_name': card['name'],
        'setting': setting,
        'footprint_m': footprint,
        'ability_summary': ability_summary(card),
        'starting_cards': card.get('starting_cards'),
        'rationale': rationale,
        'verify_row': card_id in VERIFY_ROWS,
        'status': 'brief_only',
        'scope': ('Static Western expansion skins and playable review integration, authorized October 8, 2026. '
                  'Final appearance approval remains separate; mechanics frozen.' if HOLDINGS_SET == 'boomtown'
                  else 'Static appearance only; no rig, animation or game integration before user approval.'),
        **({'mapping_review': MAPPING_REVIEW.get(card_id), 'provisional_name': card_id in PROVISIONAL_NAMES}
           if HOLDINGS_SET == 'boomtown' else {}),
    }


if __name__ == '__main__':
    for card_id in HOLDINGS:
        print(json.dumps(holding_record(card_id)))
