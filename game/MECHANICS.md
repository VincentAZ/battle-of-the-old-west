# Mechanics and behaviour to address after the full reskin

**Hold:** the project owner, October 7, 2026: “let's get a list of mechanics that need to
be addressed AFTER the full reskin … DO NOT do anything until all reskins
done.” Record items here only. Do not investigate further, fix, or change
code or tests for them until every reskin pass is finished.

## Open items

1. **Delivery showcase test:** `scripts/test_unreal_action_showcase.py` times
   out at its final step, “match result appears after natural final
   presentation”. Seen October 7, 2026 on both
   `dist/linux-development-holdings-colour-20261007` and
   `dist/linux-development-whiskey-props-20261007` (same seed and options:
   `--require-kind water --require-kind store_water`), so it predates the
   whiskey props. All earlier delivery beats were captured; only the
   end-of-match result step fails. Logs:
   `art/action_props/whiskey_kit/package-tests/showcase-*.log`.
2. **Game-type selection screen jitters:** on the opening screen where the
   player chooses the type of game, the screen jitters whenever any selection
   is tapped. Reported by the project owner, October 7, 2026; not yet investigated.
