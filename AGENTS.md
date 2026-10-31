# Dotfiles repository

This file governs this repository. In the shell, its root is `$DOTFILES_DIR`
(resolved from the installed symlink); otherwise use
`git rev-parse --show-toplevel`. The shared, harness-neutral guidance lives in
`agents/AGENTS.md`; this file adds repository-specific context.

## Purpose

Provide one public-safe, versioned source for shell, Git, and shared agent
configuration across Codex, Claude Code, and OpenCode without duplicating files
or tracking credentials.

## Principles

- Keep this repository small and understandable.
- Manage explicit files rather than copying entire application directories.
- Never track authentication files, cookies, tokens, histories, or caches.
- Keep machine-specific settings in untracked local overrides.
- Keep the installer safe to rerun; back up conflicts and never overwrite silently.
- Validate shell syntax and exercise installer changes against a temporary target.
- Keep shared agent guidance in `agents/AGENTS.md`; this file governs this repository.
- Preserve the existing allowlist-driven installer and its isolated tests.

## Layout

| Path | Purpose |
| --- | --- |
| `install.sh` | Allowlist-driven installer; dry-run by default |
| `shell/zshrc`, `shell/zprofile`, `shell/aliases`, `shell/utils` | Zsh configuration |
| `git/gitconfig` | Shared Git config; includes `~/.gitconfig.local` |
| `git/gitconfig.local.example` | Identity template for new machines |
| `agents/AGENTS.md` | Global guidance linked into every harness |
| `agents/skills.list` | Public skills to install from GitHub |
| `agents/install-skills.sh` | Installs skills and creates harness links |
| `tests/test_install.py` | Isolated installer tests |

## Harness-neutral links

`install.sh` links the same canonical files into each harness:

| Canonical source | Codex | Claude Code | OpenCode |
| --- | --- | --- | --- |
| `agents/AGENTS.md` | `~/.codex/AGENTS.md` | `~/.claude/CLAUDE.md` | `~/.config/opencode/AGENTS.md` |
| `~/.agents/skills/<name>` | `~/.codex/skills/<name>` | `~/.claude/skills/<name>` | `~/.config/opencode/skills/<name>` |

OpenCode also discovers `~/.agents/skills` and `~/.claude/skills` directly.
Keep the canonical copy under `agents/`, not inside a harness directory.

## Installer contract

- `./install.sh` previews; `./install.sh --apply` changes the filesystem.
- `DOTFILES_TARGET` overrides the target home for tests and staging.
- `DOTFILES_SKIP_AGENT_SKILLS=1` skips network skill installation.
- The allowlist is the `links` array in `install.sh`. Add explicit files there;
  never copy whole application directories.
- Preflight runs in both modes before any change. Conflicting files are moved
  under `~/.local/state/dotfiles/backup.*`, never silently overwritten.
- Preserve the first-run Git behavior: an existing `~/.gitconfig` is copied to
  `~/.gitconfig.local`; differing copies stop for manual merge.
- Keep the installer idempotent and safe to rerun.

## Adding or changing a managed file

1. Inspect existing conventions and confirm the file contains no secrets.
2. Add the source file under the appropriate topic directory.
3. Add `source:destination` to the `links` array in `install.sh`.
4. Update `LINKS` in `tests/test_install.py` and the README table.
5. Run the validation commands below.

## Skills

- `agents/skills.list` format: `OWNER/REPOSITORY SUBDIRECTORY SKILL_NAME`.
- Skills are cloned into `~/.agents/skills/<name>` and linked into each harness.
- The installer preflights the whole list, rejects unsafe path components,
  refuses dirty clones and unexpected origins, and backs up conflicting links.
- `install-agent-skills --dry-run` validates offline.
- Never add private repositories or credentials here. Prefer public, pinned,
  reviewed sources.

## Local overrides

Machine-specific settings stay outside the repository in `~/.zshrc.local`,
`~/.zprofile.local`, and `~/.gitconfig.local`. Never manage harness auth files,
histories, caches, or full config directories such as `~/.codex`,
`~/.claude`, or `~/.config/opencode`.

## Improving this setup

Use patterns common in mature dotfiles repositories, but keep this one small:

- Idempotent bootstrap and installer; dry-run first.
- Explicit files and topic-based grouping, not whole-directory copies.
- Local overrides for machine-specific settings.
- A `Brewfile` only if dependency installation is explicitly requested.
- A doctor/check command and CI running syntax checks plus installer tests.
- Backup and restore guidance for every managed file.
- Pinned dependency and skill versions for reproducibility.

Before proposing structural changes, read the current installer and tests and
preserve the safety guarantees above.

## Validation

```sh
bash -n install.sh agents/install-skills.sh
zsh -n shell/zshrc shell/zprofile shell/aliases shell/utils
python3 tests/test_install.py
TMP="$(mktemp -d)" DOTFILES_TARGET="$TMP" DOTFILES_SKIP_AGENT_SKILLS=1 ./install.sh --apply
```
