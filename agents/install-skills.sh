#!/usr/bin/env bash
# Install/update shared agent skills, then create known harness pointers.
set -euo pipefail

usage() { printf 'Usage: %s [--dry-run|--apply|-h|--help]\n' "$0"; }
apply=true
case "${1:-}" in
  --apply|'') ;;
  --dry-run) apply=false ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac
[[ $# -le 1 ]] || { usage >&2; exit 2; }

# Resolve this script through symlinks so the repository root is stable.
source_path="${BASH_SOURCE[0]}"
while [[ -L "$source_path" ]]; do
  source_parent="$(cd -- "$(dirname -- "$source_path")" && pwd -P)"
  source_target="$(readlink "$source_path")"
  [[ "$source_target" = /* ]] || source_target="$source_parent/$source_target"
  source_path="$source_target"
done
repo_dir="$(cd -- "$(dirname -- "$source_path")/.." && pwd -P)"
target_dir="${DOTFILES_TARGET:-$HOME}"
[[ "$target_dir" = /* ]] || { echo 'DOTFILES_TARGET must be absolute' >&2; exit 2; }
list="$repo_dir/agents/skills.list"
root="$target_dir/.agents/skills"
backup_root="$target_dir/.local/state/dotfiles/agent-skills"

fail() { printf '%s\n' "$*" >&2; exit 1; }

# Repository, directory, and skill names are single path components. Reject
# traversal, option-like names, and anything outside the supported format.
valid_component() {
  [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]] && [[ "$1" != *..* ]]
}
valid_subdir() { [[ "$1" == . ]] || valid_component "$1"; }

[[ -f "$list" ]] || fail "Missing skill list: $list"

# Preflight every entry before creating directories, cloning, or linking.
entries=()
while read -r repository subdir name extra; do
  [[ -z "${repository:-}" || "$repository" == \#* ]] && continue
  [[ -n "${subdir:-}" && -n "${name:-}" && -z "${extra:-}" ]] \
    || fail "Invalid skills.list entry: $repository $subdir $name $extra"
  [[ "$repository" == */* && "$repository" != */*/* ]] \
    || fail "Invalid repository in skills.list: $repository"
  owner="${repository%%/*}"
  repo="${repository#*/}"
  valid_component "$owner" && valid_component "$repo" \
    || fail "Invalid repository in skills.list: $repository"
  valid_subdir "$subdir" && valid_component "$name" \
    || fail "Invalid skill path in skills.list: $repository $subdir $name"
  entries+=("$repository" "$subdir" "$name")
done < "$list"

if ! "$apply"; then
  for ((i = 0; i < ${#entries[@]}; i += 3)); do
    display_path="${entries[i + 1]}"
    [[ "$display_path" == . ]] && display_path=""
    printf 'Would install %s from https://github.com/%s/tree/main/%s\n' \
      "${entries[i + 2]}" "${entries[i]}" "$display_path"
  done
  exit 0
fi

mkdir -p "$root"
for ((i = 0; i < ${#entries[@]}; i += 3)); do
  repository="${entries[i]}"
  subdir="${entries[i + 1]}"
  name="${entries[i + 2]}"
  destination="$root/$name"
  if [[ -d "$destination/.git" ]]; then
    origin="$(git -C "$destination" remote get-url origin)"
    [[ "$origin" == "https://github.com/$repository.git" || "$origin" == "https://github.com/$repository" ]] \
      || fail "Wrong origin at $destination; refusing update"
    [[ -z "$(git -C "$destination" status --porcelain)" ]] \
      || fail "Local changes at $destination; preserve/review them before updating"
    git -C "$destination" pull --ff-only origin main
  elif [[ -e "$destination" || -L "$destination" ]]; then
    fail "Existing non-managed skill at $destination; refusing to replace it"
  else
    mkdir -p "$(dirname -- "$destination")"
    git clone --depth 1 "https://github.com/$repository.git" "$destination"
  fi
  skill="$destination/$subdir"
  [[ -f "$skill/SKILL.md" ]] || fail "Missing SKILL.md at $skill"
  for link in \
    "$target_dir/.codex/skills/$name" \
    "$target_dir/.claude/skills/$name" \
    "$target_dir/.config/opencode/skills/$name"; do
    mkdir -p "$(dirname -- "$link")"
    if [[ -L "$link" && "$(readlink "$link")" == "$skill" ]]; then
      continue
    elif [[ -e "$link" || -L "$link" ]]; then
      mkdir -p "$backup_root"
      relative="${link#"$target_dir"/}"
      backup="$backup_root/${relative//\//-}-$(date +%Y%m%d%H%M%S)-$$"
      [[ ! -e "$backup" && ! -L "$backup" ]] || fail "Backup already exists: $backup"
      mv -- "$link" "$backup"
      printf 'Backed up %s to %s\n' "$link" "$backup"
    fi
    ln -s -- "$skill" "$link"
    printf 'Linked %s -> %s\n' "$link" "$skill"
  done
  display_path="$subdir"
  [[ "$display_path" == . ]] && display_path=""
  printf 'Installed %s from https://github.com/%s/tree/main/%s\n' \
    "$name" "$repository" "$display_path"
done
