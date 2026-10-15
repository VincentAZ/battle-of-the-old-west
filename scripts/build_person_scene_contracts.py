#!/usr/bin/env python3
"""Inventory every catalog person into explicit, unimplemented scene contracts.

This documents authored direction and current public-rule evidence. It neither
changes rules nor claims that a proposed prop, animation or scene is implemented.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'game/data/cards.json'
RULES = ROOT / 'game/OldWest/Source/OldWestGame/Private/Core/OldWestRules.cpp'
OUT = ROOT / 'art/cinematics/person_scene_contracts.json'


def scene(outcome, performer, response, camera, assets, logs, special=None):
    return dict(actual_public_outcome=outcome, performer_action=performer, target_response=response,
                camera=camera, required_authored_assets=assets, public_result_kinds=logs,
                special_constraints=special or [], implementation_status='proposed; no native acceptance yet')


SCENES = {
    'bounty_hunter': [scene(
        'Destroy the legally selected unprotected enemy person.',
        'Drop into a compact crouch, draw a suppressed sidearm, settle the wrist and fire one deliberate shot; holster only after the target response.',
        'The chosen public person takes the impact and enters the existing natural ragdoll. Other people remain unharmed.',
        'Low three-quarter close view establishes hood, pistol and selected victim; cut along the same sight line to the actual impact and full settling body.',
        ['suppressed sidearm with trigger/grip sockets', 'crouch-draw-aim-fire-recover clip', 'brief muzzle gas and casing'], ['destroy'],
        ['Do not run a melee lunge across the whole arena or pass through a camp.', 'A single selected victim, not a generic multi-target burst.'])],
    'hellfire_preacher': [scene(
        'Destroy the selected friendly sacrifice, then damage the separately selected enemy card.',
        'Plant a wired detonator, give a deliberate signal toward the public sacrifice and release its charge; then shoulder a scavenged launcher toward the enemy.',
        'First show the selected ally falling; only the later confirmed target receives the enemy impact. Keep the two causal steps distinct.',
        'Triangular staging: leader and ally in the first frame, target-side impact in the second; hold any person death to the strict natural-settling contract.',
        ['wired detonator', 'scavenged launcher', 'signal and trigger clips'], ['destroy', 'damage'],
        ['Do not reveal the identity beneath a sacrificed punk.', 'A pending target choice interrupts between resolved steps, never invent its selection.'])],
    'pinkerton_agent': [scene(
        'Damage the selected legal enemy card; activation is available only while the opponent has a queued event.',
        'Consult a battered radio receiver, react to the incoming-event signal and raise a flare-marked carbine for the shot.',
        'Only the confirmed target takes damage or a lethal transition. The queue remains in place during this activated ability.',
        'Receiver close-up with the actual public queued equipment in the background, then a sight-line cut to the target.',
        ['radio receiver with needle', 'listen-alert-aim-fire clip', 'carbine attachment'], ['damage', 'destroy'],
        ['The entry queue push is a separate trait; do not repeat it on every activation.'])],
    'regulator': [scene(
        'Destroy every currently damaged enemy person included in the authoritative outcome.',
        'Lower a mechanical range visor, scan only the public damaged targets and fire a short indexed burst at each one.',
        'All actual victims fall within one coordinated impact montage. Healthy enemy people have no hit response.',
        'Visor/weapon preparation, then a broad frame containing the entire victim set; individual cuts may clarify an occluded fall while preserving their shared timing.',
        ['range visor', 'compact automatic weapon', 'scan and multi-target burst clip'], ['destroy'],
        ['No speculative target highlighting before the authoritative target set is available.'])],
    'gatling_gunner': [scene(
        'Apply the authoritative injury/damage result to all unprotected enemy people; any resulting destruction is shown as logged by the current rules.',
        'Brace a heavy machine gun against the shoulder, spread the stance and traverse its barrel across the actual exposed-person arc with sustained recoil and a moving feed belt.',
        'Each public victim reacts at its assigned burst beat; protected people and camps are untouched. Lethal victims use the unchanged ragdoll path.',
        'Start over the gunner shoulder so the weapon and target line share a frame; widen to all actual victims, with muzzle and impact timing linked.',
        ['heavy machine gun with barrel/trigger/foregrip sockets', 'belt and casing props', 'braced sweep-fire clip'], ['damage', 'destroy'],
        ['Do not use a rifle-idle plus a lever as the ability.', 'Do not turn this into camp damage or attack protected people.', 'Camera placement must keep all victim silhouettes visible.'])],
    'widow_with_a_shotgun': [scene(
        'Damage the selected legal enemy card.',
        'Use a nearby ruin edge as a low brace, work an improvised shotgun action and fire from a compact defensive stance.',
        'The selected card takes one actual damage transition; debris comes from its visible surface.',
        'Low cover-side camera establishes the improvised brace, then cuts toward the enemy impact without placing the lens inside the ruin.',
        ['improvised shotgun', 'low-brace and pump-action clips'], ['damage', 'destroy'],
        ['Reduced deployment cost in a ruined-camp column is a rule modifier, not an extra attack.'])],
    'quanah_parker': [scene(
        'Damage the selected legal enemy card.',
        'Give a sharp forward hand signal, bring a compact assault weapon to the shoulder and deliver a controlled burst while maintaining command posture.',
        'The chosen target reacts once. Nearby allies may acknowledge the signal but receive no fabricated extra attack or readiness change.',
        'Medium frontal command beat followed by an over-shoulder target shot; preserve recognizable face and upper-body silhouette.',
        ['compact assault weapon', 'command-signal and controlled-burst clips'], ['damage', 'destroy'])],
    'claim_jumper': [scene(
        'Damage the selected card; draw one private card only if an actual camp was hit.',
        'Fire a rugged bolt launcher, then operate a short recovery winch only after a camp impact is confirmed.',
        'The actual target takes damage. For a camp hit, a sealed recovered supply case reaches the looter; a person hit produces no delivery.',
        'Launcher-to-target setup, then follow the public camp salvage delivery back toward the source.',
        ['bolt launcher and reel', 'aim-fire-recover clip', 'sealed salvage case'], ['damage', 'destroy', 'draw_card'],
        ['Never display the identity of the drawn card to the opponent.'])],
    'augustus_powder_pike': [scene(
        'Damage every card in the selected enemy column, using the authoritative list and condition transitions.',
        'Plant a heavy launcher, sight down the chosen column and send a single breaching round along that lane.',
        'The explosion travels through the actual selected column: people react and the camp takes its public damage state; adjacent columns remain untouched.',
        'Longitudinal lane composition includes foreground people and the rear camp; retain the whole result before any tighter follow-up.',
        ['heavy breaching launcher', 'plant-sight-fire clip', 'lane-local shock and debris effect'], ['damage', 'destroy'],
        ['A column attack may hit protected cards in that selected column; the presentation does not recompute targets.'])],
    'con_man': [scene(
        'Invoke the legally chosen eligible person ability, paying its actual cost and showing its resulting public effects.',
        'Observe the public copied performer, adjust a modular device and reproduce that ability through an explicitly matched performer variant.',
        'Use the copied ability contract for the actual result; Con Man remains the acting figure and the copied person is not spuriously exhausted or animated as the attacker.',
        'Brief Mimic-to-copied-person visual reference, then source-to-result staging from Mimic.',
        ['modular mimic device', 'observe-configure clip', 'compatible variants of copied ability clips'], ['ability'],
        ['Requires public copied source and chosen ability index; source identity alone is ambiguous for people with multiple abilities.', 'Do not inspect hidden punk faces to determine what was copied.'])],
    'cornelius_ashby_railroad_baron': [scene(
        'Destroy the selected enemy camp, ignoring its protection as the authoritative ability permits.',
        'Lock a shaped-charge projectile into a shoulder launcher, take a heavy braced stance and fire above the intervening frontline.',
        'Only the selected camp collapses through its authored destruction scene. People in front are not given invented hits.',
        'Low launcher shot followed by a clear exterior camp view that includes the complete collapse bounds.',
        ['shaped-charge launcher', 'load-brace-fire clip', 'camp contact charge effect'], ['destroy'])],
    'bartender': [scene(
        'Gain exactly one water.',
        'Unfold a carried hand-pump/filter, connect a jerrycan and perform one visible pumping cycle with the support hand stabilizing the hose.',
        'A single supported can fills or is delivered; the public water gain is the only gameplay result.',
        'Waist-height three-quarter view includes both hands, pump and receiving can; keep the tall storage behind the action.',
        ['portable hand pump and filter', 'hose with fitted endpoints', 'pump cycle clip', 'one water can'], ['water'])],
    'doc_holliday': [scene(
        'Resolve the optional enemy damage and optional restore of another friendly card in order, then damage Doc Holliday itself.',
        'Open a pressurized chemical rig, discharge the chosen offensive or restorative module and visibly strain against the rig as its final self-cost lands.',
        'Show only selected confirmed effects; finish on Doc Holliday stagger or natural death when self-damage is lethal.',
        'Keep the rig and Doc Holliday established between target cuts; the final return to the performer makes the unavoidable self-cost visible.',
        ['pressure rig with independent attack/medical valves', 'valve and strained-release clips', 'target-specific treatment/discharge props'], ['damage', 'restore', 'destroy'],
        ['Skipping an optional effect must not animate that omitted result.', 'The final self-damage remains visible even if both optional effects are skipped.'])],
    'barn_burner': [scene(
        'Damage the selected unprotected enemy camp.',
        'Prime a pressurized flame projector, brace its nozzle and release a short controlled incendiary burst toward the actual camp surface.',
        'Localized fire contacts the selected camp exterior, followed by its actual damaged or ruined condition; surrounding people are unaffected.',
        'Nozzle and camp share the attack axis, then a close exterior impact shot; flame stays outside building walls.',
        ['flame projector with hose and nozzle sockets', 'prime-brace-burst clip', 'surface-local flame and smoke'], ['damage', 'destroy'])],
    'ringleader': [
        scene('Gain and legally place one hidden punk.',
              'Raise a battered rally horn, blow one call and beckon toward the chosen clear arrival route.',
              'Exactly the new public Punk enters its chosen position; never reveal its hidden card face.',
              'Leader gesture opens toward the entrance path, then follow the arriving anonymous figure.',
              ['rally horn', 'call-and-beckon clip'], ['enter']),
        scene('Damage the selected legal enemy card while the player has a punk.',
              'Direct the existing rabble with a broad arm signal, then fire an improvised pistol while the squad holds cover.',
              'The selected target takes the authoritative hit; the enabling punk is not sacrificed or exhausted by invented staging.',
              'Include the source and public punk support in the initial composition, then cut to the confirmed target.',
              ['improvised pistol', 'rally-point-fire clip'], ['damage', 'destroy'])],
    'blacksmith': [scene(
        'Restore the selected other damaged friendly card.',
        'Deploy the mechanical tool arm and fitted treatment head; brace against the camp exterior or apply a medical patch to the person without intersecting the target mesh.',
        'The actual target transitions from damaged to restored at the tool-contact beat. Person treatment and structural repair use different tool heads and effects.',
        'Low mechanical close-up shows jointed robot arms and real contact, then enough target silhouette to read its restored condition.',
        ['telescopic tool-arm animation', 'welder head and medical head', 'contact sparks or sealed dressing'], ['restore'],
        ['Blacksmith stays visibly mechanical and unarmed for this ability.', 'Entry restore is optional and separate from a paid later activation.'])],
    'sarah_winnemucca': [scene(
        'Return the selected friendly person to its owner hand, clearing damage according to the rules.',
        'Unclip a rescue sling, signal the subject and guide it onto a collision-checked withdrawal route; if the source rescues itself, use a self-evacuation variant.',
        'The selected public figure leaves its old position and disappears only after reaching the exit staging point; no death reaction.',
        'Two-person staging when distinct, then follow the withdrawing person; preserve the lane geography and avoid walking through camps.',
        ['rescue sling', 'guide/assist and self-withdrawal clips'], ['return'],
        ['Do not display the private hand afterward.', 'Return can target the Sarah Winnemucca itself.'])],
    'prospector': [scene(
        'Reveal and discard three actual deck cards, then resolve at most the legally chosen junk effect; a depleted deck may end the match sooner.',
        'Holster the firearm, open a carried field-analysis case, pull three actual revealed salvage samples into separate trays, inspect them with a scanner and route only the chosen sample through its output module.',
        'The public revealed identities/junk symbols may label sample trays after revelation. The selected output causes its real water, draw, raid, injury, punk or restore result; unused samples fall into the discard receptacle.',
        'Close view includes scientist hands, scanner and three trays; switch to the chosen output target, returning to the emptied work surface when appropriate.',
        ['field-analysis case with hinged lid', 'three sample trays and scanner', 'open-sort-scan-select-reject clips', 'junk-output module variants'],
        ['reveal_discard', 'water', 'draw_card', 'raid_launch', 'event_advance', 'event_resolve', 'damage', 'destroy', 'enter', 'restore'],
        ['The current public ability log lacks the chosen ability index, though Prospector has one printed ability.', 'Use only actual revealed count and selected effect; do not assume three cards remain or animate an unchosen junk result.', 'A tiny exterior lever and idle rifle are not an accepted Prospector scene.'])],
    'rustler': [scene(
        'Launch Stampede, advance existing Stampede, or resolve them immediately as the actual public rule outcome dictates.',
        'Kneel, consult a route map, signal with a compact flare and wave the public Stampede onto their route.',
        'Use the existing public Stampede figure at its actual queue position; its movement or eventual defender-selected camp hit supplies the result.',
        'Rustler map/flare preparation, then follow the real Stampede route; do not cut to unrelated camp damage before a target is chosen.',
        ['route map', 'flare launcher', 'kneel-signal-wave clip'], ['raid_launch', 'event_advance', 'event_resolve', 'damage', 'destroy'])],
    'annie_oakley': [scene(
        'Damage the selected enemy person or camp regardless of protection.',
        'Set a bipod-supported precision rifle, settle breathing, make a small scope adjustment and fire one measured round.',
        'Only the confirmed target reacts, including a protected target when selected legally; no intervening person is accidentally hit.',
        'Close scope/trigger preparation and a long sight-line composition, followed by an unobstructed target impact view.',
        ['scoped rifle with bipod and correct hand sockets', 'set-breathe-aim-fire clip'], ['damage', 'destroy'])],
    'duelist': [scene(
        'Damage the chosen enemy card, then let the opponent choose a legal counter-damage target.',
        'Advance one braced step behind a battered shield, fire and visibly brace for the enemy reply after its choice resolves.',
        'Show the initial enemy impact, then the opponent-selected counter target taking damage; the response does not automatically hit Vanguard.',
        'Establish attack direction, then reverse the screen direction for the actual counterattack without losing the two sides.',
        ['battered shield and short carbine', 'advance-fire-brace clip'], ['damage', 'destroy'],
        ['Keep the response choice available after queued preparation ends.', 'Entry gain of a punk is a separate trait.'])],
    'charles_goodnight': [scene(
        'Injure the selected unprotected enemy person, using the actual logged damage/destruction result.',
        'Take a balanced duelist stance, make one precise sidearm shot and visibly re-cock the mechanism when the public readiness state permits another use.',
        'The actual target reacts once; continued readiness is shown by recovery into a prepared stance, not an invented second attack.',
        'Medium side view keeps the hand mechanism readable, followed by the selected person impact.',
        ['distinct duelist sidearm', 'precision-fire and rapid-recock clips'], ['damage', 'destroy'])],
    'vigilante': [scene(
        'Injure the selected unprotected enemy person, using the actual logged damage/destruction result.',
        'Draw a worn revolver from low ready, square the shoulders and fire a single sharp shot before lowering the wrist.',
        'Only the selected person takes a hit, with the normal damaged stance or natural fall.',
        'Low holster-to-muzzle framing then a clean medium target view; distinguish the quick draw from Annie Oakley setup and Gatling Gunner suppression.',
        ['worn revolver and holster', 'quick-draw-fire-lower clip'], ['damage', 'destroy'])],
    'civil_war_veteran': [scene(
        'Damage the selected legal enemy card.',
        'Brace a carbine with the stronger arm, manage a visibly painful weight shift and fire from a determined supported stance.',
        'The selected target receives the actual hit; the performer is not given additional self-damage by this activated ability.',
        'Close side view makes the support and injured posture visible, then the target response.',
        ['carbine with support strap', 'injured-brace-fire clip'], ['damage', 'destroy'])],
    'poker_alice': [scene(
        'Draw three cards, then discard three legal non-Silo cards from the hand, unless the actual draw ends the game earlier.',
        'Open an intelligence satchel, receive three sealed packets, sort them close to the chest and feed the three selected discards into a secure burn chute.',
        'Drawn identities remain private; only publicly confirmed discarded identities may become visible. Show the actual number received and discarded.',
        'Hands, satchel and supported packets fill a medium close view; follow the discarded packets into the chute without exposing the remaining hand.',
        ['intelligence satchel', 'sealed packets and burn chute', 'receive-sort-discard clips'], ['draw_card', 'discard'],
        ['Do not show all three incoming card faces to the opponent.', 'The first-event delay trait is separate from this draw/discard activation.'])],
}

TRAITS = {
    'wyatt_earp': ['On entry, signal one new anonymous punk along its selected clear deployment route.',
                   'Its granted Damage ability is index100 on eligible friendly people. Each performer needs a compatible single-hit weapon/tool variant; Argo must not fire on their behalf.'],
    'pinkerton_agent': ['Entry pushes only actual movable enemy queue objects one slot back. Show reverse equipment movement tied to public before/after queue slots.',
                  'Current Core push_queue changes public positions without an event_advance log; 29 log-family coverage does not prove this entry effect is animated.'],
    'widow_with_a_shotgun': ['When legally entering a ruined-camp column, use the ruin-aware arrival/cover stance. The reduced cost has no extra resource reward.'],
    'quanah_parker': ['People entering ready transition directly from their entrance to an alert stance; do not depict an extra free attack.'],
    'blacksmith': ['On entry, show the optional restore only after a legal target is confirmed; reuse the actual tool-contact treatment contract.'],
    'sarah_winnemucca': ['Ready-on-entry means an alert arrival posture, not an automatic withdrawal.'],
    'duelist': ['On entry, call one new anonymous punk; its position follows the actual placement choice.'],
    'charles_goodnight': ['The first ability use preserves readiness for affected friendly cards. Recover their current performer into a ready pose without replaying the ability.'],
    'civil_war_veteran': ['Entry: receive one sealed draw packet, then visibly stagger into the actual damaged condition. Do not collapse a surviving person.'],
    'poker_alice': ['The first played event uses its actual immediate slot, including Raiders. Avoid an invented queue wait or advance stage.'],
}


def main():
    catalog = json.loads(CATALOG.read_text())
    people = [card for card in catalog['cards'] if card['type'] == 'person']
    assert len(people) == 26
    assert set(SCENES) | {'wyatt_earp'} == {card['id'] for card in people}
    result = {
        'schema': 1,
        'scope': 'Explicit proposed performer scenes for all26 public person identities and all printed abilities; not implemented or screenshot-accepted coverage.',
        'priority_order': ['prospector', 'gatling_gunner', 'bounty_hunter'],
        'sources': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in (CATALOG, RULES, Path(__file__))},
        'source_locations': {
            'printed_ability_dispatch': 'OldWestRules.cpp activation() around lines393–417',
            'damage_and_destroy_results': 'OldWestRules.cpp lines120–135',
            'entry_traits': 'OldWestRules.cpp entryEffects() around lines365–373',
            'queue_push_without_log': 'OldWestRules.cpp push_queue around lines581–583',
            'scientist_public_reveals': 'OldWestRules.cpp mill_junk around lines637–640',
            'all_target_attacks': 'OldWestRules.cpp strafe/exterminate/magnus around lines611–618',
        },
        'global_acceptance': [
            'Show a distinct performer gesture with fitted prop and a corresponding actual target response; a card-name caption, idle rifle or generic exterior lever alone cannot pass.',
            'Use public source identity, chosen ability and actual public outcomes. Never inspect a private hand, deck, hidden punk face or opponent-only choice to direct a scene.',
            'An ability cue and subsequent results may form a causal montage. Preserve effect order, user-required choices and every authoritative result; only explicit Skip dismisses the remaining presentation.',
            'Every traveling person follows tested clearance paths and returns to its authoritative position. Presentation props remain non-colliding and cannot perturb the proven ragdoll rig.',
            'Keep current nonlinear/no-mass-conditioning/no-projection physics,16-body pose/velocity checks, sustained0.25s settling,6s cap and immediate Skip unchanged.',
            'Camera/lens must keep performer, contact point and actual victim set readable, with the existing compensated physical exposure and tactical focus restoration.',
            'Retain before/action/contact/after native screenshots, public revision/sequence and actual animation/prop transforms. Validate all applicable outcomes, optional skips and cancelled choices before claiming the contract accepted.',
        ],
        'required_public_dispatch_work': [
            'Current ability logs identify the performer and sometimes the copied source, but do not include the selected printed ability index. Multi-ability people and Con Man need an explicit public dispatch identifier or an equally unambiguous public action/result correlation before unique direction is reliable.',
            'Some public traits change queue positions/readiness without a dedicated action log. Their visible before/after state must be audited separately from the29 log families.',
            'The current shared standing/aim/fire clips and rifle props do not implement these distinct body mechanics. New character meshes alone are not evidence of unique abilities.',
        ],
        'people': [],
    }
    for card in people:
        contracts = SCENES.get(card['id'], [])
        assert len(contracts) == len(card['abilities']), card['id']
        entries = []
        for index, (ability, contract) in enumerate(zip(card['abilities'], contracts)):
            entries.append({'card_id': card['id'], 'ability_index': index,
                            'catalog_cost': ability['cost'], 'catalog_effect': ability['effect'], **contract})
        result['people'].append({'card_id': card['id'], 'name': card['name'],
            'printed_abilities': entries, 'catalog_trait': card.get('trait', ''),
            'entry_or_passive_scene_contracts': TRAITS.get(card['id'], []),
            'runtime_unique_animation_status': 'not validated; shared performer animation remains a known gap'})
    result['counts'] = {'person_identities': len(people), 'printed_ability_contracts': sum(len(card['printed_abilities']) for card in result['people']),
                        'additional_granted_ability_family': 'Argo Damage index100 on eligible friendly people'}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'output': str(OUT), **result['counts']}, indent=2))


if __name__ == '__main__':
    main()
