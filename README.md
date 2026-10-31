# Dotfiles

Personal shell, Git, and shared agent preferences, versioned in one place.

## Install

Keep this checkout at a permanent location. `shell/zshrc` resolves its own path
as `$DOTFILES_DIR`, so the repository works from any checkout location. The
shell's `clearplay` helper deletes the contents of `~/projects/playground`.

```sh
./install.sh             # preview changes
./install.sh --apply     # back up conflicts and create symlinks
```

Requires Bash, Zsh, and Git. Oh My Zsh and its optional plugins are used when
already installed; the installer does not download dependencies.

| Repository file | Installed location |
| --- | --- |
| `shell/zshrc` | `~/.zshrc` |
| `shell/zprofile` | `~/.zprofile` |
| `shell/aliases` | `~/.aliases` |
| `shell/utils` | `~/.utils` |
| `git/gitconfig` | `~/.gitconfig` |
| `agents/AGENTS.md` | `~/.codex/AGENTS.md` |
| `agents/AGENTS.md` | `~/.claude/CLAUDE.md` |
| `agents/AGENTS.md` | `~/.config/opencode/AGENTS.md` |
| `agents/install-skills.sh` | `~/.local/bin/install-agent-skills` |

Edits to these installed symlinks update the repository directly. The installer
skips links that already point to this checkout. Conflicting files and symlinks
are moved into a unique directory under `~/.local/state/dotfiles/`.

On first install, an existing regular `~/.gitconfig` is also copied to
`~/.gitconfig.local`, preserving identity and authentication settings outside
Git. If both files already exist and are identical, installation can resume.
If they differ, the installer stops before changing anything so you can merge
them. An existing `.gitconfig` symlink is backed up with a warning, and its
settings are not automatically copied into `.gitconfig.local`. On a fresh machine, copy `git/gitconfig.local.example` to
`~/.gitconfig.local` and fill in your identity.

## Validation and recovery

Both dry-run and apply modes check every source file, destination parent, backup
parent, and the local Git include before changing anything. Dry runs report
conflicts using `backup.<unique>` as a placeholder; apply mode creates a unique
backup directory and prints the actual paths. Equivalent links are left alone,
including links through a symlinked parent directory.

Preflight catches predictable configuration errors; installation is not atomic.
An unexpected runtime error stops the script, preserving completed changes and
backups. Fix the cause and rerun: installed links are skipped, and identical
Git config copies are accepted. Inspect the printed backup directory if a file
was moved before its replacement link could be created. Avoid editing configs
or running another installer concurrently.

## Local overrides

Use `~/.zshrc.local`, `~/.zprofile.local`, and `~/.gitconfig.local` for settings
specific to a machine. These are not managed by the repository.

## Shared agent guidance

`agents/AGENTS.md` is the single source of truth for Codex, Claude Code, and
OpenCode. The installer links it to each harness's global instruction file:

| Harness | Instruction file | Skills directory |
| --- | --- | --- |
| Codex | `~/.codex/AGENTS.md` | `~/.codex/skills` |
| Claude Code | `~/.claude/CLAUDE.md` | `~/.claude/skills` |
| OpenCode | `~/.config/opencode/AGENTS.md` | `~/.config/opencode/skills` |

OpenCode also discovers `~/.agents/skills` and `~/.claude/skills` directly.
Start a new agent session after changing the shared file. A pre-existing
`~/.codex/AGENTS.override.md` takes precedence over the Codex link.

The shared file includes the plan-first workflow and security baseline.
Repository-specific maintenance guidance lives in this repository's
`AGENTS.md`, which agents load automatically when working here. Plans belong in
`~/agents/plans/` as `YYYY-MM-DD-<slug>.md`; they are personal working documents
and are not tracked here.

## Agent skills

`agents/skills.list` lists public skills to install from GitHub, one per line:

```text
# OWNER/REPOSITORY SUBDIRECTORY SKILL_NAME
ishaan1091/publish-html . publish-html
```

`./install.sh --apply` runs `install-agent-skills`, which clones or updates each
skill into `~/.agents/skills/<name>` and links it into the harness directories
above. The installer refuses dirty clones and unexpected remotes, and backs up
unmanaged destinations under `~/.local/state/dotfiles/agent-skills/`. Set
`DOTFILES_SKIP_AGENT_SKILLS=1` when you need an offline install.

Use `install-agent-skills --dry-run` to validate the list without network or
filesystem changes. Add only public, reviewed repositories; never list private
repositories or credentials.

## Restore a previous file

Find the file in the backup directory printed during installation. Remove its
installed symlink, then move the backup back to its original location. Existing
Git settings are also preserved in `~/.gitconfig.local`.

## Validate

The isolated installer tests require Python 3 and use temporary repository copies
and target directories; they do not install anything into your home.

```sh
bash -n install.sh agents/install-skills.sh
zsh -n shell/zshrc shell/zprofile shell/aliases shell/utils
python3 tests/test_install.py
TMP="$(mktemp -d)"
DOTFILES_TARGET="$TMP" DOTFILES_SKIP_AGENT_SKILLS=1 ./install.sh --apply
./agents/install-skills.sh --dry-run
```

Only explicitly selected configuration files belong here. Do not copy entire
`~/.codex`, `~/.ssh`, or application config directories: they can contain
credentials, session data, and machine-specific state.
