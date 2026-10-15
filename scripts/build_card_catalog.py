#!/usr/bin/env python3
"""Build the runtime card catalog from the reviewed base-game definitions.

The ten redesigned holdings replace their original versions in this ruleset.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS = []

def key(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")

def add(name, kind, costs, effects, **fields):
    CARDS.append(dict(id=key(name), name=name, type=kind, **fields,
                     abilities=[dict(cost=c, effect=e) for c, e in zip(costs, effects)]))

# name | play cost | junk | ability costs | concise runtime explanation
PEOPLE = [
    ("Wyatt Earp",3,"punk",[1],["Hit"],"Your crew gain this card's 1-whiskey Hit ability. On entry, hire a drifter."),
    ("Bounty Hunter",1,"raid",[2],["Destroy an exposed enemy crew member"],""),
    ("Hellfire Preacher",1,"draw",[0],["Sacrifice one of your crew, then hit"],""),
    ("Pinkerton Agent",1,"draw",[1],["Hit if the opponent has a queued Trouble"],"On entry, you may push all enemy Trouble back one space where possible."),
    ("Regulator",1,"draw",[1],["Destroy all damaged enemy crew"],""),
    ("Gatling Gunner",1,"restore",[2],["Wound all exposed enemy crew"],""),
    ("Widow with a Shotgun",2,"raid",[1],["Hit"],"Costs 0 to play in a column with your burned-out holding."),
    ("Quanah Parker",3,"punk",[1],["Hit"],"Your crew enter ready, including Quanah."),
    ("Claim Jumper",1,"water",[2],["Hit; if a holding is hit, draw a card"],""),
    ("Augustus “Powder” Pike",3,"punk",[2],["Hit all cards in one enemy column"],""),
    ("Con Man",1,"injure",[0],["Copy a ready friendly or undamaged enemy crew member's ability; pay its cost"],""),
    ("Cornelius Ashby, Railroad Baron",4,"punk",[1],["Destroy any enemy holding"],""),
    ("Bartender",1,"injure",[0],["Gain 1 whiskey"],""),
    ("Doc Holliday",1,"injure",[0],["Hit and/or patch up another card, then hit this crew member"],""),
    ("Barn Burner",1,"injure",[1],["Hit an exposed enemy holding"],""),
    ("Ringleader",1,"raid",[1, 1],["Hire a drifter", "Hit if you have a drifter"],""),
    ("Blacksmith",1,"injure",[2],["Patch up another card"],"On entry, you may patch up another card."),
    ("Sarah Winnemucca",1,"injure",[0],["Return one of your crew to your hand"],"Enters ready."),
    ("Prospector",1,"raid",[1],["Discard 3 deck cards; you may use one of their hock effects"],""),
    ("Rustler",1,"water",[1],["Spook the herd"],""),
    ("Annie Oakley",1,"restore",[2],["Hit any enemy crew member or holding"],""),
    ("Duelist",1,"raid",[1],["Hit, then the opponent hits back"],"On entry, hire a drifter."),
    ("Charles Goodnight",3,"punk",[1],["Wound"],"Your cards remain ready after their first ability use this turn."),
    ("Vigilante",1,"raid",[1],["Wound"],""),
    ("Civil War Veteran",1,"injure",[1],["Hit"],"On entry, draw a card, then hit this crew member."),
    ("Poker Alice",3,"punk",[1],["Draw 3, then discard 3 non-Flask cards"],"Your first Trouble played each turn has delay 0, including Stampede."),
]
NAMED = {"Augustus “Powder” Pike", "Charles Goodnight", "Cornelius Ashby, Railroad Baron", "Poker Alice", "Quanah Parker", "Wyatt Earp"}
for name, play, junk, costs, effects, trait in PEOPLE:
    add(name,"person",costs,effects,play_cost=play,junk=junk,trait=trait,copies=1 if name in NAMED else 2)

EVENTS = [
    ("Run Out of Town",1,1,"raid","Destroy any enemy crew member."),
    ("Cannonade",4,3,"restore","Hit all enemy holdings; draw for each enemy burned-out holding."),
    ("Hard Winter",1,1,"injure","Each player keeps one crew member and destroys their other crew, starting with you."),
    ("Box Canyon",0,1,"water","Rearrange your crew. Enemy cards are exposed this turn."),
    ("Poker Night",1,0,"water","Draw 4, then discard 3 of those cards."),
    ("Prairie Fire",2,1,"restore","Destroy all crew in one enemy column."),
    ("Cholera",2,1,"raid","Wound all crew on both sides."),
    ("Ambush",2,0,"draw","Wound all exposed enemy crew."),
    ("Curfew",2,0,"injure","Return all crew, including drifters, to their owners' hands."),
    ("Gold Rush",1,2,"injure","Gain up to 3 drifters."),
]
for name, play, delay, junk, effect in EVENTS:
    add(name,"event",[],[],play_cost=play,event_delay=delay,junk=junk,effect=effect,copies=2)

# name, opening cards, activation costs, effects
CAMPS = [
    ("Saloon",1,[0],["Activate a damaged crew member, paying its ability cost, then destroy it"]),
    ("Livery Barn",1,[1],["Hire a drifter if you have at most one crew member"]),
    ("Hot Springs",1,[2],["Patch up and ready one of your damaged crew"]),
    ("Silver Mine",1,[0],["Sacrifice a crew member; gain 1 whiskey"]),
    ("Logging Camp",1,[0],["Hit this holding, then patch up any number of other cards"]),
    ("Stockyards",1,[2],["Spook the herd and hire a drifter"]),
    ("Army Fort",2,[2],["Hit if this holding is undamaged"]),
    ("Dynamite Shack",0,[2],["Hit any enemy card, then sacrifice one of your crew"]),
    ("Bunkhouse",1,[3],["Hit; costs 1 less for each of your drifters"]),
    ("Roundup Corral",1,[1, 2],["Move either player's crew member on its own side", "Spook the herd"]),
    ("Cattle Ranch",0,[1],["Spook the herd"]),
    ("Riverboat",0,[1],["Advance this holding; on the third advance, reset and the opponent destroys a holding"]),
    ("Railroad Work Camp",1,[0],["Sacrifice a crew member, then patch up another card"]),
    ("Toll Bridge",0,[2],["Hit any enemy holding if you have at least 4 crew"]),
    ("Undertaker",0,[0],["Sacrifice a crew member; draw a card"]),
    ("Bordello",1,[1],["Hit if at least 2 crew entered your play this turn"]),
    ("Trading Post",1,[],[]),
    ("Land Office",1,[],[]),
    ("Telegraph Office",1,[1],["Advance either player's Trouble one space if clear"]),
    ("Stagecoach Station",1,[2, 2],["Spook the herd", "Patch up another card"]),
    ("Railroad Depot",1,[0],["Play a crew member and use its ability, paying both costs, then hit it"]),
    ("Homestead Cabin",1,[3],["Hit; costs 1 less for each of your burned-out holdings"]),
    ("Gatling Emplacement",0,[2],["Hit"]),
    ("Powder Magazine",1,[2],["Destroy this holding and all crew"]),
    ("Church Bell Tower",1,[1],["Hit; this must be your only ability this turn"]),
    ("Salvage Yard",1,[0],["Discard a non-Flask card; hire a drifter or 1 whiskey"]),
    ("Artillery Battery",0,[1],["The opponent chooses one of their cards to hit"]),
    ("General Store",2,[2],["Draw 2, then discard one of those 2"]),
    ("Bare-Knuckle Ring",0,[1],["Sacrifice one of your crew; the opponent sacrifices one of theirs"]),
    ("Breaking Pen",2,[2],["Hit if this column has 2 crew"]),
    ("Barn Raising",2,[1],["Patch up another card if 2 crew entered your play this turn"]),
    ("Rodeo Grounds",1,[2, 2],["Wound", "Spook the herd"]),
    ("Freight Warehouse",1,[1],["Patch up another card if an enemy holding is exposed"]),
    ("Mountain Hideout",0,[1],["Hit if any Trouble resolved this turn"]),
]
TRAITS = {"Logging Camp":"This holding cannot be patched up.", "Army Fort":"Starts damaged.", "Trading Post":"Your crew cost 1 less to play into this column while it has no crew.", "Land Office":"Win when the last deck card is drawn while this holding survives."}
for name, start, costs, effects in CAMPS:
    add(name,"camp",costs,effects,starting_cards=start,trait=TRAITS.get(name,""))
add("Stampede","event",[],[],event_delay=2,effect="The opponent chooses one of their holdings to hit.",special=True)
add("Hip Flask","resource",[],[],junk="water",effect="Pay 1 to take into hand. Hock for 1 whiskey; return to supply.",special=True)

catalog = dict(schema_version=1, cards=CARDS, rulesets={
    "base_2024":dict(name="Base game · revised holdings", camp_ids=[key(c[0]) for c in CAMPS],
                     shared_deck=[dict(card_id=c["id"],copies=c["copies"]) for c in CARDS if "copies" in c],
                     rules_reference="Revised base holdings, 2026 rules baseline",
                     confirmed_rulings={"mimic_chains": "Confirmed ruling: copying another Con Man / Bass Reeves does not change perspective or unlock unready friendly crew."},
                     interpretation_policy={
                         "deck_exhaustion":"Check immediately after removing the final card. Land Office's actual-draw victory precedes the first reshuffle or second-exhaustion draw. An empty discard at first exhaustion ends in a draw.",
                     })},
    pending_rulesets=[])
assert len([c for c in CARDS if c['type']=='person']) == 26
assert len(CAMPS) == 34
assert sum(c.get('copies',0) for c in CARDS) == 66
assert len({c['id'] for c in CARDS}) == len(CARDS)
expansion_path=ROOT/'game/data/boomtown.verified.json'
if expansion_path.exists():
    expansion=json.loads(expansion_path.read_text())
    assert len(expansion['cards']) == 32
    for card in expansion['cards']:
        assert isinstance(card['starting_cards'],int)
        assert all(isinstance(a['cost'],int) for a in card['abilities'])
        catalog['cards'].append(card)
    base=catalog['rulesets']['base_2024']
    catalog['rulesets']['boomtown']=dict(
        name="Base + Boomtown · revised holdings",
        camp_ids=base['camp_ids']+[c['id'] for c in expansion['cards']],
        shared_deck=base['shared_deck'],
        rules_reference=base['rules_reference'],
        implementation_status='rules_tests_passed',
        confirmed_rulings=dict(base['confirmed_rulings'], **{"gas_station_zeto_priority": "Confirmed ruling: active Zeto makes the first Trouble played that turn delay 0, including a Coal Yard Stampede launch.", "rescue_post_punk_exception": "Confirmed ruling: a returned drifter may be replayed faceup this turn. Pony Express Station only restricts the returned faceup crew member and its copies.", "masquerade_batch_inspection": "Confirmed ruling: place all drifters from Wagon Fort or Gold Rush before inspecting the new faces."}),
        interpretation_policy=dict(base['interpretation_policy'], **{"mining_removed_ruin_counts": "Only burned-out holdings still on the battlefield count for Homestead Cabin, Widow with a Shotgun / Homestead Defender and Cannonade. A removed burned out does not patch up a holding life.", "black_market_controller_corner_case": "Follow the printed crew member scope: either side, provided the crew member is faceup and entered during this turn.", "guillotine_granted_abilities": "Gallows retains a destroyed drifter's granted Argo/Gunsmith attack for its final ability opportunity. This is a supported interpretation of the granted ability; the FAQ does not separately name this combination. Argo's own attack is printed on its card and requires no lost-trait exception."}),
        ruling_status="These explicit sequencing policies are game interpretations, not claims of a definitive designer ruling.")
    assert len(catalog['rulesets']['boomtown']['camp_ids']) == 66
target=ROOT/'game/data/cards.json'
target.parent.mkdir(parents=True,exist_ok=True)
target.write_text(json.dumps(catalog,indent=2,ensure_ascii=False)+'\n')
runtime=ROOT/'game/OldWest/Content/Data/cards.json'
runtime.parent.mkdir(parents=True,exist_ok=True)
runtime.write_text(target.read_text())
print(f"Wrote {len(catalog['cards'])} definitions; 66 shared-deck cards; 34 base + 32 expansion camps to {target}")
