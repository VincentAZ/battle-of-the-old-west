# Western rebrand guardrails

## Mandatory documented historical accuracy — October 5, 2026

the project owner requires ALL rendering of ALL things to be historically accurate and
documented, and a factual history lesson for every person. This supersedes
the earlier practice of deferring historical research until asset approval.
Before rendering, establish the date, location, identity or archetype,
occupation, clothing, and equipment through authoritative references; record
what each source supports. Audit the resulting image and mesh against that
evidence. Clearly disclose reconstruction, uncertainty, and fictional composites.
Never fabricate a biography or treat a legend as an established fact.

For the current Crew audit, the project owner requests white male replacements where
fictional demographic choices have no historical support. Preserve documented
people and supported exceptions. A white male replacement still needs evidence
for his role, period clothing, and equipment. An unsuccessful search does not
prove a demographic group never occupied a role.

History content is mandatory for every person; the History link remains an
optional way for the player to read it. Keep sources with each note. Research
records live under `research/crew-history-audit/`; persistent agent instructions
live in `.cursor/rules/historical-accuracy.mdc`. Previous appearance approval
does not substitute for historical verification or the separate Native review.

## Crew appearance approval gate — October 5, 2026

the project owner requested static reskins for all 46 person-card copies and explicitly
prohibited new animation until he approves all 46. He clarified that all 46
copies must depict distinct people: no reused character, mesh or appearance,
including cards with identical mechanics. This supersedes the original brief's
seven shared pairs. The v002 pass retained 39 appearances and created seven
additional characters. The later historical audit authorizes versioned
corrections to unsupported appearances while preserving their original sources.
Preserve the three previously approved Native
appearances and the existing Drifter. All new assets remain unrigged and static.
Reference images alone do not satisfy the mesh appearance checkpoint.

Do not add rigs, animations, retargeting, playable imports or replacement
packages for this Crew pass before the complete appearance set is reviewed.
Existing approved in-game animations remain intact. Technical validation and
agent visual inspection do not constitute the project owner's approval. Sourced history
and documented historical accuracy are now required before rendering.

## Mechanics freeze

Do not change game mechanics until the entire Western rebrand is complete and
the project owner has approved the finished rebrand as a whole. This includes rules, card
effects, costs, timing, legal actions, AI behavior, card counts, canonical IDs,
save data, network payloads, and win conditions.

If the project owner asks for a mechanics change before that milestone, remind him of
this freeze and defer the request. Record the idea for later if useful, but do
not implement it. Presentation-only work remains allowed: models, textures,
animation, audio, display names, UI copy, icons, portraits, and other changes
that preserve authoritative gameplay exactly.

The freeze ends only when the project owner explicitly says the full Western rebrand is
complete and separately authorizes mechanics work.

On October 5, 2026, the project owner authorized the narrow cosmetic metadata exception
needed to integrate all three Native characters. A separate, visibility-filtered
sidecar tracks Lozen's Pinkerton Agent copy and Sarah Winnemucca's Sarah Winnemucca copy
through public-handle changes. Local presentation uses that sidecar for models,
portraits, names and history. Canonical rules snapshots, commands, save data,
catalogs, AI inputs, counts and mechanics remain frozen. This exception does not
end the mechanics freeze or authorize exposing face-down character identities.


## Mandatory asset history, optional viewing

the project owner requested this on October 4, 2026 and confirmed: “remember to add the
2-3 history line as each new assets is approved”. Every newly approved Western
asset must have a concise, sourced historical note of two or three display
lines as part of its approval/integration checklist. Start with approved
Western assets and extend coverage with every subsequent approved reskin.

Keep the note behind a discreet, optional History link in the asset inspector.
No automatic popups, hover expansions, gameplay interruptions or history on
ordinary action/UI controls. Keep rules and action selection unchanged. Notes
must describe the displayed asset; generic or fictional figures get clearly
identified real-world context. Face-down assets show only generic Drifter
history, never the hidden character's identity or history, including private
peek identities. Duplicate character variants need the same per-entity visual
resolver as their portraits before enabling a named historical note.

Retain source attribution with every note. Native names, artwork and historical
text remain subject to the brief's separate tribal review before art lock.

## Crew approval and integration authorization — October 5, 2026

the project owner explicitly approved all 46 appearances: “approved. rig and add to game.”
The appearance gate above is satisfied for the exact project hashes in
`art/western/crew/review-v003/appearance-approval.json`. Rigging, animation and
playable integration are authorized. Preserve approved geometry and sources;
keep mechanics frozen. Extend the existing cosmetic sidecar only as needed to
map all 46 distinct physical copies, preserving hidden-identity filtering and
authoritative gameplay state. Historical documentation remains mandatory.

## Holdings appearance gate — October 6, 2026

the project owner directed: “Continue with: 'Holdings: base camps' in Mixar - just the
skin, no rigging until I approve.” The 34 revised base camps receive static
Western holding skins named in the Western presentation plan. Historical
evidence with sources precedes every paid generation. No rigging, animation,
Unreal import, camp-scene replacement, package build or launcher change for
holdings until the project owner approves all 34 appearances. Canonical camp IDs, text,
costs and mechanics stay frozen; Western names are presentation labels only.
See `game/HOLDINGS_PILOT.md`. The v001 skins (`art/western/holdings/review-v001/`)
were generated with a retired muted-colour prompt and are superseded by the
full-colour pass in `review-v002/`.

## Art direction — full colour, October 7, 2026

the project owner, October 7, 2026: “I do not want muted colors. I want full color and a fun
historically accurate game that pops.” Never prompt, light, grade or texture for muted,
faded, washed-out or desaturated colour. History decides *which* colours; they are
rendered at full natural strength in clear warm light with readable contrast. Where
the documented material really is plain (unpainted weathered wood, bare earth), the
colour comes from documented neighbours (brick, paint, iron, canvas, grass, water,
soil) and the setting base, never from invented paint. Earlier briefs and records
that used muted wording are kept as history only and are not direction.

## Whiskey presentation — October 7, 2026

The canonical `water` resource is presented as whiskey: bottles, a hip flask,
bottle cases, kegs and barrels with sourced 1865-1890 forms
(`art/action_props/README.md`). Rules, counts, commands and saves are
unchanged. No whiskey appears in Native characters' presentation; deliveries
to or from them use plain trade crates.

## Playable completion pass — October 9, 2026

After the status report identified unfinished items 2–5 and the expansion
export hold, the project owner directed: “do it, do not be pendentic. we can imrpove and
twrek later which we will”. Continue expansion integration and deliver a
playable review package with the existing Trouble, regions and presentation
work. Usable first-pass art may retain documented cosmetic issues for later
refinement. The 34 base-holding appearance approvals and final/tribal review
remain the project owner's items 1 and 6; this is not final art approval. Mechanics,
hidden-identity filtering, approved Crew sources and historical provenance
remain protected.

## App name and zero visible leftovers — October 14, 2026

the project owner: “nuke every single left over and/or replace with updated terminology.
There should be no reason to show any at all. Also change the name of the app
to Battle of the Old West.”

- The player-visible name is **Battle of the Old West**: HUD header, window
  title (`ProjectDisplayedTitle`), start-menu tagline, bundled docs and the
  launcher `launch_battle_of_the_old_west.sh`.
- The expansion holdings set is shown as **Boomtown** (provisional name,
  `scripts/western_terms.py` `EXPANSION_NAME`).
- Any visible string must either be written in Western terms or pass through
  `OldWestDisplay::Text`. The term table also maps the original product names
  as a safety net. `Label()`/`Button()` do not translate; literals handed to
  them must already be Western.
- The in-game Rules panel has no Sources tab; bracketed citations are stripped
  on display. The source register stays in `rules-help.json` and `research/`.
- Packages bundle only player docs: player guide, remote play, playtest guide
  and template, third-party notices. Build notes, the research follow-up and
  the rules study are not shipped.
- Still internal, not visible to players, and unchanged: canonical card IDs,
  `cards.json` names, the Unreal project folder/module/target names, config
  section keys, command-line test flags, actor tags and the research files.
  Renaming the Unreal target and project is a separate structural task.

