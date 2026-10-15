"""Generate the presentation-only Holdings catalog and History notes for the game.

Run: python3 -I scripts/generate_holdings_presentation.py

Writes OldWestHoldingsCatalog.h (camp id -> Unreal asset and history key) and
OldWestHoldingsHistory.inl (three compact lines per holding). Each note's
source title and URL come from the holding's validated historical evidence;
the visible lines are hand-written paraphrases of its sourced history lesson.
Canonical camp IDs, card text and rules are never changed.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from holdings_roster import HOLDINGS, REVIEW, catalog  # noqa: E402

PRIVATE = ROOT / 'game/OldWest/Source/OldWestGame/Private'
GAME = ROOT / 'art/western/holdings' / REVIEW.name.replace('review-', 'game-')

# camp id: (three display lines, URL substring of the evidence source they paraphrase)
NOTES = {
 'saloon': (["Newton, Kansas counted 27 saloons in 1871.", "A saloon was a plain storefront with a long bar,", "foot rail, spittoons and a back bar of bottles."], 'cowtowns'),
 'livery_barn': (["A livery hired out horses and buggies and", "sheltered travelers' teams. South Pass City's", "c.1868 livery was a windowless hewn-log barn."], 'wy0070'),
 'hot_springs': (["Early bathers used open seeps or crude sheds.", "By the 1880s small frame bathhouses held wooden", "tubs fed by troughs from the spring."], 'bathhouse-row'),
 'silver_mine': (["Late-1870s silver strikes spread hardrock mining", "across the West. Miners drove adits into hills,", "timbering each portal against cave-ins."], 'historycolorado'),
 'logging_camp': (["Logging camps were built of tree-length logs,", "chinked and roofed with boards. Ox and horse", "teams dragged logs on skid roads to the water."], 'Ryan_The-Buildings'),
 'stockyards': (["In 1867 Joseph McCoy built stockyards beside the", "Kansas Pacific at Abilene for Texas herds. Cattle", "went from the pens up chutes into stock cars."], 'archive.org'),
 'army_fort': (["Fort Larned guarded the Santa Fe Trail in Kansas.", "Timber was scarce, so it never had a stockade;", "its stone blockhouse became the guardhouse."], 'fort-larned-blockhouse'),
 'dynamite_shack': (["Western hardrock mines took up dynamite after", "1868 and kept it in a separate powder house", "with thick stone walls and a banded iron door."], 'parks.ca.gov'),
 'bunkhouse': (["Ranch hands slept in plain log bunkhouses. At", "the Mason-Lovell ranch, c.1883, they used pole", "bunks over dirt floors beside the cook shack."], 'mason-lovell'),
 'roundup_corral': (["Open-range cattle were rounded up each spring", "and fall. Roosevelt described a high circular", "corral with a snubbing post and a gate wing."], 'ranchlifehunting'),
 'cattle_ranch': (["A ranch headquarters had a house, bunkhouse,", "barns and rail corrals. Grant-Kohrs, Montana,", "ran its cattle from a hewn-log home ranch."], '890242'),
 'riverboat': (["Shallow sternwheel mountain boats ran the", "Missouri to Fort Benton until 1887. Snags sank", "many, including the Bertrand in 1865."], '69000138'),
 'railroad_work_camp': (["Transcontinental railroad crews of 1865-1869", "lived in tent camps beside the grade; a row of", "wall tents rose at Promontory in one week."], 'tent-city'),
 'toll_bridge': (["In 1865 a licensed company bridged the Snake", "River at Eagle Rock, Idaho, replacing a ferry.", "Such frontier toll bridges were timber-built."], 'history.idaho.gov'),
 'undertaker': (["Plains-town undertakers were often furniture", "makers. W. H. Eicholtz began building furniture", "and coffins in Abilene, Kansas, in 1870."], 'eicholtz'),
 'bordello': (["Western towns banned prostitution on paper but", "regulated it in practice; Waco, Texas licensed", "houses within a set district by 1889."], 'tshaonline'),
 'trading_post': (["John Lorenzo Hubbell opened his trading post at", "Ganado on the Navajo Reservation in 1878. Navajo", "weaving and silverwork became staples of trade."], 'hutr/learn/historyculture'),
 'land_office': (["Homesteaders filed claims and fees at a local", "land office. At Kingfisher in 1889 the office", "began in a tent on the afternoon of the run."], 'metadc229014'),
 'telegraph_office': (["The transcontinental telegraph was finished in", "October 1861, with relay stations about every", "20 miles along the line."], 'telegraph-crosses'),
 'stagecoach_station': (["Overland stage stations of the 1860s crossed", "southern Wyoming. Where timber was scarce, as at", "Point of Rocks, stations were built of stone."], 'point-rocks'),
 'railroad_depot': (["Kansas railroads built standard frame depots:", "waiting room, agent's office and freight room", "under one roof, beside a long platform."], '400bb84f'),
 'homestead_cabin': (["The 1862 Homestead Act offered 160 acres to", "families who lived on and farmed the land. In", "1867 George Palmer built a log cabin in Nebraska."], 'palmer-epard'),
 'gatling_emplacement': (["The Army took wheeled Gatling guns into the", "field; one went with Reno's column in June 1876.", "Troops under fire dug rifle pits."], 'little-bighorn'),
 'powder_magazine': (["Fort Missoula's 1878 powder magazine had", "two-foot rubble stone walls, one sheathed door", "and an earth-covered log ceiling."], 'mt0032'),
 'church_bell_tower': (["Frame churches followed families and railroads.", "Hailey, Idaho's 1886 Methodist church has its", "belfry tower set into the front gable."], 'Hailey_Methodist'),
 'salvage_yard': (["Denver papers reported on junk and scrap-iron", "dealers by 1879. Dealers sorted rags, bones,", "metal and paper in a yard for resale."], 'denverlibrary'),
 'artillery_battery': (["Frontier columns hauled light mountain", "howitzers by mule. At the Big Hole in 1877 Nez", "Perce warriors captured and dismantled one."], 'places/howitzer'),
 'general_store': (["A general store was among a frontier town's", "first businesses: display windows, counters,", "shelves, and a place for townsfolk to meet."], 'or0509'),
 'bare_knuckle_ring': (["Prize fights used London rules: a 24-foot turf", "ring of eight stakes and two ropes. Illegal", "title bouts were held in secret on open ground."], 'fistiana'),
 'breaking_pen': (["Ranches broke young horses in small round", "corrals of posts and rails, built around a", "single center snubbing post."], '94367800'),
 'barn_raising': (["Plains barns were heavy timber frames with", "pegged joints. Raising one took many hands, and", "barn raisings became neighborly social events."], 'Homesteading.pdf'),
 'rodeo_grounds': (["Pecos, Texas held prize cowboy contests in", "1883; Prescott charged admission in 1888.", "Wooden chutes and grandstands came later."], 'sharlothallmuseum'),
 'freight_warehouse': (["Busy rail towns built separate freight houses.", "Atchison's 1880 Santa Fe freight depot was stone,", "with freight doors onto a wooden dock."], 'natreg_listings/view/11'),
 'mountain_hideout': (["Outlaws hid at Hole-in-the-Wall, Wyoming, in", "the 1890s. The documented building there is a", "two-room log cabin built in 1883."], 'oldtrailtown'),
}


def c_string(value):
    assert all(32 <= ord(ch) < 127 for ch in value), ('ASCII only', value)
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def main():
    catalog()
    assert set(NOTES) == set(HOLDINGS)
    imported = json.loads((GAME / 'unreal-import.json').read_text())
    assert imported['ok'] and imported['existing_content_unchanged']
    entries, notes = [], []
    for card_id, (slug, name, *_rest) in HOLDINGS.items():
        export = json.loads((GAME / slug / 'export.json').read_text())
        asset = export['asset_name']
        assert imported['holdings'][slug]['card_id'] == card_id
        key = 'holding-' + slug
        entries.append(f'    {{{c_string(card_id)}, {c_string(asset)}, {c_string(key)}}},')
        lines, needle = NOTES[card_id]
        assert 2 <= len(lines) <= 3 and all(len(line.encode()) <= 52 for line in lines), (card_id, lines)
        evidence = json.loads((REVIEW / slug / 'historical-evidence.json').read_text())
        matches = [s for s in evidence['sources'] if needle in s['url']]
        # Colour-pass evidence appends sources after the originals; the note cites the original.
        assert matches, (card_id, needle)
        source = matches[0]
        title = source['title'].replace('—', '-').replace('–', '-').replace('’', "'").replace('‘', "'")
        title = ''.join(ch for ch in title if ord(ch) < 127)
        notes.append(f'    {{{c_string(key)}, {c_string(name)},\n     {'"' + chr(92).join(['']) + (chr(92) + 'n').join(c_string(line)[1:-1] for line in lines) + '"'},\n'
                     f'     {c_string(title)},\n     {c_string(source["url"])}}},')
    (PRIVATE / 'OldWestHoldingsCatalog.h').write_text(
        '#pragma once\n#include <string_view>\n\n'
        '// Generated by scripts/generate_holdings_presentation.py. Presentation only:\n'
        '// maps a canonical base camp ID to its static Western holding asset and its\n'
        '// History key. Rules, card text, saves and network data never read this.\n'
        'namespace OldWestHoldings\n{\nstruct FEntry\n{\n    const char* CampId;\n    const char* Asset;\n    const char* Key;\n};\n'
        'inline constexpr FEntry Entries[] = {\n' + '\n'.join(entries) + '\n};\n'
        'inline const FEntry* ForCamp(std::string_view CampId)\n{\n'
        '    for (const auto& Entry : Entries) if (CampId == Entry.CampId) return &Entry;\n    return nullptr;\n}\n}\n')
    (PRIVATE / 'OldWestHoldingsHistory.inl').write_text(
        '// Generated by scripts/generate_holdings_presentation.py from each holding\'s\n'
        '// validated evidence in art/western/holdings/review-v001. Paraphrased lines;\n'
        '// the full lessons and every source stay with the review assets.\n' + '\n'.join(notes) + '\n')
    print('HOLDINGS_PRESENTATION', len(entries), 'entries')


if __name__ == '__main__':
    main()
