#!/usr/bin/env bash
# Separate pilot launcher; never changes dist/current or the normal launcher.
set -euo pipefail
stampede_script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$stampede_script_dir/launch_battle_of_the_old_west.sh" \
    --package-dir "$stampede_script_dir/../dist/linux-development-stampede-review-20261003/archive" -- "$@"
