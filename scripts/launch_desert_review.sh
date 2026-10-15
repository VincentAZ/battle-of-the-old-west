#!/usr/bin/env bash
# Local appearance review: keep each match on the desert using the existing
# Development-build scenery override. Ordinary launcher keeps all 3 regions.
set -euo pipefail
oldwest_review_scripts="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$oldwest_review_scripts/launch_battle_of_the_old_west.sh" -OldWestVisualTest -OldWestRegionReview=0 "$@"
