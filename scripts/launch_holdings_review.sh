#!/usr/bin/env bash
# Holdings review launcher; never changes dist/current or the normal launcher.
set -euo pipefail
holdings_script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$holdings_script_dir/launch_battle_of_the_old_west.sh" \
    --package-dir "$holdings_script_dir/../dist/linux-development-whiskey-props-20261007/archive" -- "$@"
