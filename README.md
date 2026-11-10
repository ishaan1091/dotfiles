# Dotfiles

Personal shell, Git, and shared agent preferences, versioned in one place.

## Install

Keep this checkout at a permanent location. `shell/zshrc` resolves its own path
as `$DOTFILES_DIR`, so the repository works from any checkout location. The
shell's `clearplay` helper deletes the contents of `~/projects/playground`.

On a new Mac:

```sh
./scripts/bootstrap.sh --apply   # validate and install missing prerequisites
./install.sh --apply             # back up conflicts and create symlinks
```

`install.sh` only links files; it does not install packages or download
dependencies. Use the bootstrap for machine provisioning.

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
| `agents/memory/` | `~/.claude/memory` (native directory link) |
| `agents/integrations/claude-settings.json` | `~/.claude/settings.json` |
| `agents/integrations/opencode.json` | `~/.config/opencode/opencode.json` |

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

## Bootstrap a new Mac

`scripts/bootstrap.sh` follows the validation-first rule: it checks every
prerequisite, skips what is already present, and only changes the machine with
`--apply`.

```sh
./scripts/bootstrap.sh                       # read-only check
./scripts/bootstrap.sh --apply               # CLI essentials and shell setup
./scripts/bootstrap.sh --apply --with-apps   # also optional GUI apps
```

It validates and, when missing, installs or configures:

| Check | Action with `--apply` |
| --- | --- |
| macOS | Refuses to run on other platforms |
| Xcode Command Line Tools | Requests the Apple installer, then stops for completion |
| Homebrew | Downloads the official installer, syntax-checks it, then runs it |
| `Brewfile` packages | `brew bundle install --file Brewfile` |
| `Brewfile.apps` packages | Only with `--with-apps` |
| Oh My Zsh | `git clone`, without running its `.zshrc`-modifying installer |
| `zsh-autosuggestions`, `zsh-syntax-highlighting` | `git clone` into the Oh My Zsh plugin directory |
| iTerm2 shell integration | Downloads, syntax-checks, then installs |
| Meslo LG M Powerline fonts | Copies from the official `powerline/fonts` repository |
| VS Code CLI | Links the app's `code` binary into `~/.local/bin` |

Safety properties:

- Dry-run is the default and exits nonzero when something is missing.
- Every step is idempotent and safe to rerun.
- Remote installers are downloaded to a temporary file and validated before
  execution; the script never uses `curl | sh`.
- Git identity, `gh` authentication, macOS preferences, and Python/Node versions
  are read-only checks with instructions. They are never written automatically.
- Every run reports the status of each GUI app listed in `Brewfile.apps`.
  Installing missing GUI apps requires `--apply --with-apps`.
- The script is macOS-only and fails clearly elsewhere.

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

## Shared agent memory

Shared memory lives at `$DOTFILES_DIR/agents/memory`. Use this path in guidance
and tools. The installed `shell/zshrc` derives and exports `DOTFILES_DIR` from
its symlink, so a new shell points to the current checkout without a fixed
machine path. Start agents from that environment. If a GUI or remote session
has no `DOTFILES_DIR`, provide the checkout root explicitly before launching it.

| Harness | Integration |
| --- | --- |
| Codex | Shared guidance reads/writes `$DOTFILES_DIR/agents/memory` |
| OpenCode | Native `{env:DOTFILES_DIR}` substitution loads the index and profile from that same directory |
| Claude Code | `autoMemoryDirectory` selects `~/.claude/memory`; the installer links this native entry point to the checkout's `agents/memory` directory |

Claude's setting documents absolute and `~/` paths, not shell-variable
expansion. Its fixed native entry point is confined to the integration config
and installer. It is not an alternative canonical root. Reapply the installer
and start a new shell after moving the checkout.

The installer backs up existing integration configs before linking; it does
not merge their contents. Preserve local settings and providers before switching
to the managed files. Keep credentials outside repository-backed settings.
See [the memory workflow](agents/memory/README.md) for update rules and limits.

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
bash -n install.sh agents/install-skills.sh scripts/bootstrap.sh
zsh -n shell/zshrc shell/zprofile shell/aliases shell/utils
python3 tests/test_install.py
./scripts/bootstrap.sh
TMP="$(mktemp -d)"
DOTFILES_TARGET="$TMP" DOTFILES_SKIP_AGENT_SKILLS=1 ./install.sh --apply
./agents/install-skills.sh --dry-run
```

Only explicitly selected configuration files belong here. Do not copy entire
`~/.codex`, `~/.ssh`, or application config directories: they can contain
credentials, session data, and machine-specific state.
