# Optional history for Western assets

the project owner approved a discreet History link on October 4, 2026, starting with
approved Western assets and adding a two-to-three-line note with each newly
approved asset. The standing requirement is in `REBRAND_GUARDRAILS.md`.

The link appears in the existing clicked-card inspector, including selected
card details in Battle Plan. It opens only on an explicit click. The note is
three authored lines; source attribution is available on the Source tooltip.
Click outside or press Escape to dismiss it. Rules, hover text, actions,
selection behavior, network state and save data remain unchanged.

`OldWestAssetHistory.h` and `OldWestCrewHistory.inl` contain presentation-only
notes with explicit source attribution. All 46 distinct Crew appearances have
their own note, resolved through the same physical-copy identity as their model
and portrait. Stampede and the generic Drifter retain their notes. Private peeks
never select history; face-down cards always use Drifter. Fictional composites
are identified as such and receive sourced occupational context.

All three Native notes are enabled: Quanah Parker for `quanah_parker`, Lozen for
her specific Pinkerton Agent copy and Sarah Winnemucca for her specific Sarah Winnemucca
copy. The same per-entity cosmetic resolver selects the model, portrait and note.
The remaining physical copies now have distinct Crew identities and sourced
notes too. Catalog previews without a physical copy use the first appearance;
live cards use their visibility-filtered cosmetic sidecar. Face-down cards and
private peeks retain only the generic Drifter note. Tribal text review remains
pending as required before art lock.

Notes currently draw on [NPS Trail Drives](https://www.nps.gov/grko/learn/historyculture/traildrives.htm),
[TSHA Quanah Parker](https://www.tshaonline.org/handbook/entries/parker-quanah),
[New Mexico Historic Women: Lozen](https://www.nmhistoricwomen.org/new-mexico-historic-women/little-sister-lozen/),
and [University of Nevada, Reno: Sarah Winnemucca](https://library.unr.edu/nevada-writers-hall-of-fame/sarah-winnemucca).
The notes are paraphrases, and the Drifter entry is historical context rather
than a fabricated biography.

The October 8 reveal-cloth pass updates the generic Drifter note with the
kerchief's documented dust-mask and neck-cover uses, sourced to
[NPS Pipe Spring, Cowboy Gear](https://www.nps.gov/pisp/learn/photosmultimedia/cowboy-gear.htm).
Its third line identifies the stranger and reveal as fictional. Private peeks
continue to select this generic note. The separate cloth prop and its public
drop are documented in `art/western/drifter/reveal-bandana-v001/`; the source
review does not replace native privacy and lifecycle verification.

The complete Crew claim-by-claim sources and reconstruction limits are retained
under `research/crew-history-audit/` and with each approved review asset. The
compact game notes do not replace that evidence or imply every visual detail
is independently documented.

## Verification

`game/tests/presentation/asset_history_tests.cpp` verifies hidden-face masking,
unchanged input data, generic canonical twins, source attribution, unique keys
and the three-line text budget. Compile it as C++20 with
`game/OldWest/Source/OldWestGame/Private` on the include path.

`scripts/test_unreal_asset_history.py` uses two native peers and legal game
commands to produce a Stampede and Drifter. It clicks the actual Slate History
link, checks that hover leaves it closed, captures the popup, checks Escape
and outside dismissal, and verifies both views and legal actions remain exactly
unchanged by history interactions. Run it with `--package-dir` and `--output`;
the default sizes are 1280×720 and 1920×1080.

Evidence is in `art/western/history/ui-v001/`. This is a text/UI change; no new
visual art assets or changes to the approved Mixar meshes are involved.

The initial History build was `dist/linux-development-history-review-20261004`.
Native checks passed at 720p (`package-v004/1280x720/result.json`) and 1080p
(`package-v005/1920x1080/result.json`), including both inspector variants.
Earlier failed test evidence is retained: the first run reported a hidden
inspector's popup state, and later harness attempts needed to expose the Battle
Plan details and wait for updated widget positions before clicking.

`preservation.json` verifies that all 840 baseline files are unchanged except
the three intended HUD source files; rules, AI, catalogs and existing Content
are unchanged. Portable rules/AI tests and the history lookup tests pass.
`promotion.json` records the executable hash and previous package. Restart via
`scripts/launch_battle_of_the_old_west.sh` to load this build; existing sessions are untouched.

Quanah's subsequent playable integration is documented in
`NATIVE_CHARACTERS_PILOT.md`. Battle Plan now places History near the identity,
above the rules, so a longer character description cannot hide the link below
the section's initial viewport.

The October 5 Native integration adds `native_cosmetics_tests.cpp` for physical
copy identity and hidden-state masking, and `test_unreal_native_copies.py` for
all three named notes in real 720p/1080p multiplayer. Evidence is retained in
`art/western/native/playable-v001/integration/`.

The October 8 bonus-whiskey pass adds a three-line supply note to the Hip Flask
asset inspector. It describes the sourced strap-side flask and the plain bar
tumbler listed by McKee in 1868, explicitly identifying the bonus glass's exact
profile as a reconstruction. Source attribution retains both the SHA/BLM
bottle history and the period catalogue. Hidden-card masking still runs first.
The optional link, unchanged authoritative views and native bonus scene were
checked in `art/western/whiskey/bonus-v002/runtime-v004/`. This remains an
incremental development review; no new launcher package has been selected.
The [bonus camera review](../art/western/whiskey/bonus-view-v007/review-v002.json)
retains the documented glass and original materials while backing the full rim
with wood for snow readability. Exact public-state and private-hand checks pass.

The October 8 Gunsmith integration adds a three-line note for canonical Gunsmith:
Freund & Brother's 1868 Laramie shop, its photographed firearms/ammunition
signs, and an explicit reconstruction statement. Attribution retains Hull's
photograph (Denver Public Library Z-5809), regional soil and native grass
references. Native legal replays in
`art/western/holdings/expansion-game-v001/gunsmith/runtime-v003/` verify click-only
viewing, hover remaining closed, Escape dismissal and unchanged complete peer
snapshots. A Drifter granted Gunsmith's ability still receives only generic
Drifter History. The v004 replay also passes its motion requirement after
adding preparation from the existing generic attack clip. This limited replay
does not imply complete presentation or release acceptance.

The October 8 Jailhouse integration adds a three-line note for canonical Jailhouse:
Fort Smith constructed its new jail in 1888, its tall barred windows lit three
tiers of cells, and this detached miniature is reconstructed. Attribution
retains the NPS nomination and early postcard; the door, end walls, proportions,
exact hues and vegetation are disclosed reconstruction. Fictional game fire
damage is explicitly distinguished from the historical building. Portable
History checks pass. Owner and opponent native replays in
`art/western/holdings/expansion-game-v001/jailhouse/runtime-{owner,opponent}-v001/`
verify click-only History, hover remaining closed, Escape dismissal and unchanged
complete peer snapshots. Legal recruitment preserves the wounded Buffalo Soldier
Veteran's appearance and bandage; restoration removes the bandage. A privately
inspected Drifter retains generic History and appearance in both views. These are
limited uninterrupted replays, not complete lifecycle or release acceptance.
Native condition portraits and exact visual
repair restoration pass in `art/western/holdings/expansion-game-v001/jailhouse/native-portraits-v001/`.

The Post Office note describes emigrant postal service at Fort Laramie, its
location within the sutler complex, and this miniature's reconstructed scope.
Attribution distinguishes the circa 1852 stone portion from the earlier adobe
store and the 1883 lime-concrete addition. Exact hues, unseen rear and fictional
damage are disclosed. All three lines meet the 52-character display limit.
Owner and opponent native replays verify click-only viewing, hover remaining
closed, Escape dismissal and unchanged complete peer snapshots in
`art/western/holdings/expansion-game-v001/post-office/runtime-{owner,opponent}-v001/`.
Legal draw-two and private-hand checks pass. Follow-up owner v002 and opponent
v003 replays also pass with the masonry residency fix (12/12 texture mips).
`art/western/holdings/expansion-game-v001/post-office/gameplay-review-v002.json`
records the inspected images. The subsequent render-only terrain-fit pilot
passes one placement in all three regions and preserves the original portrait
appearance (`art/western/holdings/ground-fit-v001/visual-review.json`). Other
placements/lifecycles remain. Revised cargo arrangements pass two-crate
readability from both seats and a counts 1–4 regression
(`art/western/delivery/cargo-layout-v001/visual-review.json`).

The Army Surgeon's Tent note describes army field hospitals, John Wiley's
1862–1864 wall tent, and the miniature's reconstructed scope. Its three lines
meet the 52-character display limit. Attribution distinguishes the Petersburg
photograph and surviving museum object from the reconstructed proportions,
summer-prairie setting and fictional burned-out condition. Evidence is in
`art/western/holdings/expansion-review-v001/army-surgeons-tent/`.
Both initial native seat replays passed optional click-only viewing, hover
remaining closed, Escape dismissal, unchanged peer snapshots and private-hand
filtering. Those captures exposed a separate treatment-camera failure, recorded
as a visual rejection rather than hidden by the technical pass. Corrected
replays and their explicit coverage limits are retained under
`art/western/holdings/expansion-game-v001/army-surgeons-tent/`.

The tent terrain follow-up records the seasonal source and reconstruction in
`art/western/holdings/ground-fit-tent-v001/winter-render-brief.json`. Final native
views pass one placement in each region; all four portrait conditions retain
the source appearance and exact repair restoration. The evidence and explicit
coverage limits are pinned in that directory’s `visual-review.json`.

Rockslide Ridge adds a three-line note about the 1872 earthquake in Yosemite,
fractured granite and the reconstructed landform. Attribution distinguishes
the modern material references, the older El Capitan avalanche and fictional
game damage. Sources, precise reconstruction limits and static reviews are in
`art/western/holdings/expansion-review-v001/rockslide-ridge/`. Both native seat
replays pass click-only History, hover remaining closed, Escape dismissal,
unchanged complete peer snapshots and private-hand filtering. Native evidence
and coverage limits are pinned in
`art/western/holdings/expansion-game-v001/rockslide-ridge/gameplay-review-v001.json`.


The Courthouse note describes Cochise County's 1882 courthouse and its service
to a growing mining town. The three lines identify the model as a reconstruction.
Attribution distinguishes documented cross-plan masonry and surviving HABS
details from reconstructed rear fenestration, chimney count, roof finish and
exact hues; its ruined condition is explicitly fictional game damage.
Source evidence is in `art/western/holdings/expansion-review-v001/courthouse/`.
History resolver and hidden-identity tests pass. Both native seat replays pass
click-only viewing, hover remaining closed, Escape dismissal, unchanged peer
snapshots and private-hand filtering. Evidence and remaining visual limits are
in `art/western/holdings/expansion-game-v001/courthouse/gameplay-review-v001.json`.

Courthouse terrain fitting now has a separately documented material scope in
`art/western/holdings/ground-fit-courthouse-v001/render-brief.json`. Three native
regional runs preserve optional History and private-hand filtering, with the
source/base meshes unchanged. The exact coverage limits and portrait repair
regression are recorded in that directory's `visual-review.json`.

Free Homestead expansion sources now include [the reviewed cabin, setting and ruin](../art/western/holdings/expansion-review-v001/free-homestead/README.md). [Three sourced History lines](../art/western/holdings/expansion-review-v001/free-homestead/history-note-v001.json) are integrated behind optional History; owner/opponent recruitment and generic Drifter privacy checks pass. Native portraits/repair and one placement in all three regions also pass; broader lifecycle/placement and packaging remain. This is an 1868–1874 Nebraska cabin-type reconstruction with fictional game damage, not an exact original building or historical fire.

Chuckwagon expansion now has [three sourced History lines](../art/western/holdings/expansion-game-v001/chuckwagon/history-note-v001.json), describing Goodnight’s 1866 adaptation and explicitly identifying the model as a reconstruction. Both native seat replays pass click-only viewing, hover staying closed, Escape dismissal, unchanged peer snapshots and generic Drifter history/mesh checks. [Gameplay review](../art/western/holdings/expansion-game-v001/chuckwagon/gameplay-review-v001.json) records readiness eligibility. [Regional ground review](../art/western/holdings/ground-fit-chuckwagon-v001/visual-review.json) now passes one placement in all three regions and post-fit condition portraits; other placements and broader lifecycle checks remain. Its charred wagon is fictional game damage, not a historical accident.

Pony Express Station now has [three sourced History lines](../art/western/holdings/expansion-game-v001/pony-express-station/history-note-v001.json) covering Simpson Springs, 1890s stage reuse and the later reconstruction. Its separate masonry ruin is explicitly fictional game damage. The note is mapped in development; CPU History privacy/line-budget tests and owner/opponent native click-only History, hover/escape and unchanged-peer-state checks pass. [Four-condition native portraits](../art/western/holdings/expansion-game-v001/pony-express-station/native-portraits-v001/visual-review.json) and exact repair pass.

Pony Express Station now also passes [both-seat Drifter return/privacy review](../art/western/holdings/ground-fit-pony-express-station-v001/drifter-sidecar-validation.json), including optional generic Drifter History. The hidden face stays concealed during withdrawal and becomes named only on legal public reentry. [Three-region placement review](../art/western/holdings/ground-fit-pony-express-station-v001/visual-review.json) and post-fit condition portraits pass at one location; broader coverage and packaging remain.

Lookout Ridge now has [three sourced History lines](../art/western/holdings/expansion-game-v001/lookout-ridge/history-note-v003.json) describing limestone, softer sediment and the overland-trail setting. Its profile and geological conditions are explicitly reconstructed/fictional, not a named summit or documented historical fall. CPU History privacy/source/line-budget tests and native owner/opponent click/hover/Escape checks pass; optional History preserves both peer states. Opponent-hand filtering passes in legal exposure replays. [Four additional native replays](../art/western/holdings/expansion-game-v001/lookout-ridge/drifter-review-v001.json) verify generic Drifter History/model before, during and after exposure from both seats, with both a hidden Trouble face and a hidden person. Private peeks remain owner-only and never select named History. [Post-fit four-condition portraits and exact repair](../art/western/holdings/expansion-game-v001/lookout-ridge/native-portraits-post-fit-v001/visual-review.json) also pass.

Gallows has [three sourced History lines prepared](../art/western/holdings/expansion-review-v001/gallows/history-note-v001.json) about Fort Smith’s 1886 oak scaffold, twelve steps and whitewash. The [reviewed static model and setting](../art/western/holdings/expansion-review-v001/gallows/README.md) depict the later roofed 1889–1890 type, with reconstruction and omitted-compound limits disclosed. The note is now mapped in development: optional click/hover/Escape behavior and unchanged peer states pass native checks from both seats, alongside CPU History/privacy/line-budget checks. The response performer/caption now uses a public last-moments reprise; privately inspected hidden Trouble and person Drifters retain generic History and visuals from both native views. Controller Skip and reconnect preserve peer state, private filtering and cleanup. Sourced terrain fitting and seasonal colour are reviewed at one placement in all three regions, with post-fit four-condition portraits and exact repair passing. An intermittent faceup death-settling timeout, thin edge/path transitions, other placements and ability types, battlefield lifecycles, effects/audio and packaging remain.

The [Sharpshooter attachment revision](../art/western/crew/attachments-v001/sharpshooter/README.md) preserves approved appearance and its sourced fictional-composite History; native portrait, optional History, privacy and reconnect pass. Gallows [Assayer final-response review](../art/western/holdings/expansion-game-v001/gallows/analysis-response-review-v002.json) now covers both rendered seats, three public reveals and an actual Ledger choice click. This is presentation continuity, with existing Western delivery props; bespoke assaying presentation and broader checks remain.

Robbers Roost has [three sourced History lines mapped](../art/western/holdings/expansion-game-v001/robbers-roost/history-note-v001.json); optional click/hover/Escape behavior and unchanged peer states pass from both seats. Its [static cabin and setting](../art/western/holdings/expansion-review-v001/robbers-roost/README.md) pass eight structure views, three setting views and saved-source checks. Upright juniper walls and bark roofing follow a documented 1890s local building method; the hideout layout and setting are reconstructed, with no claim about the ranch family’s involvement in outlaw activity. Its separate fictional charred ruin and intact/base assets are imported. Native four-condition portraits and exact repair pass; the legal Stampede one-whiskey bonus and private-hand filtering pass from both rendered seats at one pine placement. Terrain fitting and seasonal colour are now reviewed at one placement in all three regions, with post-fit four-condition portraits and exact repair passing. The resolved-herd bonus transition is corrected; natural owner/opponent replays, owner Skip and client reconnect during bonus preserve state, private filtering and cleanup. The bonus camera now keeps the full clear-glass rim against wood, reviewed at one placement in all three regions with original materials preserved. Two successive bonuses and later Stampede relaunch from pine-owner and river-opponent views pass exact peer states/actions, private filtering and cleanup. Thin apron seams/root residuals, other placements, battlefield condition lifecycles, simultaneous bonuses, other interruption timings, queued relaunch interruptions, effects/audio and packaging remain.

Smuggler’s Landing has [three sourced History lines prepared](../art/western/holdings/expansion-review-v001/smugglers-landing/history-note-v001.json), covering Rio Grande trade, the 1879 report near Roma and the reconstructed landing. Its [boat and setting review](../art/western/holdings/expansion-review-v001/smugglers-landing/README.md) passes static visual, historical, geometry-preservation and shoreline-contact checks. The native History mapping now passes click/hover/Escape, unchanged peer snapshots and opponent-hand filtering from both seats ([integration evidence](../art/western/holdings/expansion-game-v001/smugglers-landing/integration-progress-v005.json)). Broader integration remains in progress. No photographed boat operators are identified as smugglers; modern botanical and water-colour references are explicitly material analogues.

The three regional battlefield appearances are user approved. Pine and river were
approved together; the project owner approved the revised Sonoran desert on October 9,
2026 after two low dunes, 11 saguaros and eight prickly-pear groups were added.
The cactus placement stays on stable ground beside the dune reconstruction rather
than claiming saguaros grow on active dune crests. The selected package is
`linux-development-desert-scenery-20261009-v3`; all three packaged regional checks
passed, and nine protected mechanics files remained unchanged. Exact approval,
package, capture and source hashes are recorded in
`research/western-presentation/desert-approval-20261009.json`.

Bounty Office has [three sourced History lines prepared](../art/western/holdings/expansion-review-v001/bounty-office/history-note-v001.json). Its [static office and setting review](../art/western/holdings/expansion-review-v001/bounty-office/README.md) documents a fictional detached interpretation of the pre-1891 Fort Smith office portion: brick galleries, divided sash and paired gable chimneys. The note distinguishes statutory deputy fees from private rewards and does not claim an independent historical Bounty Office. Native optional-link interaction now passes from both players’ rendered views, with three legible lines, no hover expansion and unchanged peer snapshots. A newly recruited face-down Drifter retains generic appearance and History from both views. Post-fit healthy/damaged/ruined/repaired portraits pass with exact repair restoration.
