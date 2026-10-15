# Battle of the Old West — development notes

> The Unreal project folder, module and targets keep their original internal
> names (`game/OldWest`, `OldWestGame`). Players never see them; renaming
> them is a tracked backlog item because it touches every build and test script.

## Run the game

- **Built package:** from the repository root run
  `scripts/launch_battle_of_the_old_west.sh`. It follows the `dist/current`
  symlink. A copied package carries its own launcher.
- **Editor:** build `OldWestGameEditor`, open `OldWest/OldWest.uproject`
  with Unreal Engine 5.8.2 and press Play in a standalone window.
- **Controls and connections:** see the [player guide](PLAYER_GUIDE.md) and
  [remote play](REMOTE_PLAY.md).

## Build and test

Example Linux editor build using an installed engine:

```bash
~/Applications/UnrealEngine-5.8.2/Engine/Build/BatchFiles/Linux/Build.sh \
  OldWestGameEditor Linux Development \
  ~/Repos/battle-of-the-old-west/game/OldWest/OldWest.uproject \
  -NoHotReload -NoUBA -MaxParallelActions=2
```

`-NoUBA` avoids an observed accelerator/compiler crash. Runtime game rules are
ordinary C++; the Python scripts are asset, packaging and verification tools.

Portable rules and AI tests, from the repository root:

```bash
cmake -S game/tests/core -B /tmp/old-west-core-build -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/old-west-core-build -j2
ctest --test-dir /tmp/old-west-core-build --output-on-failure
```

Native Unreal checks each launch real processes and record their evidence
under a run folder:

- `scripts/test_unreal_multiplayer.py --render-client --timeout 420`: a server
  and two clients play a match through real RPCs; public states must agree and
  private information must stay private.
- `scripts/test_unreal_singleplayer.py`: complete offline games across all
  difficulties and both rulesets, rematch, privacy and profile preservation.
- `scripts/test_unreal_listen_host.py`: Host a Match, a complete two-player
  match, rematch, guest reconnect, host departure and normal Quit.
- `scripts/test_unreal_reconnect_restart.py`: application exit, forced process
  death, fresh sessions and invalid or duplicate seat claims.
- `scripts/test_unreal_hud.py`: two-resolution screenshots, public and private
  inspection, 3D picking and cinematic control visibility.
- `scripts/test_unreal_settings.py`: display trials and rollback, quality,
  frame cap, volume and restart persistence.
- `scripts/test_unreal_cinematics.py --audio`: impact timing, camera
  visibility, death presentation and a recording of the output mix;
  `scripts/analyze_game_audio.py <recording.wav>` checks that recording.

`scripts/package_oldwest.py --build --output <dir>` builds, cooks and stages
a Linux Development package and validates the executable, cooked containers
and packaged card data. `--validate <dir>` re-checks an existing package and
`scripts/record_package_runtime.py` attaches runtime reports to the copy they
tested. Windows packaging is described in [WINDOWS_BUILD.md](WINDOWS_BUILD.md).

## Rules and data

`data/cards.json` and `OldWest/Content/Data/cards.json` are generated
together by `../scripts/build_card_catalog.py`: 104 definitions covering 26
crew, 10 Trouble cards, 34 revised base holdings, 32 Boomtown holdings, the
Stampede and the Hip Flask. Canonical card IDs are frozen. The Western display
names live in `../scripts/western_terms.py`, which writes
`data/western-terms.json` and the generated `OldWestWesternTerms.inl` that the
HUD applies at render time.

The authoritative engine lives in `OldWest/Source/OldWestGame/Private/Core/`.
It owns legality, sequencing, choices, random state and wins; the HUD only
presents server-validated moves. Uncommon interactions that the rules do not
settle conclusively are implemented as labelled interpretation policies in the
catalog rulesets. The in-game Rules panel reads
`OldWest/Content/Data/rules-help.json`, which is maintained by hand.

Known mechanics issues are logged in [MECHANICS.md](MECHANICS.md) and held
until the Western presentation is approved as a whole; see
[REBRAND_GUARDRAILS.md](REBRAND_GUARDRAILS.md).

## Art sources and editable assets

- Depot environment Blender source: `../art/water_depot_v2/WaterDepot.blend`.
- Main Unreal map: `/Game/Maps/WaterDepotV2`.
- Crew rig and costume work: `../art/characters/`.
- Holding set work: `../art/camps/` and the Western passes under `../art/western/`.
- Continuous terrain and distant landscape: `../art/world/`.
- Original synthesized ambience and effects: `../art/audio/`.

`../scripts/fetch_depot_assets.py` fetches the public CC0 photographic
materials and verifies their recorded hashes. Attribution for third-party
components and assets is in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
Historical sourcing for every rendered person and building is recorded in
[ASSET_HISTORY.md](ASSET_HISTORY.md) and the research folder.

## Current priorities

Art, effects, sound and human playtesting, under the appearance-approval gate
in [REBRAND_GUARDRAILS.md](REBRAND_GUARDRAILS.md). The active pilots are
[holdings](HOLDINGS_PILOT.md), [drifters](DRIFTER_PILOT.md),
[the Stampede](STAMPEDE_PILOT.md) and
[Native leaders](NATIVE_CHARACTERS_PILOT.md). Deferred release buckets are in
[BACKLOG.md](BACKLOG.md).
