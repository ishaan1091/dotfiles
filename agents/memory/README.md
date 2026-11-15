# Starter context

`$DOTFILES_DIR/agents/memory/about-me.md` is the versioned starting profile.
Setup duplicates it into independent local files for Codex and OpenCode only:

| Harness | Local file |
| --- | --- |
| Codex | `~/.codex/memory.md` |
| OpenCode | `~/.config/opencode/memory.md` |

## Automatic initialization

Run `./install.sh` to preview or `./install.sh --apply` to initialize. No manual
import, extra prompt, or memory instruction in the shared `AGENTS.md` is needed.
Python 3.11+ is required; the CLI Brewfile supplies it through bootstrap.

The installer invokes `scripts/seed-agent-memory.py`. It validates the profile,
destinations, and native configs before any installer changes, then creates
missing copies by publishing fully written files without overwriting existing
files. An interrupted seed write leaves no partial destination to block a retry.
Existing memory files are kept exactly as they are. They must be regular local files, not symlinks or paths
inside the repository.

Codex's local `developer_instructions` tells it to read its `memory.md` at
session start and keep durable personal updates there. Existing developer
instructions are retained. OpenCode's local `instructions` array loads its
own `memory.md` alongside any existing instruction files. Changed local configs
are backed up under `~/.local/state/dotfiles/backup.memory-config.*`.

The helper merges JSON or JSONC OpenCode configuration, preserving comments
and other settings. It rejects invalid configuration and unsafe symlinks.
Config and memory files stay local; nothing is linked back to this checkout.
Native configuration or policy overrides can still affect session loading.

## After initialization

Start new harness sessions. Each local file can evolve independently. Rerunning
setup does not refresh it from the starter, overwrite edits, or duplicate config
entries. Other harnesses are outside the scope of initialization. Codex's
background-generated memory stores remain under Codex's control; setup does
not synthesize their internal files or enable that feature.

The repository starter changes only on explicit request. Its future revisions
apply to new copies, not established local memories. Keep starter material
public-safe and do not commit or push local memory or config files.

## Former shared-memory installations

On an old device, back up and detach any repository-backed memory/config links
before running initialization. Removing old entries from an installer alone
does not remove already-installed links. Preserve prior notes in real local
copies and retain unrelated config settings.

## Native configuration references

- [Codex developer instructions](https://learn.chatgpt.com/docs/config-file/config-reference): optional additional session instructions.
- [OpenCode instructions](https://opencode.ai/docs/instructions#configuration): configured local context files.
