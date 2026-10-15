# Native characters — playable integration and source history

The user requested Quanah Parker (Comanche, 1870s) for Quanah Parker, Lozen
(Chihenne Chiricahua Apache, 1880s) for one Pinkerton Agent copy, and Sarah Winnemucca
(Northern Paiute, 1870s) for one Sarah Winnemucca copy. Stampede and Drifter are the
approved visual references. All generated references, meshes, materials and
renders use Mixar. All three now have dedicated playable models, animations,
portraits and optional history. The sections below retain the appearance and
animation review history; the October 5 integration section records current work.

## Preservation

`game/REBRAND_GUARDRAILS.md` remains in force. Do not change either catalog,
canonical IDs, copy counts, costs, effects, legal actions, rules, AI, saves or
network rules data. the project owner authorized a cosmetic-only sidecar exception on
October 5 for stable named copies; see `REBRAND_GUARDRAILS.md`.
`art/western/native/review-v001/baseline.json` protects 840 existing
source, configuration, catalog and Content files and the selected Drifter package.
The initial appearance candidates stayed outside Unreal until approval.

The actual catalog includes details omitted from the brief's short summaries:

- `quanah_parker`: one copy; cost 3; hock grants a punk; your people enter ready,
  including Karli; cost-1 damage ability.
- `pinkerton_agent`: two copies; cost 1; hock draws; optional entry delay of enemy
  events where possible; cost-1 damage ability if the opponent has a queued event.
  Only one copy will display Lozen.
- `sarah_winnemucca`: two copies; cost 1; hock injures; enters ready; cost-0 return
  one of your people to hand. Only one copy will display Sarah Winnemucca.

The initial appearance pass installed no display mapping. Playable integration
selects duplicate appearance per persistent entity at the presentation boundary,
without renaming every instance by canonical card ID. The sidecar preserves that
choice through return/replay and both peers and masks face-down Drifters and hidden
opponent hands. Generic twins remain unchanged. Authoritative state has no new
variant fields.

## Design and source limits

These are provisional artistic interpretations, not authenticated likenesses or
reconstructions. Colors, exact tailoring, satchel and game-normalized heights are
art choices. Historical photographs and written context constrain the brief;
no archival image was uploaded as a generation input. An attempted upload of the
local Drifter style render was blocked by automatic approval review before
submission. Generation uses text-only style descriptions and newly generated
Mixar references; the Drifter render is retained only for local comparison.

Quanah's candidate uses a clay-red trade shirt, plain hide leggings, breechcloth,
moccasins and two braids. It depicts a younger leader rather than copying his
later-life ceremonial portraits. The [Comanche Nation history](https://www.comanchenation.com/about/page/history)
provides the equestrian context. The [Kansas Historical Society portrait record](https://www.kansasmemory.gov/item/210736)
has a broad 1870–1889 date range; it cannot establish an exact 1870s outfit.
The [Gilcrease group portrait](https://collections.gilcrease.org/object/43163227)
has uncertain identification and broad dating and is not treated as proof.

Lozen's candidate uses a plain cotton blouse, gathered cloth skirt and tall
soft-hide footwear. Her tactical role is expressed through bearing. The
[NPS page identifying Lozen in National Archives photograph 530797](https://www.nps.gov/chir/learn/historyculture/post-apache-wars.htm)
provides an 1886 reference and explicitly identifies her in the back row.
The small group portrait does not establish fine facial, footwear or textile
detail; these remain review questions, including the candidate's headband.

Sarah's candidate uses a muted indigo high-necked bodice, full dark skirt,
plain ankle boots and a small document satchel. The
[University of Nevada, Reno biography](https://library.unr.edu/nevada-writers-hall-of-fame/sarah-winnemucca)
documents her 1870s interpreter work. The
[NPS biography](https://www.nps.gov/people/sarah-winnemucca.htm) identifies its
familiar 1883 portrait as a nontraditional stage costume, so that outfit is not
used as evidence for everyday Paiute dress. Tailored travel clothes are an
interpretation; do not label them traditional Northern Paiute clothing.

The three candidates have no alcohol, ceremonial props, invented beadwork,
fantasy effects or threat-to-settlers framing. Weapons and mounts are not part
of these neutral appearance studies.

the Western presentation plan requires: “Before art lock, have names, art and text
reviewed by the Comanche Nation, the Fort Sill Apache Tribe (Chiricahua) and a
Northern Paiute tribe such as the Pyramid Lake Paiute Tribe.” That review is
pending; nobody has been contacted and no tribal approval is claimed. It does
not prevent making these concrete candidates for review.

## Local assets and reproduction

Each character has its own directory under `art/western/native/review-v001/`:
`quanah-parker`, `lozen`, and `sarah-winnemucca`. The directory is outside Git
under the existing asset policy and must be backed up separately.

`character.json` records identity, nation, decade, copy scope and provisional
status. `reference-request.json` uses Mixar `flash-3-1`; `model-request.json`
uses `tripo-v31`, PBR textures and a 24,000-face request. `catalog.json` retains
the live catalog. Use `scripts/stampede_mixar_job.py` to submit, check status and
download exactly as documented in `game/STAMPEDE_PILOT.md`. Its legacy log prefix
does not affect the asset destination. Retain idempotency records locally and
never include job records or temporary download URLs in a shareable archive.

Prepare each downloaded `original.glb` with Mixar:

```sh
~/.local/bin/mixar --background --factory-startup --python-exit-code 1 \
  --python scripts/prepare_native_review.py -- \
  --source art/western/native/review-v001/quanah-parker/original.glb \
  --character art/western/native/review-v001/quanah-parker/character.json \
  --output art/western/native/review-v001/quanah-parker/review
```

Replace the slug for the other characters. Inspect facing before choosing
`--heading-degrees` (default 270 for source +X). The preparation enforces a
30,000-triangle ceiling, one material and three packed 2K textures. It saves an
editable Mixar project and renders front, side, rear, three-quarter, approximate
game camera, face, hands and underside views of the actual mesh. Floors, lights
and cameras are review aids, not game assets. No render is an Unreal capture.

Reopen each source with `scripts/validate_native_review.py -- REVIEW_DIRECTORY`
inside Mixar to check saved geometry, texture packing, preview hashes and all
protected files. This validation is technical evidence, not historical approval.
Appearance review precedes rigging, animation and playable integration, following
the approved pilots' workflow.

## Completed v001 appearance pass

The actual mesh review is `art/western/native/review-v001/Native-Appearance-three-quarter.png`.
Quanah has 23,636 triangles, Lozen 22,470 and Sarah 22,990. Each saved source
reopened successfully with one material, three packed 2K textures and no rig
or animation. All 24 inspection renders were reviewed. Validation confirms all
840 protected files and the selected Drifter package are unchanged. Existing
portable rules and AI suites both pass.

`REVIEW.txt` records the remaining appearance questions: generated facial
likenesses, Quanah's leggings, Lozen's headband/hair/raised front hem/footwear,
and Sarah's tailored travel outfit and satchel. The first preparation attempt
failed before project saving because of a path expression; partial outputs
are retained under `prepare-error/`. Corrected normal-runtime renders and all
saved-source validators exit cleanly. No historical approval is inferred.

`scripts/bundle_native_review.py` creates `Native-Appearance-Review.zip` from
an explicit allowlist, including the three editable projects, originals,
textures, renders, requests, source notes, scripts and validation evidence.
Private job records, temporary download URLs and prior Drifter imagery are
excluded. `art/western/native/CURRENT.json` points to this appearance checkpoint.

## Appearance approval

The user approved all three v001 appearances (“look apprived.”).
`review-v001/appearance-approval.json` records the exact approved project hashes.
This supersedes the pending user-appearance status inside the preserved review
bundle. Tribal review remains a separate pre-art-lock checkpoint. The user also
requested a discreet optional two-to-three-line history note for clicked game
assets. This is presentation work and does not relax the mechanics freeze.

## Quanah playable integration

The user reported drawing Quanah Parker and seeing the original character. The
appearance approval had been recorded without completing playable integration.
`art/western/native/quanah-game-v001/` now contains the approved Quanah model's
Mixar guide rig, editable `Quanah-Rigged.blend`, FBX and packed textures, native
import/retarget audits, and runtime verification evidence.

The Mixar rig preserves all 23,636 triangles and the approved geometry/UV hash.
Its 53 bones use at most four normalized influences per vertex; maximum bind
pose error is below one micrometer. Existing idle, walk, hit and unarmed attack
motions are retargeted with the established Unreal pipeline. The new native
assets live only under `/Game/Art/Western/Quanah`.

Presentation maps the public `quanah_parker` identity to Quanah's mesh, animations,
portrait and name. The obsolete Karli flame/flag portrait vignette is removed.
His sourced history note is enabled. Face-down identities still choose Drifter
before any named lookup. Canonical names, IDs, costs, abilities, catalogs,
authoritative state and rules remain unchanged. Lozen and Sarah remain at the
approved appearance checkpoint and are not implied to be integrated by this fix.

Reproduction scripts: `export_quanah_mixar.py`, `rig_quanah_mixar.py`,
`import_quanah_unreal.py`, `retarget_quanah_unreal.py`,
`preview_quanah_unreal.py`, and `test_unreal_quanah.py` under `scripts/`.
The native scenario draws and plays the card through legal commands, checks
the public model/name/history and both peers' canonical identity, then exercises
the original damage ability. Tribal review remains separate from this playable
user-approved appearance and is still required before art lock.

The final candidate package is
`dist/linux-development-quanah-review-20261004-v002`. Legal two-peer scenarios
pass at 720p (`quanah-game-v001/package-v003/1280x720/result.json`) and 1080p
(`quanah-game-v001/package-v004/1920x1080/result.json`), including the history
popup in both inspectors, drawing, deployment, enter-ready behavior and the
original damage ability. The catalogs retain “Quanah Parker” and the original
trait text; displayed prose substitutes Quanah's name, including the short
“including Quanah” reference.

The standalone Vulkan editor captured all five reviewed animation poses, then
hit the existing pilot shutdown crash. The import/readback and retarget
commandlets passed; packaged runtime results are independent of that editor
shutdown. Earlier test retries are retained, including the hand/board diagnostic
distinction, asynchronous hand-label arrangement, and the original History
link falling below the selected-card section viewport.

The animated portrait regression passes in `quanah-game-v001/portrait-v002/`,
including the expected Quanah mesh, skeletal motion, changing rendered pixels,
and unchanged authoritative snapshot. `promotion.json` selects the verified
package through `dist/current` and retains the previous History package.
Restart through `scripts/launch_battle_of_the_old_west.sh` to use it. No running player game
was terminated or modified. `Quanah-Game-Source.zip`, built by
`scripts/bundle_quanah_game.py`, retains the editable Mixar project, approved
appearance, source guide, textures, exports, native assets and authoring scripts;
private Mixar job URLs are excluded.

## Three-character Unreal animation preview

The requested side-by-side reel is
`art/western/native/trio-animation-v001/Native-Trio-Unreal-Animation.mp4`:
12 seconds at 1080p/24 fps, with idle, walking in place, then idle. Its 288
frames are native Unreal Movie Render Queue output, with name/nation/decade
labels added during encoding. The preview reuses Quanah's integrated assets.
Lozen and Sarah have new Mixar guide rigs transferred onto their exact approved
geometry and UVs, with editable `Lozen-Rigged.blend` and `Sarah-Rigged.blend`
projects in their respective subdirectories. Each has 53 bones and the existing
project's idle, walk, hit and attack motions retargeted in Unreal.

New imports are isolated under `/Game/Art/Western/NativePreview/Lozen` and
`Sarah`; the saved review level and sequence are under `ShowcaseV002` there.
No duplicate card mapping or build promotion is part of this animation preview.
Lozen's skirt clips the forward leg during parts of the walk and requires
weight/cloth refinement before playable integration. This is an animation
review checkpoint, not an animation or tribal approval.

Reproduce with `export_native_trio_mixar.py`, `rig_native_preview_mixar.py`,
`prepare_native_trio_unreal.py`, `render_native_trio_unreal.py` (enable the
MovieRenderPipeline plugin for that editor session), then
`encode_native_trio_preview.py`. Per-character rig/import/retarget reports,
`render.json`, `video-validation.json` and `preservation.json` retain evidence.
All 907 pre-existing source, configuration, catalog and Content hashes and the
selected Quanah package remain unchanged.
Movie Render Queue reports success with no render errors and all 288 frames;
the editor then reproduces the known shutdown SIGSEGV. The encoded video
independently passes duration, dimensions and frame-count checks.

## Native trio playable integration — October 5, 2026

The active request is to fix Lozen's clipping and integrate Lozen and Sarah with
stable appearances for their individual Pinkerton Agent and Sarah Winnemucca copies.
All three mappings are implemented. Final package verification and promotion
are recorded under `art/western/native/playable-v001/integration/`.

The initial guide rig pinned most of Lozen's skirt to the pelvis. The first
weight correction (`lozen-cloth-v002`) restored thigh following but still let
the trailing calf cross the rear hem. The next correction (`v003`) added calf
following but retained small opposite-leg influences. Native bone-pose exports
and a Mixar reproduction isolated those residual influences. The current
candidate is `art/western/native/lozen-cloth-v004/Lozen-Rigged.blend`, authored
by `scripts/repair_lozen_cloth_mixar.py`: the covered legs and skirt share a
smooth anatomical weight field, with a narrow blend at the center and a smooth
transition at the waist. Geometry, UVs, textures and the 53-bone rig are retained.
The approved appearance and original preview sources remain intact. The 48 native v004 poses pass capture integrity checks and were visually
reviewed from front, side and rear, including idle, hit and attack samples.
The original forward-knee breakthrough is absent. `visual-review.json` records
this pose-review scope; the full native motion reel is a separate check. The
native materials now also render both sides of the hem, matching Mixar.

Both candidates are imported under `/Game/Art/Western/Lozen` and
`/Game/Art/Western/Sarah`. Each has the existing four motions (idle, walking,
hit and unarmed attack), plus a character-fitted physics asset with 16 bodies
and 15 constraints. The editor authoring function now accepts an optional
`WesternCharacter` argument restricted to Lozen/Sarah; its existing callers
keep their original behavior. The editor build passes. Saved-source reopening
checks normalized weights, at most four influences, packed 2K textures, exact
approved geometry/UV hashes and bind-pose preservation. Existing rules and AI
test suites pass. Each named copy now selects its own asset path in field models
and every portrait surface.

Reproduction: `prepare_native_playable_unreal.py` imports/retargets both assets;
`validate_native_playable_sources.py` verifies the saved editable sources;
`preview_lozen_cloth_unreal.py` captures 48 native poses; and
`export_lozen_pose_diagnostics.py` reads actual native reference/animation
transforms for cloth diagnosis. Setting `OLDWEST_NATIVE_PLAYABLE=1` when running
`render_native_trio_unreal.py` and `encode_native_trio_preview.py` creates a
separate reel under `playable-v001/trio-review`, preserving the original reel.

the project owner authorized integration of all three after the cosmetic-metadata question.
The server keeps a separate map for the second Pinkerton Agent copy (Lozen) and first
Sarah Winnemucca copy (Sarah Winnemucca). It rekeys that map when the existing engine
replaces a deck card's public handle. No parity or current handle-order heuristic
is used during play. Player snapshots receive tags only for their own visible
hand and face-up board cards. Local presentation resolves names, meshes,
portraits, ability/target/choice labels and History from the same tag. Named
source/target duplicates are disambiguated; generic twins remain generic.

Canonical `ViewJson`, `LegalActionsJson` and `SaveJson` remain unchanged. AI sees
those canonical inputs. `CosmeticSaveJson`/`RestoreCosmeticJson` offer separate
server-only persistence: callers restoring a full match must restore this
sidecar after `RestoreJson` to retain exact copies. The game currently reconnects
to its live server state, which already retains the sidecar. Rejected commands
roll back cosmetic handle changes with the authoritative state.

`game/tests/presentation/native_cosmetics_tests.cpp` covers 12 seeds, both named
copies, generic duplicates, visibility/face-down masking (including private
peeks), legal return/replay, public-handle rekeying, invalid-action rollback,
sidecar persistence and duplicate-target labels. The existing rules and AI
suites pass. A deterministic before/after trace across six seeds in each of both
rulesets has identical canonical save, both-player view and legal-action output
(SHA-256 `6b1ac409b9fb0d78a1bcf33a9a70b6adbd0a1e7693e4ac7e8f05bb9ac6a3f9b3`).

`scripts/test_unreal_native_copies.py` uses ordinary legal actions and two real
peers to draw/play all three, verify native meshes and render-ready portraits,
click optional History in both inspectors, return/replay Lozen using Sarah, and
leave/rejoin the exact match. It captures 720p and 1080p field and close views.
Quanah's separate regression exercises his original damage ability. Earlier
failed harness evidence is retained: the first test exhausted the deck before
replaying Lozen; the corrected test uses a legal water-junk action first.

The updated 12-second native trio reel is in
`art/western/native/playable-v001/trio-review/Native-Trio-Unreal-Animation.mp4`.
Movie Render Queue completed all 288 frames without render errors; encoding
checks confirm 1080p/24 fps and 12 seconds. A complete 36-frame walking cycle
and the former failing frame 140 were visually reviewed. The knee now remains
behind the moving front hem. The editor still reproduces the previously
documented shutdown SIGSEGV after saving complete captures; commandlet import,
readback and the editor build pass independently. Playable-game verification
is separate under `integration/`. The original `Native-Playable-Candidates.zip`
is retained; `Native-Trio-Game-Source.zip` additionally includes all three editable
rigs, native assets, integration source/configuration and portable tests.

The verified release is `dist/linux-development-native-trio-20261005-v003`, now
selected by `dist/current`. `integration/packaged-release/result.json` records
passing 720p and 1080p runs, including render-ready portraits, copy visibility,
real History clicks, legal return/replay and exact reconnect state. The final
rules, AI and native-copy tests all pass. `promotion.json` records the executable
hash and preserves the previous Quanah package. Restart through the normal
launcher to use this build; existing running sessions were not interrupted.
