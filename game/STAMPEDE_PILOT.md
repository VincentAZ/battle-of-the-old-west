# Stampede pilot — playable herd review

The Western rebrand starts with a single longhorn authored through Mixar.
The user approved the animal's appearance and animation, then requested the
in-game herd. Stage C integrates three copies into the existing Raider actor
and its card portrait. The user approved the playable herd with “FUCKIN love it.” The normal
launcher now selects the Stampede package; the previous package is retained.

## Invariants

- Keep the existing card roster, duplicate counts, rules, AI, and canonical IDs.
- Keep `stampede` as the gameplay ID; display it as Stampede in presentation.
- Grounded stylized Western art, believable anatomy and natural materials.
- At most 30,000 triangles, one shared 2K material texture set, one eventual rig.
- Preserve the current truck assets and the currently selected game package.

## Local asset records

`art/western/stampede/review-v001/` holds the baseline, generation requests,
original generated mesh, reference, and review deliverables. This directory is
ignored by Git under the repository's existing asset policy. Preserve the
editable asset bundle separately when copying or backing up the code repository.

Current candidate: `review/Longhorn-Review.blend`, with the four views under
`review/previews/`. It has 22,626 triangles, one material, and 2K base-color,
normal, and packed occlusion/roughness/metallic maps. The coat shader uses no
metallic response and softens the generated normal detail. The user approved this appearance with “yup, great job.” Earlier `prepared/` and `appearance/` folders are retained
as diagnostic iterations, not the current deliverable.

`baseline.json` records the starting Git commit, current package location, and
SHA-256 checksums of the complete portable Core directory and both card catalogs.
`baseline-core-tests.log` records the rules and AI test baseline.

Generation uses the installed Mixar application's normal authenticated services.
Credentials are never embedded in authoring scripts or asset manifests. Local job
records can contain temporary asset download URLs and must remain outside Git.

## Reproduce the workflow

Run from the repository root with the installed Mixar executable:

```sh
~/.local/bin/mixar --background --factory-startup --python-exit-code 1 \
  --python scripts/stampede_mixar_job.py -- REQUEST.json submit
```

Use `status` to poll the same request. The persisted idempotency key makes a
submission retry reuse its job. Revised prompts/settings require a new request
file; don't overwrite an existing paid request. Once complete, use
`download --output NEW_FILE` to retain the original result.

Request JSON contains `service`, `model`, `params`, optional top-level `prompt`,
and an optional `image` or `mesh` path relative to the request. Image generation requires
the top-level prompt; it is not a model parameter. Choose available models and
parameters from Mixar's live catalog rather than assuming provider defaults.

After inspecting the reference and generated model:

```sh
~/.local/bin/mixar --background --factory-startup --python-exit-code 1 \
  --python scripts/prepare_stampede_review.py -- \
  --source art/western/stampede/review-v001/longhorn-original.glb \
  --output art/western/stampede/review-v001/review-new
```

The preparation script retains the original GLB, normalizes the review mesh's
scale/orientation, enforces the triangle budget, saves a packed editable Mixar
project, and renders front, side, three-quarter, and approximate game-camera
views. The last view is a Mixar render, not evidence of native Unreal appearance.
The review source intentionally has no rig or animations yet.

## Appearance review criteria

Inspect the entire model, including horns, hooves, underside, and tail. Approve
proportions, silhouette, coat, material response, and readability at game-camera
distance before rigging. Inspect the actual mesh renders rather than treating
the generated reference image as evidence of the finished model.

## Stage B — single-animal animation review

`art/western/stampede/animation-v001/` retains the appearance approval, Mixar
quadruped rig request and original result, editable `Longhorn-Animated.blend`,
FBX exports, previews, and validation reports. The provider normalized the mesh;
authoring restores its approved three-meter length and transfers weights back
to the exact approved geometry and UVs. Geometric filtering removes stray
weights; the skull and horns remain rigid, and the hooves retain ground contact.

- 22,626 triangles, one material, three packed 2048×2048 textures.
- One 30-bone skeleton, with at most four normalized weights per vertex.
- `Longhorn_Idle`: four seconds, 30 fps, duplicate endpoint at frame 120.
- `Longhorn_Run`: 0.8 seconds, 30 fps, duplicate endpoint at frame 24.
- Both clips are in place, with a stationary `Root` and matching endpoints.
- Run stance speed is 2.25 m/s; later presentation should match playback speed
  to visual movement and blend between idle/run without changing event timing.

Source units are meters, forward −Y, up +Z. Disposable FBX export converts mesh,
bones and translation keys to physical centimeters with object scale one. The
legacy Unreal importer produces forward +Y, up +Z, with no extra import rotation.

New native assets live only in `/Game/Art/Western/StampedeStudy`: the skeletal
mesh, skeleton, two sequences, material and three textures. No physics asset,
event actor, catalog, rules, AI input, cooking configuration, map or launcher
package is changed in this checkpoint.

Run these scripts in order using the installed Mixar executable as above:

1. `scripts/animate_stampede_review.py` — author rig/weights/loops from the
   approved project and downloaded Mixar rig.
2. `scripts/preview_stampede_mixar.py` — render key poses; use `--sequence Idle`
   or `--sequence Run` and `--camera side`/`three-quarter` for movie frames.
3. `scripts/validate_stampede_source.py` — reopen the source and compare exact
   approved geometry/UVs, weights, seam continuity, floor contact and loop joins.
4. `scripts/export_stampede_fbx.py` — export mesh, skeleton, animation, textures
   and expected native poses; never overwrite the editable source.

Run `scripts/import_stampede_unreal.py` with UnrealEditor-Cmd's Python commandlet.
Set `OLDWEST_STAMPEDE_VERIFY_ONLY=1` for independent saved-package readback.
`scripts/preview_stampede_unreal.py` performs that readback and captures native
poses in a transient review scene. It requires a rendered editor process with
`-ExecutePythonScript`, `-RenderOffscreen` and isolated game-user settings.
It never saves the map. Finish asynchronous texture compilation before querying
native dimensions; a still-compiling texture initially reports a placeholder.

The source audit checks 146 frames. Native checks compare all 30 bones on all
146 frames against the source, including position, orientation, scale, endpoints
and root drift. SHA-256 snapshots protect all pre-existing Content files.
The pilot baseline separately protects the rules, AI, both catalogs and selected
package. Stage A's portable rules and AI suites remain the test baseline.

`previews/Longhorn-Idle.mp4` and `Longhorn-Run.mp4` show Mixar studio loops.
`previews/Unreal-*.png` are actual Unreal renders of the imported animal on a
temporary flat floor. They are single-animal review evidence; event lifecycle,
portrait framing, packaging, gameplay capture and scene performance comparison
belong to Stage C after animation approval.

**Review checkpoint:** approve the idle/run gait and deformation before assembling
three copies into the Stampede. Game mechanics remain unchanged throughout.


## Stage B editor capture limitation

The offscreen Vulkan editor completes captures and asset checks, then exits with
code 139 during shutdown after its normal exit/SDL teardown log. An unchanged
WaterDepotV2 capture control, without loading the longhorn, reproduces the same
failure. The asset import commandlet exits cleanly. This remains an editor
capture-tooling issue to track; it is not evidence of a packaged gameplay pass.
The diagnostic and captured review outputs are retained in the animation bundle.


## Stage C — playable review

The user approved Stage B with “we good, let's see it in the game now.”
The review package is `dist/linux-development-stampede-review-20261003/archive`.
Launch it with `scripts/launch_stampede_review.sh`. The previous package, `dist/linux-development-real-ruins-20260912`, and truck
assets remain available for rollback. `dist/current` now selects this approved build.

`UOldWestStampedeVisuals` creates three collision-free copies at fixed offsets.
Movement comes exclusively from the existing presentation director. Actual
visual distance advances the in-place running loop; backward queue delays run
the same clip backward, and stationary animals idle at staggered phases.
A short pose blend joins idle and running. Scale is 0.72 with a formation that
fits the existing queue and camera. All three share one mesh, skeleton and
material. New animal audio and elaborate dust remain deferred.

The herd remains visible in the queue while the defender chooses. A charge is
queued only after the authoritative damage/destroy log identifies the holding.
An immediately resolved event receives the same presentation and supports
removal, reuse and cinematic skip. Visuals never choose targets or apply damage.

`OldWestDisplayNames.h` maps the existing `stampede` ID to Stampede and converts
rendered labels at the presentation boundary. Canonical card text, commands,
legal actions, AI inputs, saves and network payloads retain their original names.
No other rebrand terms are applied yet.

Evidence lives in `art/western/stampede/game-v001/`:

- `rules-validation.json`: all nine protected file hashes unchanged; 2,622
  seeded snapshots across two rulesets and six seeds per ruleset match the
  baseline in complete authoritative state and both players' legal actions.
- `core-tests.log`: existing portable rules and AI suites pass.
- `package-lifecycle*`: native two-player launch, advance, choice, damage,
  destruction and cleanup at 720p and 1080p, screenshots and motion telemetry.
- `package-edges*`: legal Pinkerton Agent backward/blocked delay and Zeto/Gas Station
  immediate resolution, covered holding, same-ID reuse and cinematic skip.
- `package-portrait*`: native animated portrait, pixel checks, cleanup and
  packaged asset readback.
- `Stampede-Gameplay.mp4`: timed native gameplay screenshots assembled into a
  short review clip, with original frames and timestamps retained.

The editable asset bundle remains
`art/western/stampede/animation-v001/Longhorn-Animation-Review.zip`.
It contains the approved Mixar project, source/export scripts, textures,
animations, export settings and asset manifests. Integration is additive.

Re-run `scripts/test_unreal_stampede.py` with `--package-dir` pointing at the
review archive. `scripts/test_unreal_stampede_edges.py` accepts the retained
public-command plans with `--plans`; every command must match an offered action
and its legal-action hash. `scripts/test_unreal_portraits.py --cards raiders`
checks the shared portrait actor. `scripts/compare_stampede_performance.py`
compares repeatable launch/advance scenes against the retained truck package.

**Review checkpoint:** inspect the playable Stampede before promoting the build
or creating any other replacement assets. Final title and roster remain deferred.


### Performance review

Two sequential 1080p trials in opposite build order compare identical seeded
commands on the same machine, with uncapped frame rate and the first 0.3 seconds
of each beat excluded. Median frame times improve by 7.67% for launch and 7.57%
for advancement. Pooled advancement p95 increases 10.72%; the individual changes
are 10.87% and 7.75%, so an increase above 10% does not repeat across both trials.
GPU medians improve in both scenes. The retained slow-frame investigation shows
substantial lifecycle-report serialization/write overhead (23.84 ms for one
900,743-character candidate report). These are instrumented Development results,
not a claim about uninstrumented shipping performance. See
`game-v001/performance-final/result.json` for raw frames and report timings.


### Playable review approval

The user approved Stampede. `game-v001/promotion.json` records the approval and
previous package. The normal launcher now uses the verified review binary.
No other replacement assets were started during promotion.
