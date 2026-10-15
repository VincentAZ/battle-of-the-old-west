# Cattlemen's Club event play — user feedback, 9 September 2026

The user reported three water, a ready Cattlemen's Club, and Cannonade in hand, but
only Raid on Cattlemen's Club and Junk on Bombardment. The screenshot shows a printed
four-water cost. The user expected the discount to make the event playable.
This records one human observation, not completion of a full playtest session.

The retained physical card scan confirms Cattlemen's Club reduces event cost **by one**,
so Cannonade costs three, not one. Its trait is automatic and independent of
the camp's separate two-water Raid activation. Cannonade also requires an
open event position three.

Diagnosis: the rules already applied the discount, but the Battle Panel hid
every event Play action and showed only printed cost. Dragging an event was
the available play path. The selected-card action panel therefore appeared to
offer only Junk even when the event was affordable.

Build U adds event Play buttons, effective event costs in the hand/hover/detail
views, and a reason when a selected event cannot play. It retains drag play.
Rules regressions cover payment, camp readiness/damage/destruction, zero cost,
occupied queue space and private information. The native regression uses legal
seed 42 and real Slate clicks; results belong to the exact packaged build.

Status: implementation complete; delivery and runtime evidence are recorded in
`tests/reports/build-u-review.json` when finalized. User retest remains pending.
