# Drifter — playable Western replacement

The user selected Punks → Drifter after approving the playable Stampede.
Stampede remains the approved style reference.

The latest appearance revision is in `art/western/drifter/review-v003/`.
The user liked the face bandana and requested clothes with restrained wear,
suited to a Western drifter whose outfit is still cared for. The subsequent
“put in game now” instruction approves v003 for integration and authorizes the
necessary rigging, motion checks and playable package. Earlier checkpoint notes
below record the review history; this latest instruction supersedes their pauses.

## Invariants

- Preserve the card roster, duplicate counts, canonical `punk` identity,
  face-down rules, legal actions, AI, saves and network payloads.
- One anonymous, unarmed frontier figure represents all face-down people.
  Hidden card identity must never select a visual, portrait or animation.
- Use Mixar for reference generation, mesh generation and asset authoring.
- Follow Stampede's grounded proportions and natural material response.
  (The original “muted earth colors” direction is superseded by the October 7,
  2026 full-colour art direction in `AGENTS.md`; any future Drifter revision
  uses documented colours at full strength.) Conceal the face with a hat brim and raised bandana.
- Review one asset and one checkpoint at a time: appearance, then animation,
  then playable integration. Approval of one checkpoint is not approval of
  later checkpoints.

## Stage A — appearance

Local evidence and editable assets live in
`art/western/drifter/review-v001/`, outside Git under the existing asset policy.
Back up that directory separately from the code repository. Generation job
records may contain temporary download URLs and must stay outside Git.

The design uses a worn brown felt hat, faded brick-red cotton bandana, dusty
brown canvas jacket, oatmeal work shirt, dark trousers, leather gloves and
boots. A neutral low A-pose leaves room to inspect and later rig the limbs.
No weapon or identifying insignia is part of the figure.

`baseline.json` records the starting Git status and hashes of all pre-existing
game source, configuration and Content files, plus the portable card catalog
and selected package path. Existing Stampede changes are preserved.

`catalog.json` records Mixar's live generation catalog. `reference-request.json`
uses Mixar's `flash-3-1` image service; `model-request.json` uses `tripo-v31` with
textures, PBR and a 24,000-face request. The retained job helper is
`scripts/stampede_mixar_job.py`; its Stampede log prefix does not change the
request directory or generation inputs. Requests retain idempotency keys;
revised settings require a new request file.

Prepare the mesh and render its actual appearance with:

```sh
~/.local/bin/mixar --background --factory-startup --python-exit-code 1 \
  --python scripts/prepare_drifter_review.py -- \
  --source art/western/drifter/review-v001/drifter-original.glb \
  --output art/western/drifter/review-v001/review
```

The preparation keeps the original GLB intact, normalizes the figure to 1.85 m
including the hat, uses forward −Y and up +Z, caps the mesh at 30,000 triangles,
and packs one material's three 2K textures into `Drifter-Review.blend`.
The stage floor, lights and cameras are review aids, not game geometry.

Reopen the saved source and verify it with:

```sh
~/.local/bin/mixar --background --factory-startup --python-exit-code 1 \
  --python scripts/validate_drifter_review.py -- \
  art/western/drifter/review-v001/review
```

Inspect front, side, rear and three-quarter renders, face and hand details,
underside, and the approximate game-camera view. These are Mixar renders,
not native Unreal captures. Check the hat brim and bandana concealment,
proportions, hands, boots, garment surfaces and distant silhouette.

**Historical review checkpoint:** the initial appearance pass stopped before
rigging. The later “put in game now” instruction authorizes the current integration.

### Initial candidate and evidence

The v001 `review/Drifter-Review.blend` is the retained initial candidate: 23,646 triangles, one
material, three packed 2048×2048 textures, no rig or animation. The original
mesh faces +X on import; the preparation rotates it 270° to forward −Y.
Normal strength is 0.3, metallic is zero, and roughness has a 0.6 floor to
remove the generated leather's excessive gloss. The eight reviewed previews
are in `review/previews/`. `orientation-diagnostic/` retains the initial
orientation/material check and is not the current deliverable.

`review/validation.json` records independent saved-project readback and all
826 protected file hashes unchanged. The selected package still points to
`dist/linux-development-stampede-review-20261003`. The existing portable
rules and AI suites both pass; see `baseline-core-tests.log`.

`Drifter-Appearance-Review.zip` retains the packed Mixar project, original
GLB, textures, reference, requests, previews, authoring scripts and validation
evidence without private generation job records. `CURRENT.json` identifies
the current checkpoint and bundle. Rebuild a new bundle with
`python3 scripts/bundle_drifter_review.py` only after saving and validating
the review; the script refuses to overwrite an existing archive.

The sandboxed render sessions completed their files but stalled during audio
shutdown after a PulseAudio permission error. Saved-source validation in the
normal Mixar runtime exited cleanly. This does not constitute native Unreal
or animation validation, which belongs to later checkpoints.

### Worn-clothes revision — v002

The retained first wear candidate is
`art/western/drifter/review-v002/review/Drifter-Review.blend`.
The revision is a texture-only Mixar authoring pass: sun-softened canvas,
restrained abrasion at high-use garment areas, faded knees and light trail
dust at the trouser hems. There are no tears, holes or added costume pieces.
The hat, head and bandana's protected texture pixels remain exactly unchanged.
The original geometry, topology, UVs, normal map and ORM map are preserved.

`Drifter-Before-Wear.blend` retains the previous editable source. The initial
wear diagnostic is retained in `wear-diagnostic/`; it is not the current
candidate. `review/manifest.json` records the source lineage, geometry/UV hash,
protected texture pixels and current render hashes. `review/validation.json`
records independent saved-project readback against the predecessor and the
gameplay baseline. Existing rules/AI test results are retained from v001;
the texture-only revision does not change game code or require those tests
to be repeated.

Reproduce in a fresh revision directory containing the retained source and
baseline records:

```sh
~/.local/bin/mixar --background --factory-startup --python-exit-code 1 \
  --python scripts/weather_drifter_review.py -- art/western/drifter/review-v002
~/.local/bin/mixar --background --factory-startup --python-exit-code 1 \
  --python scripts/validate_drifter_review.py -- art/western/drifter/review-v002/review
python3 scripts/bundle_drifter_review.py --source art/western/drifter/review-v002
```

The authoring and bundling scripts refuse to overwrite an existing review or
archive. The revision bundle includes both editable projects and the wear
authoring script. All review views remain Mixar mesh renders, not Unreal
captures. Approve this revised appearance before rigging or animation.

### Readable garment wear — v003 (current)

The user found v002 visually indistinguishable from the original. V003 uses
stronger localized wear that reads at full-body size: sun-faded shoulders and
sleeves, rubbed cuff and pocket seams, unequal faded knees and dusty lower
trouser legs. Clothes remain intact; the head and bandana are preserved.

Current source: `art/western/drifter/review-v003/review/Drifter-Review.blend`.
`wear-settings.json` selects the `readable_wear` profile in the same Mixar
authoring script. V003 starts from the original v001 source, not a cumulative
edit of v002. `Drifter-Before-After.png` places original and current actual
mesh renders side by side with the same camera and lighting, without
retouching. It is composed using `scripts/compare_drifter_review.py` in Mixar.
The first seam-placement study is retained in `edge-placement-diagnostic/`.

Use the v002 commands above with `review-v003` as the directory. The final
validation again checks saved geometry/UVs and normal/ORM textures against
the original source and all 826 protected files against the gameplay baseline.
The current pointer is `art/western/drifter/CURRENT.json`. The user then
requested “put in game now”; v003 is the appearance used by the integration.

## Playable integration — game-v001

User authorization is retained in `art/western/drifter/animation-v001/approval.json`.
The approved appearance source hash is
`3156d980bf20fdf2ab84d23eb2b9b9c8e293b90cb2f23d38549dc77576c85715`.

Mixar's rig service produced the biped guide. `scripts/rig_drifter_mixar.py`
transfers its weights onto the exact approved mesh, preserving geometry, UVs,
and all three textures. The packed editable source is
`art/western/drifter/animation-v001/Drifter-Rigged.blend`. The 53-bone rig uses
at most four normalized influences, rigid headwear, and explicit anatomical
bone naming. The saved-source validation records sub-micrometer bind-pose
error and unchanged geometry/UV hashes.

`scripts/import_drifter_unreal.py` creates only `/Game/Art/Western/Drifter`
assets. `scripts/retarget_drifter_unreal.py` adapts the game's existing idle,
unarmed walking, attack and hit motions onto this skeleton, with unchanged
clip durations. This keeps the game's established motion and event timing.
`scripts/preview_drifter_unreal.py` captures the native animation study on a
transient floor without saving a map. The physics asset uses the same body
and constraint authoring as existing people, fitted to the Drifter skeleton.

The presentation chooses the Drifter mesh and animations for canonical `punk`,
including decorative gate residents and hidden-card portraits. Face-down
cards never choose a mesh from private identity. The display boundary maps
Punk/Punks prose to Drifter/Drifters, while commands, IDs, network state and
catalog entries remain unchanged. Existing Stampede assets and prior packages
are preserved. No other Western replacement is included.

Integration evidence is retained in `art/western/drifter/game-v001/`.
`baseline.json` records the pre-integration files; `preservation.json` checks
rules, catalogs and prior assets. `core-tests.log` records passing rules and
AI suites. Packaged interaction and visual evidence is recorded here before selecting
the new package for the normal launcher. The native editor pose capture
completed all five screenshots, then encountered the same Vulkan shutdown
segfault previously reproduced with the Stampede control. Commandlet imports
and rig validation exited successfully; packaged runtime checks are separate.

The first packaged checks exposed a display-helper diagnostic issue: serialized
JSON containing spaces could have lowercase `punk` rewritten. The display
helper now returns serialized objects/arrays unchanged. The canonical game
snapshots were unchanged throughout. The original interaction harness also
expected the retired field-action strip and an initially open Battle Plan;
`scripts/test_unreal_drifter.py` uses current context menus and explicitly opens
the current panel. Initial failed evidence is retained separately from reruns.

### Packaged review and launcher

The playable package is `dist/linux-development-drifter-review-20261004`.
The 720p recruitment evidence is `game-v001/package-shelter-v006/`; the
1080p private-inspection/reveal evidence is `game-v001/package-masquerade-v002/`.
The latter ran before the final recruitment-label layout adjustment. That
subsequent adjustment only changes prompt placement and panel avoidance.
The final recruitment test checks all three prompts are labeled DRAG DRIFTER,
do not overlap one another, and remain outside the visible HUD panels.

The two-peer scenarios cover six decorative residents, idle/walk/punch motion,
Wagon Fort recruitment, drag/cancel/drop/Skip, Stockyards recruitment, resource and
revision preservation, private inspection, event-card flip restrictions,
paid person reveals and identity synchronization. Runtime evidence asserts
that anonymous board figures, residents and portraits all use SK_Drifter,
remain unarmed, and preserve canonical `punk` IDs. The remaining Stampede
context-menu check uses the current movable HUD with its abilities dock
collapsed so the queue target is not obscured.

`game-v001/preservation.json` confirms the rules/AI sources, both card catalogs,
and all 754 pre-existing Content files are unchanged. Both portable test suites
pass. New assets are isolated under `/Game/Art/Western/Drifter`.

After packaged verification, `game-v001/promotion.json` records selection through
`dist/current`, retaining the previous Stampede package. Restart the running
game through `scripts/launch_battle_of_the_old_west.sh` to load the new package. No running
player session is terminated or altered by the promotion.

`scripts/bundle_drifter_game.py` preserves the approved appearance, editable
Mixar rig, source guide, FBX/textures, native assets, authoring scripts and
review evidence in `game-v001/Drifter-Game-Source.zip`. This local asset bundle
is separate from the code-only repository and excludes private Mixar job URLs.
No further asset has been started.

## October 8: public bandana drop in development

`art/western/drifter/reveal-bandana-v001/review.json` records a separate cloth
prop derived from the approved Drifter, preserving the body, original material
and animation clips. Its two-sided material copy uses the existing textures.
The public reveal drops the cloth from the neck to the ground, then cleans it up
with the shot. Private inspection never creates a drop or selects named History.
The generic optional note now explains documented kerchief uses, with a source
link, and identifies the stranger and reveal as fictional.

Owner/opponent native views, natural completion, ordinary Skip and rendered guest
reconnect pass legal two-peer replays. Interruption leaves both full gameplay
snapshots unchanged and no registered cloth. Other identities, the opposite
board-owner orientation, crowded layouts, full regional phase coverage and final
packaging remain. The launcher still selects the earlier package.
