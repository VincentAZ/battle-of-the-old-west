#!/usr/bin/env bash
# Launch a staged Development build. All Unreal arguments and the caller's
# rendering, audio, Vulkan, and library environment are passed through intact.
set -euo pipefail

oldwest_script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
oldwest_package_dir="${OLDWEST_PACKAGE_DIR:-}"
oldwest_project_name="${OLDWEST_PROJECT_NAME:-OldWest}"
oldwest_target_name="${OLDWEST_TARGET_NAME:-OldWestGame}"
oldwest_default_output="$oldwest_script_dir/../dist/linux-development"
if [[ -d "$oldwest_script_dir/../dist/current" ]]; then
    oldwest_default_output="$oldwest_script_dir/../dist/current"
fi
oldwest_output_root="${OLDWEST_PACKAGE_ROOT:-$oldwest_default_output}"

if [[ "${1:-}" == "--help" ]]; then
    cat <<'EOF'
Usage: launch_battle_of_the_old_west.sh [--package-dir DIRECTORY] [--] [Unreal arguments...]

Examples:
  launch_battle_of_the_old_west.sh
  launch_battle_of_the_old_west.sh -windowed -ResX=1920 -ResY=1080
  launch_battle_of_the_old_west.sh '127.0.0.1:7777'

OLDWEST_PACKAGE_DIR overrides package discovery. OLDWEST_BINARY selects an
explicit executable. No quality, resolution, fullscreen, or driver setting is
forced. This script needs an already packaged game, not Unreal Editor.
EOF
    exit 0
fi
if [[ "${1:-}" == "--package-dir" ]]; then
    if [[ $# -lt 2 ]]; then
        printf '%s\n' '--package-dir needs a directory.' >&2
        exit 2
    fi
    oldwest_package_dir="$2"
    shift 2
fi
if [[ "${1:-}" == "--" ]]; then shift; fi

if [[ -z "$oldwest_package_dir" ]]; then
    for oldwest_candidate in \
        "$oldwest_script_dir" \
        "$oldwest_output_root/archive" \
        "$oldwest_output_root/archive/Linux" \
        "$oldwest_output_root/stage" \
        "$oldwest_output_root/stage/Linux"; do
        if [[ -d "$oldwest_candidate/$oldwest_project_name/Binaries/Linux" ]]; then
            oldwest_package_dir="$oldwest_candidate"
            break
        fi
    done
fi
if [[ -z "$oldwest_package_dir" && -n "${OLDWEST_BINARY:-}" ]]; then
    # An explicit binary can be launched independently of package discovery.
    oldwest_package_dir="$(dirname -- "$OLDWEST_BINARY")"
fi
if [[ -z "$oldwest_package_dir" || ! -d "$oldwest_package_dir" ]]; then
    printf '%s\n' 'No packaged Battle of the Old West build found. Build it with scripts/package_oldwest.py --build, or set OLDWEST_PACKAGE_DIR.' >&2
    exit 1
fi
oldwest_package_dir="$(cd -- "$oldwest_package_dir" && pwd)"
for oldwest_child in Linux LinuxNoEditor; do
    if [[ -d "$oldwest_package_dir/$oldwest_child/$oldwest_project_name/Binaries/Linux" ]]; then
        oldwest_package_dir="$oldwest_package_dir/$oldwest_child"
        break
    fi
done
oldwest_binary="${OLDWEST_BINARY:-$oldwest_package_dir/$oldwest_project_name/Binaries/Linux/$oldwest_target_name}"
if [[ -z "${OLDWEST_BINARY:-}" && ! -f "$oldwest_binary" ]]; then
    oldwest_binary="$oldwest_package_dir/$oldwest_project_name/Binaries/Linux/$oldwest_target_name-Linux-Development"
fi
if [[ ! -x "$oldwest_binary" ]]; then
    printf 'Packaged executable is absent or not executable: %s\n' "$oldwest_binary" >&2
    exit 1
fi
# Resolve a relative caller-supplied binary before changing working directory.
oldwest_binary="$(realpath -- "$oldwest_binary")"
cd -- "$oldwest_package_dir"
# Unreal's generated Linux bootstrap passes the short project name as argv[1].
exec "$oldwest_binary" "$oldwest_project_name" "$@"
