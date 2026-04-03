#!/usr/bin/env bash
#
# Deploy the addon to a Home Assistant instance over Samba (SMB).
#
# Usage:
#   ./deploy.sh                        # uses defaults from env / .deploy.env
#   ./deploy.sh -H 192.168.1.100       # override HA IP
#   ./deploy.sh -H 192.168.1.100 -f addons/gridmate
#   ./deploy.sh -H 192.168.1.100 -u username -p password
#
# The script copies only the files needed for the addon (mirroring the
# Dockerfile COPY directives), skipping dev-only artefacts like venv/,
# __pycache__/, .env, docs/, etc.
#
# Configuration can be provided via:
#   1. Command-line flags (highest priority)
#   2. Environment variables
#   3. The .env file in the same directory as this script (lowest priority)
#
# Environment variables / .env keys:
#   HA_HOST        – IP or hostname of the HA instance
#   HA_SMB_SHARE   – Samba share name (default: "addons")
#   HA_ADDON_FOLDER– Folder inside the share (default: "gridmate")
#   HA_SMB_USER    – Samba username (default: empty / guest)
#   HA_SMB_PASS    – Samba password (default: empty / guest)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Load .env if present ─────────────────────────────────────────────────────
ENV_FILE="$SCRIPT_DIR/.env"
if [[ -f "$ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    set -a
    source "$ENV_FILE"
    set +a
fi

# ── Defaults ─────────────────────────────────────────────────────────────────
HA_HOST="${HA_HOST:-}"
HA_SMB_SHARE="${HA_SMB_SHARE:-addons}"
HA_ADDON_FOLDER="${HA_ADDON_FOLDER:-gridmate}"
HA_SMB_USER="${HA_SMB_USER:-}"
HA_SMB_PASS="${HA_SMB_PASS:-}"
RESTART_ADDON="${RESTART_ADDON:-false}"
DRY_RUN=false

# ── Parse CLI flags ─────────────────────────────────────────────────────────
usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Deploy the GridMate addon to a Home Assistant instance via Samba.

Options:
  -H, --host HOST         HA IP address or hostname (required)
  -s, --share SHARE       Samba share name           [default: addons]
  -f, --folder FOLDER     Addon folder inside share  [default: gridmate]
  -u, --user USER         Samba username             [default: guest]
  -p, --password PASS     Samba password             [default: guest]
  -n, --dry-run           Show what would be copied without actually copying
  -h, --help              Show this help message

Environment / .env:
  HA_HOST, HA_SMB_SHARE, HA_ADDON_FOLDER, HA_SMB_USER, HA_SMB_PASS

Example .env:
  HA_HOST=192.168.1.100
  HA_SMB_SHARE=addons
  HA_ADDON_FOLDER=gridmate
  HA_SMB_USER=
  HA_SMB_PASS=
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -H|--host)      HA_HOST="$2";          shift 2 ;;
        -s|--share)     HA_SMB_SHARE="$2";     shift 2 ;;
        -f|--folder)    HA_ADDON_FOLDER="$2";  shift 2 ;;
        -u|--user)      HA_SMB_USER="$2";      shift 2 ;;
        -p|--password)  HA_SMB_PASS="$2";      shift 2 ;;
        -n|--dry-run)   DRY_RUN=true;          shift   ;;
        -h|--help)      usage ;;
        *)              echo "Unknown option: $1"; usage ;;
    esac
done

# ── Validate ─────────────────────────────────────────────────────────────────
if [[ -z "$HA_HOST" ]]; then
    echo "Error: HA_HOST is required. Pass -H <ip> or set HA_HOST in .deploy.env"
    exit 1
fi

# ── Check dependencies ───────────────────────────────────────────────────────
if ! command -v smbclient &>/dev/null; then
    echo "Error: 'smbclient' is not installed."
    echo "  Install it with:  sudo apt install smbclient"
    exit 1
fi

# ── Build SMB auth ───────────────────────────────────────────────────────────
SMB_TARGET="//${HA_HOST}/${HA_SMB_SHARE}"

SMB_AUTH_ARGS=()
if [[ -n "$HA_SMB_USER" && -n "$HA_SMB_PASS" ]]; then
    SMB_AUTH_ARGS=(-U "${HA_SMB_USER}%${HA_SMB_PASS}")
elif [[ -n "$HA_SMB_USER" ]]; then
    SMB_AUTH_ARGS=(-U "${HA_SMB_USER}%")
else
    SMB_AUTH_ARGS=(-N)  # no password / guest
fi

# ── Files & directories to deploy (mirrors Dockerfile) ──────────────────────
# These paths are relative to the addon source directory ($SCRIPT_DIR)
DEPLOY_FILES=(
    "app.py"
    "config.yaml"
    "requirements.txt"
    "run.sh"
    "Dockerfile"
)

DEPLOY_DIRS=(
    "web"
    "translations"
)

# Patterns to exclude when copying directories
EXCLUDE_PATTERNS=(
    "__pycache__"
    "*.pyc"
    "*.pyo"
    ".DS_Store"
)

# ── Helper functions ─────────────────────────────────────────────────────────
smb_cmd() {
    # Execute one or more smbclient commands
    local cmds="$1"
    if [[ "$DRY_RUN" == "true" ]]; then
        echo "  [dry-run] smbclient ${SMB_TARGET} ${SMB_AUTH_ARGS[*]} -c \"$cmds\""
        return 0
    fi
    smbclient "${SMB_TARGET}" "${SMB_AUTH_ARGS[@]}" -c "$cmds" 2>&1
}

smb_mkdir_p() {
    # Recursively create directories on the SMB share
    local dir="$1"
    local parts
    IFS='/' read -ra parts <<< "$dir"
    local path=""
    for part in "${parts[@]}"; do
        [[ -z "$part" ]] && continue
        if [[ -z "$path" ]]; then
            path="$part"
        else
            path="$path/$part"
        fi
        smb_cmd "mkdir \"$path\"" 2>/dev/null || true
    done
}

should_exclude() {
    local name="$1"
    for pattern in "${EXCLUDE_PATTERNS[@]}"; do
        # shellcheck disable=SC2254
        case "$name" in
            $pattern) return 0 ;;
        esac
    done
    return 1
}

deploy_file() {
    local local_path="$1"   # relative to SCRIPT_DIR
    local remote_dir="$2"   # remote directory (inside share)

    echo "  Copying: $local_path -> $remote_dir/$(basename "$local_path")"
    if [[ "$DRY_RUN" != "true" ]]; then
        smb_cmd "cd \"$remote_dir\"; put \"${SCRIPT_DIR}/${local_path}\" \"$(basename "$local_path")\""
    fi
}

deploy_directory() {
    local local_dir="$1"    # relative to SCRIPT_DIR
    local remote_base="$2"  # remote base directory

    # Create the remote directory
    local remote_dir="${remote_base}/${local_dir}"
    smb_mkdir_p "$remote_dir"

    # Iterate over contents
    local entry
    for entry in "${SCRIPT_DIR}/${local_dir}"/*; do
        local name
        name="$(basename "$entry")"

        # Check exclusions
        if should_exclude "$name"; then
            echo "  Skipping: ${local_dir}/${name} (excluded)"
            continue
        fi

        if [[ -d "$entry" ]]; then
            deploy_directory "${local_dir}/${name}" "$remote_base"
        elif [[ -f "$entry" ]]; then
            deploy_file "${local_dir}/${name}" "$remote_dir"
        fi
    done
}

# ── Main ─────────────────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              GridMate Addon Deploy Script                   ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Target:  ${SMB_TARGET}/${HA_ADDON_FOLDER}"
echo "  Source:  ${SCRIPT_DIR}"
[[ "$DRY_RUN" == "true" ]] && echo "  Mode:    DRY RUN (no files will be copied)"
echo ""

# Test SMB connectivity
echo "── Testing connection to ${SMB_TARGET} ──"
if [[ "$DRY_RUN" != "true" ]]; then
    if ! smb_cmd "ls" &>/dev/null; then
        echo "Error: Cannot connect to ${SMB_TARGET}"
        echo "  Check that the Samba share addon is running and the IP/credentials are correct."
        exit 1
    fi
    echo "  Connection OK"
fi
echo ""

# Ensure the addon folder exists
echo "── Creating addon folder: ${HA_ADDON_FOLDER} ──"
smb_mkdir_p "${HA_ADDON_FOLDER}"
echo ""

# Deploy individual files
echo "── Deploying files ──"
for f in "${DEPLOY_FILES[@]}"; do
    deploy_file "$f" "${HA_ADDON_FOLDER}"
done
echo ""

# Deploy directories
echo "── Deploying directories ──"
for d in "${DEPLOY_DIRS[@]}"; do
    deploy_directory "$d" "${HA_ADDON_FOLDER}"
done
echo ""

echo "── Deploy complete! ──"
echo ""
echo "Next steps:"
echo "  1. In Home Assistant, go to Settings → Add-ons → GridMate"
echo "  2. Click 'Rebuild' to apply the changes"
echo "  3. Check the addon logs for any errors"
