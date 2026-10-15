# Western Crew appearance and integration review

## Current scope and approval

On October 5, 2026 (Arizona time), the project owner approved the complete set: “approved.
rig and add to game.” The static-only approval gate is satisfied. Rigging,
animation and playable integration are authorized for the exact appearances in
[`appearance-approval.json`](../art/western/crew/review-v003/appearance-approval.json).
The subsequent explicit permission to upload 43 models to Mixar is recorded in
[`service-authorization.json`](../art/western/crew/playable-v001/integration/service-authorization.json).
Internal QA remains distinct from user approval and final package promotion.

There are **46 distinct people for 46 physical person-card copies**: 43 new Crew
assets and three retained approved Native characters, Quanah Parker, Lozen and
Sarah Winnemucca. Their existing playable assets are reused only for their own
identities; no appearance is shared between different Crew copies. Drifter is
additional and unchanged. The integration manifest records the source mapping
and the three retained assets:
[`playable-v001/manifest.json`](../art/western/crew/playable-v001/manifest.json).

The presentation sidecar maps canonical card ID and copy index to the appearance,
portrait and history note. It does not change mechanics, catalog counts or
authoritative gameplay state, and must preserve hidden-identity filtering.
**The verified Crew package is selected:** `dist/current` points to
`dist/linux-development-crew-20261005`. The prior camp-portrait build remains
intact. Exact package hashes, coverage and results are recorded in
[`integration/promotion.json`](../art/western/crew/playable-v001/integration/promotion.json).

## Historical documentation and compact display

All 46 people have sourced history lessons and authored three-line in-game
summaries. The maintained copies are:

- [`compact-display-notes.json`](../research/crew-history-audit/compact-display-notes.json): all 46 compact summaries, each tied to the SHA-256 of its full lesson; each line is limited to 52 UTF-8 bytes.
- [`audit-a.json`](../research/crew-history-audit/audit-a.json), [`audit-b.json`](../research/crew-history-audit/audit-b.json) and [`audit-c.json`](../research/crew-history-audit/audit-c.json): identities, date/place scope, full lessons, original citations, claim-specific support, actual-mesh observations and reconstruction limits.
- The selected revision's `historical-review.json` and historical evidence file: corrected appearance, additional sources and remaining uncertainties. The review gallery merges these with the original audit sources.

[`generate_crew_presentation_catalog.py`](../scripts/generate_crew_presentation_catalog.py)
checks complete 46-copy coverage and the lesson hashes before generating the
presentation catalog. It uses the authored summaries rather than truncating
historical claims. Full lessons and all original merged source titles, URLs and
support statements remain in the generated history attribution; the compact
visible text does not replace those citations. History is opened explicitly
through the existing optional History interaction.

The working period is approximately 1865–1900, with individual dates rather than
a false universal circa-1880 setting. Named people retain documented identities;
fictional composites receive occupational or social history, never invented
personal biographies. Retention establishes researched plausibility, not exact
facial likeness, garment color, every accessory or historical certification.
Native tribal review remains a separate pre-art-lock requirement.

Historical evidence is mandatory before new Western rendering. New generation
requests must identify evidence containing `date_scope`, `location_scope`,
claim-specific `sources`, `render_brief` and `history_lesson`. This documentation
gate does not replace source research or visual comparison of the actual mesh.

## Rigging and animation work

All 43 new Mixar rig-guide jobs completed; IDs and downloaded-source hashes are
recorded in [`rig-service-summary.json`](../art/western/crew/playable-v001/integration/rig-service-summary.json).
The guides supply anatomy and weights, while the local pipeline binds the exact
approved appearance geometry. [`rig_crew_mixar.py`](../scripts/rig_crew_mixar.py)
and [`crew_rig_mapping.py`](../scripts/crew_rig_mapping.py) produce compatible
skeletons and exports without substituting the service's appearance mesh.
Ambiguous anatomy required explicit mapping or documented local joint/weight
recovery. Reconstructed joints are practical rig placements, not anatomical
measurements of the depicted person.

The 43 new characters use idle, forward walk, attack and frontal hit-reaction
clips derived from the existing Manny source motions. Severe coat deformation
in the original full punch led to an **attack-only 0.35 rotation blend from bind**
for the active upper-body bones. Frozen bones are excluded. Hips/legs and local
translations/scales retain the original attack data; walk, idle and hit clips
are unchanged by this adjustment. The result is a restrained action gesture,
not a full-force punch. Original animation packages and sampled keys are
archived under each character's `attack-gesture-baseline-v001/`; the adjustment
and its exact package hashes are recorded in `attack-gesture-validation.json`.

Finger local transforms preserve the approved resting pose throughout these
body clips. This avoids invented finger gestures, but does not by itself fix
bad skin weights: observed cross-hand spikes were repaired separately and
stress-tested. Original appearance geometry, UVs and materials remain protected.

Rigid equipment receives explicit attachment weights and motion constraints.
Examples include slung rifles, Coach Guard's two-hand shotgun, Barn Burner's can
and belt tool, Claim Jumper's map case, and the Gatling carriage. Source-fused
contacts require some character-specific limits: Coach Guard preserves both
arm chains; Getaway Rider preserves the bag-side arm; Sharpshooter preserves the
planted rifle, torso and holding arm. Their other permitted motion remains
active. The per-character `rig-settings.json`, `rig-validation.json` and visual
review describe the exact policy. These are **not bespoke firing, reloading,
cranking, wheel-rolling or unrestricted weapon-handling animations**. Skirts,
coats and straps use skeletal deformation rather than cloth simulation.

## Gatling orientation derivative

the project owner identified the gun pointing opposite the operator. The user-directed
correction in [`review-v004/gatling-gunner/`](../art/western/crew/review-v004/gatling-gunner/)
rotates the complete 12,918-vertex gun/carriage assembly 180 degrees around Z and
repositions it so the operator stands behind the axle by the breech/crank,
facing the muzzle direction. All 3,252 human vertices are unchanged. Topology,
UVs, texture hashes and material graph are preserved; this is a rigid assembly
transform, not a new character or weapon model.

[`orientation-correction-provenance.json`](../art/western/crew/review-v004/gatling-gunner/orientation-correction-provenance.json)
records the exact transform and before/after fingerprints. The corrected static
project SHA-256 is
`f845311591fdc1fe9b6710b5b812b0d2d1cf4ecd5eb2c23569e552c30be4895b`.
The earlier approval snapshot remains in
[`appearance-approval-before-orientation.json`](../art/western/crew/review-v004/appearance-approval-before-orientation.json).
Current source approval and playable mappings select the derivative; the v003
source remains intact. Static alignment does not establish final Unreal
rig/capture acceptance, which is tracked separately below.

## Source preservation and review evidence

Approved static review sources remain separate from playable work under
`art/western/crew/playable-v001/SLUG/`. Static `.blend` sources have no armatures
or animation actions; playable derivatives intentionally contain rigs. Each
character's reports identify the approved source hash, geometry/UV fingerprint,
rig project hash, export hashes, source materials and available texture channels.
Some approved sources have no normal map; the import preserves available
channels rather than inventing one. Binding checks include a bind-pose maximum
error below 0.00001 m and at most four influences per vertex.

Unreal exports use `/Game/Art/Western/Crew/<AssetName>/` for the 43 new characters;
the three retained Native characters keep their established paths. The primary
review chain is:

- `rig-validation.json`: approved source identity, exact rig/export hashes and binding checks.
- `unreal-assets.json` and fresh readback reports: imported package hashes, meshes, materials, skeletons and animation assets.
- `unreal-pose-captures.json`: 24 pose images, every PNG hash, rig/package evidence and measured rendered component poses compared with the requested animation poses.
- `animation-visual-review.json`: actual visual inspection, exact capture-manifest and rig hashes, all reviewed filenames and limitations.

The 24 views comprise four walk phases from front/side/rear and four phases each
of idle, attack and hit reaction. After an attack-only change, 20 earlier frames
may be reused only through strict unchanged-rig/non-attack-package and image
hash checks; the four attack frames must be fresh. Changed rigs require fresh
24-frame capture. A technical capture pass is not a visual pass.

Dedicated repair scripts, archived pre-repair sources, masks and stress renders
preserve the reasons for localized prop, hand, head and foot corrections.
`skeleton-reference-audit.json` separately compares the imported mesh reference
pose with its Unreal skeleton reference pose; stale references discovered after
reimport must be repaired and recaptured before final acceptance. Historical
archives remain immutable snapshots. Private service responses and temporary
URLs are excluded from review bundles.

## Earlier static-review chronology

The original brief shared seven appearances between mechanically identical
copies. the project owner required 46 distinct characters, superseding those entries.
The v002 set retained 39 appearances and added these seven second-copy identities:

| Original role | First copy | Distinct second copy |
| --- | --- | --- |
| Hellfire Preacher | Hellfire Preacher | Revival Sister |
| Gatling Gunner | Gatling Gunner | Coach Guard |
| Widow with a Shotgun | Widow with a Shotgun | Homestead Defender |
| Barn Burner | Barn Burner | Railroad Saboteur |
| Ringleader | Ringleader | Trail Organizer |
| Vigilante | Vigilante | Town Avenger |
| Civil War Veteran | Civil War Veteran | Buffalo Soldier Veteran |

The subsequent historical pass revised Coach Guard, Gatling Gunner, Getaway
Rider, Railroad Saboteur, Ringleader, Sharpshooter, Town Avenger and Vigilante.
Six changes followed the project owner's direction on unsupported fictional demographic
assignments; Coach Guard and Sharpshooter corrected weapon depiction. This was
creative direction for fictional assets, not a claim that other demographics
were historically impossible in those occupations.

The static set was packaged as `Crew-46-Historical-Review-v003.zip`, with eight
saved-mesh views per person and 3,044 protected files unchanged during that pass.
Its static-only no-animation boundary applied **before** the later explicit
all-46 approval. Old review notes, context snapshots and archives retain that
chronology and are not current authorization statements. The studio game-camera
view was an approximation, not an Unreal capture.

Earlier corrections remain documented: revised Pinkerton/Billy/Barn references,
Gatling tripod-foot and Wild Bill revolver-grip repairs, Buffalo Soldier's
terrain removal, and Coach Guard's versioned shotgun replacement and subsequent
historical barrel correction. Original references, requests and pre-repair
assets remain preserved. No later rig work rewrites those approved static
sources; the user-directed Gatling v004 derivative is versioned separately.

## Reproduction and final validation

Use the existing job IDs and source filenames recorded in the manifests; do
not resubmit completed paid generation or rig jobs. Mixar calls are serialized
through `scripts/crew_mixar_job.py`. Local preparation and rigging use the normal
host Mixar launch because sandboxed background renders may hang at shutdown.
Reproduction requires the per-character settings and recovery/provenance
scripts, not just a blind rerun of the generic binder.

Static preparation/validation uses `prepare_crew_review.py` and
`validate_crew_review.py`; gallery/contact/bundle generation uses
`build_crew_review.py`, `compose_crew_contacts.py` and `bundle_crew_review.py`.
Playable work uses the rig, import, retarget, constraint, attack-adjustment and
capture helpers under `scripts/`. Existing static archives must not be
silently overwritten or treated as final playable packages.

Final acceptance is recorded in `playable-v001/integration/`:

- `playable-review-validation.json`: all 43 new rigs pass current source/import hashes, reference-pose equality, 24-pose evidence and visual review (1,032 poses total).
- `skeleton-reference-audit.json`: all 43 imported skeletons match their meshes. The Gatling and Homestead reference repairs and prior evidence are preserved in their `before-skeleton-reference-repair/` directories.
- `packaged-crew-v002/result.json`: Bartender, Piano Player and Gatling pass two-peer mesh, portrait, optional History, private hand filtering and exact reconnect checks. The Gatling points toward opposing camps on both connected peers; this runtime scenario exercises side 1. Its imported geometry separately verifies both side-facing transforms.
- `packaged-native-final/result.json`: Lozen, Sarah Winnemucca and Quanah Parker pass the same packaged presentation checks, plus Sarah returning Lozen to a private hand, replay and exact reconnect.
- `mechanics-regression/result.json`: six seeds, up to 100 legal actions each, produce byte-identical authoritative save/view/legal-action/apply outputs against the pre-Crew baseline. Rules, AI, card data and rules-help hashes remain unchanged. Core tests, 14 Crew Python tests and the history privacy/source/line-budget test pass.
- `promotion.json`: the selected package, previous selection, exact executable/container hashes and evidence hashes. Package validation checks required cooked assets for all 46 identities; live end-to-end scenarios sample the six named people rather than every possible card interaction.

The final package build log is under
`dist/linux-development-crew-20261005/logs/20261006T053402Z-2548031/`.
Some offline Vulkan capture processes exited 139 during shutdown after writing
all verified frames and complete manifests. This is retained as a capture-tool
limitation; both final packaged runtime test suites completed successfully.
Animation scope remains the base motions and prop constraints documented above.
