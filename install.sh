#!/usr/bin/env bash
# Stop after errors. Completed changes are not automatically rolled back.
set -euo pipefail

usage() { printf 'Usage: %s [--dry-run|--apply|-h|--help]\n' "$0"; }
apply=false
[[ $# -le 1 ]] || { usage >&2; exit 2; }
case "${1:---dry-run}" in
  --apply) apply=true ;;
  --dry-run) ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac

# Resolve the script itself through symlinks, including relative link targets.
script_path="${BASH_SOURCE[0]}"
link_depth=0
while [[ -L "$script_path" ]]; do
  link_depth=$((link_depth + 1))
  [[ $link_depth -le 40 ]] || { echo 'Too many script symlinks' >&2; exit 1; }
  script_parent="$(cd -- "$(dirname -- "$script_path")" && pwd -P)"
  script_path="$(readlink "$script_path")"
  [[ "$script_path" = /* ]] || script_path="$script_parent/$script_path"
done
repo_dir="$(cd -- "$(dirname -- "$script_path")" && pwd -P)"
target_dir="${DOTFILES_TARGET:-$HOME}"
[[ "$target_dir" = /* ]] || { echo 'DOTFILES_TARGET must be absolute' >&2; exit 2; }

# One allowlist drives validation, reporting, and installation.
links=(
  'shell/zshrc:.zshrc'
  'shell/zprofile:.zprofile'
  'shell/aliases:.aliases'
  'shell/utils:.utils'
  'git/gitconfig:.gitconfig'
  'agents/AGENTS.md:.codex/AGENTS.md'
)
backup_root="$target_dir/.local/state/dotfiles"
backup_dir=""

fail() { printf '%s\n' "$*" >&2; exit 1; }

# Missing ancestors can be created later. Any existing ancestor must be a
# directory; explicitly detect dangling symlinks rather than treating them as absent.
check_directory() {
  local ancestor="$1"
  while [[ ! -e "$ancestor" && ! -L "$ancestor" ]]; do
    ancestor="$(dirname -- "$ancestor")"
  done
  [[ -d "$ancestor" ]] || fail "Not a directory: $ancestor; no files changed."
}

# -ef compares the underlying file, so relative symlinks, hardlinks, and a
# destination reached through a symlinked parent are all recognized as installed.
already_linked() { [[ "$1" -ef "$2" ]]; }

# Preflight is read-only in BOTH modes and runs before any copy, move, or mkdir.
for entry in "${links[@]}"; do
  source="$repo_dir/${entry%%:*}"
  destination="$target_dir/${entry#*:}"
  [[ -f "$source" ]] || fail "Missing or non-file source: $source; no files changed."
  check_directory "$(dirname -- "$destination")"
done
check_directory "$backup_root"

# Parse Git syntax rather than accepting a mention in a comment or wrong section.
# --no-includes prevents reading the user's local file during this check.
include_paths="$(git config --no-includes --file "$repo_dir/git/gitconfig" --get-all include.path)" \
  || fail 'git/gitconfig must include ~/.gitconfig.local; no files changed.'
include_found=false
while IFS= read -r include_path; do
  [[ "$include_path" != '~/.gitconfig.local' ]] || include_found=true
done <<< "$include_paths"
"$include_found" || fail 'git/gitconfig must include ~/.gitconfig.local; no files changed.'

# Retain local Git settings before replacing a regular config. Identical copies
# are safe to resume after interruption; differing copies require a manual merge.
gc="$target_dir/.gitconfig"
preserve_git=false
if ! already_linked "$gc" "$repo_dir/git/gitconfig"; then
  if [[ -f "$gc" && ! -L "$gc" ]]; then
    if [[ -e "$gc.local" || -L "$gc.local" ]]; then
      if [[ -f "$gc.local" ]] && cmp -s -- "$gc" "$gc.local"; then
        printf 'Existing Git settings already preserved: %s\n' "$gc.local"
      else
        fail 'Existing .gitconfig and .gitconfig.local differ; merge manually. No files changed.'
      fi
    else
      preserve_git=true
    fi
  elif [[ -L "$gc" ]]; then
    printf 'Warning: %s is a symlink; it will be backed up, but its settings will not be copied to .gitconfig.local.\n' "$gc" >&2
  elif [[ -e "$gc" ]]; then
    fail "Git configuration is not a regular file: $gc; no files changed."
  fi
fi

# Reserve a unique backup directory only when applying an actual conflict.
# Dry runs show a placeholder because reserving a directory would mutate disk.
backup() {
  local destination="$1" relative="$2"
  if [[ -z "$backup_dir" ]]; then
    mkdir -p "$backup_root"
    backup_dir="$(mktemp -d "$backup_root/backup.XXXXXXXX")"
  fi
  printf 'Conflict: %s will be backed up to %s/%s\n' "$destination" "$backup_dir" "$relative"
  mkdir -p "$backup_dir/$(dirname -- "$relative")"
  mv -- "$destination" "$backup_dir/$relative"
}

link_file() {
  local source="$repo_dir/$1" relative="$2" destination="$target_dir/$2"
  if already_linked "$destination" "$source"; then
    printf 'Already linked: %s\n' "$destination"
    return
  fi
  if [[ -e "$destination" || -L "$destination" ]]; then
    if "$apply"; then
      backup "$destination" "$relative"
    else
      printf 'Conflict: %s will be backed up to %s/backup.<unique>/%s\n' "$destination" "$backup_root" "$relative"
    fi
  fi
  printf 'Link %s → %s\n' "$destination" "$source"
  if "$apply"; then
    mkdir -p "$(dirname -- "$destination")"
    # No forced overwrites. A concurrent change causes failure instead.
    ln -s -- "$source" "$destination"
  fi
}

if "$preserve_git"; then
  printf 'Preserve existing Git settings in %s.local\n' "$gc"
  if "$apply"; then
    cp -p -- "$gc" "$gc.local"
  fi
fi
for entry in "${links[@]}"; do
  link_file "${entry%%:*}" "${entry#*:}"
done

if ! "$apply"; then
  printf 'Dry run only. Run %s --apply to install.\n' "$0"
elif [[ -n "$backup_dir" ]]; then
  printf 'Backups: %s\n' "$backup_dir"
fi
