# Holdings pilot — base camp static skins

> **Superseded direction:** the v001 pass described below used a prompt asking
> for “muted colors” and a bare-ground patch. That direction is retired; the
> current pass is the full-colour `review-v002` (see the colour section at the
> end). v001 files stay only as the record of what was generated.

the project owner directed on October 6, 2026: “Continue with: 'Holdings: base camps' in
Mixar - just the skin, no rigging until I approve.” This pass gives each of the
34 revised base camps the Western holding named under “Holdings: base camps”
in the Western presentation plan, as a static textured mesh only.

## Invariants

- Canonical camp IDs, names in catalogs, card text, costs, abilities, counts,
  AI inputs, saves and network payloads are unchanged. The Western names are
  presentation labels recorded in `scripts/holdings_roster.py`.
- Static skins only. No rig, animation, retargeting, Unreal import, camp-scene
  replacement, package build or launcher change until the project owner approves all 34.
- Every holding has dated, located, sourced historical evidence before any
  paid generation, and a factual two-to-three-sentence history lesson.
- Full colour: documented period colours at full natural strength, never muted
  or desaturated (the project owner, October 7, 2026: “I want full color and a fun
  historically accurate game that pops”). Each holding stands on its own
  irregular, setting-specific base; no generated ground slab.
- Footprint scale is game presentation, not a historical dimension claim.
- At most 30,000 triangles, one material, 2048×2048 packed textures, like Crew.
- Existing camp scenes, Crew, Native, Stampede and Drifter assets are protected
  by `art/western/holdings/review-v001/baseline.json` (11,238 hashed files).

## Local asset records

`art/western/holdings/review-v001/` is ignored by Git under the asset policy.
Each `SLUG/` directory holds `holding.json` (mapping, ability text, footprint),
`historical-evidence.json`, `reference-request.json`, `reference.png`,
`reference-review.json`, `model-request.json`, `original.glb` and `review/`
with the packed Mixar project, 2K textures, eight renders, `manifest.json`,
`validation.json`, `visual-review.json` and `historical-review.json`.
Mixar job state (`*.job.json`) and logs stay local and out of bundles.

`service-authorization.json` records the project owner's instruction and the credit
estimate (54 credits per holding, 1,836 for 34). `history-validation.json`
records the evidence check. `roster-status.json` and `index.html` are the
audit and gallery; `Holdings-Static-Contact-NN.jpg` are contact sheets.

## Workflow

Run from the repository root.

1. Research: write each `historical-evidence.json` (date and location scope,
   claim-specific sources, documented features, cited `documented_colors`,
   render brief ending with the full-colour `SUFFIX` from
   `validate_holdings_history.py`, history lesson, uncertainties). Then
   `python3 -I scripts/validate_holdings_history.py` fetches every cited URL.
2. `python3 -I scripts/author_holdings_requests.py` writes the paid requests
   once; the reference prompt is the sourced render brief itself.
3. `python3 -I scripts/run_holdings_generation_jobs.py reference submit|status|download`
   runs the serialized Mixar job protocol from `stampede_mixar_job.py`.
4. Inspect each `reference.png` against the evidence and write
   `reference-review.json`; only `accepted_for_static_mesh_generation` with the
   matching SHA-256 unlocks `run_holdings_generation_jobs.py model submit`.
5. Prepare and validate in the installed Mixar:

```sh
~/.local/bin/mixar --background --factory-startup --python-exit-code 1 \
  --python scripts/prepare_holdings_review.py -- --source SLUG/original.glb \
  --output SLUG/review --holding SLUG/holding.json [--heading-degrees N]
~/.local/bin/mixar --background --factory-startup --python-exit-code 1 \
  --python scripts/validate_holdings_review.py -- SLUG/review
```

6. Inspect all eight saved renders and write `visual-review.json`; compare the
   mesh with the evidence and write `historical-review.json` (matches,
   differences, remaining uncertainties).
7. `python3 -I scripts/build_holdings_review.py` audits everything and builds
   the gallery; `python3 -I scripts/bundle_holdings_review.py` packages it.

## Orientation and revisions

Tripo results face an arbitrary axis. Each `holding.json` records the
`heading_degrees` applied at import so the documented entrance or principal
face meets the −Y game front; the value was chosen from diagnostic renders and
corrected after inspecting the full eight-view set. Rejected references are
retained as `reference-v1-rejected.png` with `reference-review-v1.json`; the
revision is a new numbered request (`reference-v2-request.json`) so the first
paid job is never resubmitted. Two references were revised: Stockyards (the
office and scale house floated as detached pieces) and Bare-Knuckle Ring (six
stakes instead of the documented eight).

## Status — October 6, 2026

All 34 holdings are ready for the project owner's appearance review. Every holding has
validated evidence (2–4 fetched sources each), an accepted reference, a
validated static mesh (15,959–23,274 triangles, one material, three packed
2048×2048 maps), an eight-view visual inspection and a historical comparison.
`roster-status.json` reports `ready_for_all_34_appearance_review`, with all
11,238 protected files unchanged and the selected package untouched.
`Holdings-34-Static-Review.zip` and `bundle-manifest.json` package the set
without Mixar job state. Paid generation used 36 reference and 34 model jobs
(two reference revisions), about 1,916 credits.

## Playable review build — October 6, 2026

the project owner asked to see the holdings in game before deciding: “let's get them
into the game so I can judge” (`game-v001/review-integration-authorization.json`).
This is a review build, not final approval. Nothing is rigged or animated.

- `scripts/export_holdings_mixar.py` exports each validated review source to
  FBX without saving it, baking a 180° turn so the −Y Blender entrance lands
  on the camp's −Y Unreal front. `scripts/import_holdings_unreal.py` imports
  `/Game/Art/Western/Holdings/<Name>/` (mesh, material with the review's 0.3
  normal strength, 0.6 roughness floor and zero metallic, plus `Conditions/`
  soot and ruin variants). Existing Content stayed byte-identical.
- `UOldWestCampVisuals::Build` places the holding for each of the 34 base
  camps, scaled uniformly to fit the 6 m wide, 4.8 m deep lane (never
  enlarged). Damage applies the soot variant and puts fires on the actual roof
  surface; ruin applies the charred variant, timber debris along the front and
  sides, and the existing smoke. The authored wasteland scene remains only as a
  logged fallback if an asset is missing. Expansion camps are unchanged.
- The Western name and a three-line sourced note appear through the optional
  History link (`OldWestHoldingsHistory.inl`, generated by
  `scripts/generate_holdings_presentation.py`). Card names and rules text stay
  canonical, because the shared text filter would also rename rules prose and
  UI labels such as the Bunkhouse action hub.
- Package: `dist/linux-development-holdings-review-20261006/archive`, launched
  with `scripts/launch_holdings_review.sh`. After the project owner launched the normal
  game and saw no holdings, `dist/current` was pointed at this build so the
  normal launcher shows them (`game-v001/promotion.json`; rollback:
  `ln -sfn linux-development-crew-20261005 dist/current`). This is for review,
  not final approval. Holdings appear for the 34 base camps; the Boomtown
  ruleset also deals 32 expansion camps that this pass did not reskin.
- Burned-out holdings are the charred intact model with debris and smoke;
  bespoke collapsed geometry is not authored.

## Review criteria

Inspect the whole structure: roof, every facade, rear, underside, scale against
the 1.8 m crew, material response and readability at game-camera distance.
Judge the saved mesh renders, not the generation reference. Names the rebrand
list marked “verify” show the actual catalog ability in the gallery so the
chosen name can be judged; Toll Bridge (“Damage any enemy camp if you have
at least 4 people”) does not match the “Toll Bridge: pay the toll” rationale,
so that name is flagged for the project owner's decision rather than changed.

**Review checkpoint:** no rigging, animation, Unreal import or package until
the project owner approves all 34 appearances. Mechanics remain frozen throughout.

## Western terminology pass — October 6, 2026

the project owner asked why only card titles would change when everything will be
Western, and said “yes” to applying the full vocabulary. Presentation only:
canonical IDs, card data, commands, saves and network payloads are unchanged.

- `scripts/western_terms.py` is the single vocabulary: every holding (34 base,
  32 Boomtown), Trouble, Hip Flask, Drifter, crew card types (“Annie
  Oakley / Sharpshooter”; live copies already show their own person), and game
  words (camp→holding, people→crew, event→Trouble, water→whiskey, silo→flask,
  junk→hock, damage→hit, injure→wound, restore→patch up, raid→spook the herd,
  protected/unprotected→covered/exposed, ruin→burned out, wasteland→territory).
  It generates `OldWestWesternTerms.inl` and `game/data/western-terms.json`.
- `OldWestDisplay::Text` translates in one longest-first, whole-word pass, so
  translated names are never re-translated and bare IDs stay canonical. The
  battle history and unit captions now translate exactly once.
- `scripts/apply_western_ui_literals.py` rewrote 86 visible UI literals that
  bypass the filter, excluding lookup keys, comparisons, component names and
  generic UI resets. The action hub is now the Ledger.
- Provisional names (the list leaves these six Boomtown holdings
  unnamed): Vigilance Committee → Vigilance Committee, Post Office → Post Office, Laser
  Tower → Nitro Works, Rustlers' Corral → Rustlers' Corral, Horse Trader →
  Horse Trader, Lookout Ridge → Lookout Ridge. Toll Bridge is kept as listed.
- Not converted: the bundled PLAYER_GUIDE.md, rules study and the 32 Boomtown holding models (names only). UI test harnesses that look for old
  labels (for example “BUNKHOUSE”, “WATER”) need their expectations updated.

## Colour and base pilot (review-v002) — October 7, 2026

the project owner: “these ar bland as hell. I want: 1. color - what do they ACTUALLY look
like with color? 2. base - … a small perimeter around each one that reflects
their location … the base should not be the same shape in them all.”

- Cause: the retired v001 suffix asked for “muted colors” and “a small flat
  patch of bare ground”, so every holding came out tan with the same baked
  rectangular slab. The default `SUFFIX` in `validate_holdings_history.py` now
  asks for full rich period colour that reads as lively game art, with no
  ground under the structure. `review-v002` is the default review directory;
  v001 is a read-only record (`OLDWEST_HOLDINGS_REVIEW=review-v001` to audit
  it) protected by `review-v002/baseline.json` (12,379 hashed files).
- v002 evidence adds `documented_colors` with [Sn] citations (up to 10
  sources). Pilot: riverboat (white superstructure and black stacks,
  Chittenden 1903 and the 1874 Currier & Ives St. Louis print), homestead
  cabin (HABS NE-21: ridge flue, not the v001 brick chimney; brick gable
  nogging; grey-weathered bur oak) and saloon (painted and grained Dodge City
  saloons and painted window-panes are documented; the specific off-white,
  black sash and black-and-gold sign are flagged reconstruction).
- Bases: `scripts/holdings_base.py` builds an irregular outline seeded from
  the slug and stretched to the structure, a setting surface from
  `art/western/holdings/base-palettes.json` (River, Range and Town cited;
  Mountains, Rail and Timber provisional), and natural scatter. The rim fades
  into the board sand. River water is a separate object so Unreal can give it
  a moving material at integration.
- Pilot cost: 3 references + 3 models (about 162 credits). The other 31 and
  the Unreal base/water integration wait for the project owner's verdict on the pilot.

## Full-colour rollout and in-game bases — October 7, 2026

the project owner answered “yup!” to rolling the colour pass out to all 34 and
brightening the camp portraits (`review-v002/service-authorization.json`,
`rollout`).

- Research: six parallel batches by setting fetched new colour sources for the
  31 remaining holdings; `scripts/merge_holdings_colour_research.py` appends
  them to the v001 evidence (cap 10 sources), renumbers citations, moves
  uncited “reconstruction / not documented” lines into uncertainties and
  appends the full-colour suffix. Many briefs were corrected by the evidence,
  for example: Santa Fe depots “deep clay red”; Fort Missoula magazine of
  maroon and plum stone under white limewash; Model 1883 Gatling in a brass
  casing; Hubbell trading post without a parapet before about 1910; the Grant
  house white clapboard with green shutters (two storeys, flagged).
- `run_holdings_generation_jobs.py` now refuses a reference submission unless
  that holding's evidence passed validation and the request prompt equals the
  validated brief. Army Fort needed reference revisions v2-v5 (octagon,
  misplaced plaster, a second flagpole); all superseded files are kept.
- Every mesh was oriented from heading-0 diagnostics, validated, inspected in
  all eight views and compared with its evidence (`visual-review.json`,
  `historical-review.json`). Known mesh differences are recorded there and in
  `CURRENT.json` `flagged_for_user`.
- Bases (`scripts/holdings_base.py`, `base-palettes.json` with cited soil,
  plant, stone and water colours for all six settings): seeded irregular
  outline, setting colour in vertex RGB, rim fade in vertex alpha, natural
  scatter sized to read from the game camera. Per-holding overrides in
  `holding.json`: `base_colors` (prize-ring turf; Ganado red ground),
  `base_water` (`surround` for the boat and toll bridge, `behind` for the
  Hubbell post's wash), `base_scatter`.
- Unreal (`import_holdings_unreal.py`, game directory follows the review
  directory): `SM_HoldingBase_<Name>` with shared `M_HoldingBase` (setting
  colour given the board dirt's grain, fading into `T_dirt_diff_4k` at the
  rim) and `SM_HoldingWater_<Name>` with `M_HoldingWater` (documented silty
  grey-brown water, two world-aligned ripple layers panning in different
  directions, grazing sky sheen). `UOldWestCampVisuals::BuildHoldingGround`
  places them outside the damage/ruin part list, within 11 m wide and 7 m
  deep with water (9 m dry), so no crew stands in a river.
- Camp portraits: exposure -1 -> -0.45, warm near-neutral fill, saturation
  1.12; people and events unchanged.
- Package `dist/linux-development-holdings-colour-20261007` is now
  `dist/current` (rollback in `game-v002/promotion.json`). Packaged checks:
  66 camp portraits in healthy, damaged, ruined and repaired states; a legal
  match to a burned-out holding; core rules, AI and cosmetics suites. Not
  verified: ripple motion by frame comparison (capture noise), Windows.
- Still awaiting the project owner's appearance approval of all 34. No rigging.
