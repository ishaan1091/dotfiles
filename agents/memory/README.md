# Shared agent memory

Canonical location: `$DOTFILES_DIR/agents/memory`. Use this one root for shared
artifacts across harnesses. `MEMORY.md` indexes topics; `about-me.md` holds
personal context. Keep the global guide brief and the update workflow here.

## Path resolution

The installed Zsh configuration derives and exports `DOTFILES_DIR` from its
own symlink. Launch agents from that shell. For a GUI or remote environment,
ensure the same variable is supplied; do not silently create another memory
folder when it is missing. Moving the checkout requires reapplying the installer
and starting a new shell so the variable and installed links agree.

OpenCode uses its native `{env:DOTFILES_DIR}` syntax to load the index and
profile. An unset variable expands to an empty string, so verify it before
launching OpenCode. Codex uses the short shared guidance to read these files.
Its generated `memories/` and `memories_v2/` stores keep their separate lifecycle.

Claude's documented `autoMemoryDirectory` setting accepts absolute or `~/`
paths. The integration therefore selects its fixed native entry point,
`~/.claude/memory`, which the installer symlinks to the canonical directory
resolved from the checkout. This is the only memory directory alias. Fixed
native settings locations belong in the installer and integration configs;
other guidance and tools use `$DOTFILES_DIR`.

## Reading and updating

Read the index at session start and topics when relevant. Before an update,
reread the target, change the existing fact in place, and preserve others'
edits. Keep the index concise and add new topics there. Date durable facts and
record sources; distinguish confirmed information, goals, and unverified claims.
Explicit user corrections supersede older notes. Keep project-specific details
in their project and private information outside this public-safe checkout.

Claude's native auto-memory writes directly here instead of its default
per-project destination; there is no extra extraction or synchronization job.
This deliberately shares its notes across projects. Native toggles or project
settings may override that behavior. Other agents use these same files through
their shared guidance. Avoid simultaneous writers to the same topic or index:
symlinks do not lock files or merge conflicting changes.

## Installation and verification

Run the installer in dry-run mode before applying it. Existing config files
and memory directories are backed up, not merged. Review prior contents before
replacing them. The curated memory folder is the sole directory-link exception;
never link an entire application config or a generated Codex memory store.

Verify `DOTFILES_DIR` names this checkout, Claude's native memory link resolves
to `$DOTFILES_DIR/agents/memory`, and OpenCode's configured paths substitute to
that same directory. In Claude, use `/memory` to check the selected location.
Filesystem tests verify wiring, not agent recall or concurrent-write safety.
Claude runtime behavior is unverified where its CLI is unavailable. Remote
hosts need their own checkout and environment; symlinks do not sync machines.
Do not commit or push memory automatically.

## Integration references

- [Claude Code memory](https://code.claude.com/docs/en/memory#storage-location)
- [OpenCode config variables](https://opencode.ai/docs/config#env-vars)
- [Codex memories](https://learn.chatgpt.com/docs/customization/memories)

Reviewed on 2026-11-10.
