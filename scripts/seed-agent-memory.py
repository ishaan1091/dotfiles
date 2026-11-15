#!/usr/bin/env python3
"""Seed independent Codex/OpenCode memory and configure loading; dry-run by default."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile

if sys.version_info < (3, 11):
    raise SystemExit('Python 3.11+ is required; run scripts/bootstrap.sh --apply to install prerequisites.')
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def codex_config(text, directive):
    """Replace only the root developer_instructions assignment; preserve other TOML."""
    data = tomllib.loads(text)
    previous = data.pop('developer_instructions', '')
    if not isinstance(previous, str):
        raise ValueError('Codex developer_instructions must be a string')
    if directive in previous:
        return text
    updated = (previous.rstrip() + '\n\n' + directive).lstrip('\n')
    assignment = 'developer_instructions = ' + json.dumps(updated, ensure_ascii=False) + '\n'
    if 'developer_instructions' not in tomllib.loads(text):
        return assignment + text
    # Prefix parsing finds the smallest complete assignment, including multiline
    # strings. Comparing the decoded remainder prevents matching nested keys.
    lines = text.splitlines(keepends=True)
    pattern = r'''^\s*(?:developer_instructions|"developer_instructions"|'developer_instructions')\s*='''
    for start, line in enumerate(lines):
        if not re.match(pattern, line):
            continue
        for end in range(start + 1, len(lines) + 1):
            remainder = ''.join(lines[:start] + lines[end:])
            try:
                if tomllib.loads(remainder) == data:
                    return ''.join(lines[:start]) + assignment + ''.join(lines[end:])
            except tomllib.TOMLDecodeError:
                pass
    raise ValueError('Cannot safely locate Codex developer_instructions assignment')


def preflight(path):
    resolved = path.resolve()
    if resolved.is_relative_to(ROOT):
        raise ValueError(f'Local memory/configuration must be outside the checkout: {path}')
    if path.is_symlink():
        raise ValueError(f'Expected an independent local file, found symlink: {path}')
    if path.exists() and not path.is_file():
        raise ValueError(f'Expected a file: {path}')
    ancestor = path.parent
    while not ancestor.exists() and not ancestor.is_symlink():
        ancestor = ancestor.parent
    if not ancestor.is_dir() or not os.access(ancestor, os.W_OK):
        raise ValueError(f'Destination parent must be a writable directory: {ancestor}')


def opencode_config(text, memory):
    """Insert one loading entry while retaining JSONC comments and other settings."""
    # Mask comments without changing offsets or matching comment syntax in strings.
    strings = r'"(?:\\.|[^"\\])*"'
    masked = re.sub(strings + r'|//[^\r\n]*|/\*[\s\S]*?\*/',
                    lambda m: m[0] if m[0].startswith('"') else re.sub(r'[^\r\n]', ' ', m[0]), text)
    cleaned = re.sub(strings + r'|,(?=\s*[}\]])',
                     lambda m: ' ' if m[0] == ',' else m[0], masked)
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError('OpenCode config must be a JSON object')
    instructions = data.get('instructions', [])
    if not isinstance(instructions, list) or any(not isinstance(item, str) for item in instructions):
        raise ValueError('OpenCode instructions must be an array of strings')
    if memory in instructions:
        return text
    decoder = json.JSONDecoder()
    opening = cleaned.index('{')
    position = opening + 1
    while cleaned[position:].lstrip() and cleaned[position:].lstrip()[0] != '}':
        position += len(cleaned[position:]) - len(cleaned[position:].lstrip())
        key, position = decoder.raw_decode(cleaned, position)
        position = cleaned.index(':', position) + 1
        position += len(cleaned[position:]) - len(cleaned[position:].lstrip())
        start = position
        value, end = decoder.raw_decode(cleaned, position)
        if key == 'instructions':
            trailing_comma = masked[start + 1:end - 1].rstrip().endswith(',')
            separator = ', ' if value and not trailing_comma else ''
            return text[:end - 1] + separator + json.dumps(memory) + text[end - 1:]
        position = end
        position += len(cleaned[position:]) - len(cleaned[position:].lstrip())
        if cleaned[position:position + 1] == ',':
            position += 1
    entry = '\n  "instructions": [' + json.dumps(memory) + ']' + (',' if data else '') + '\n'
    return text[:opening + 1] + entry + text[opening + 1:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--apply', action='store_true')
    modes.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    target = args.target
    if not target.is_absolute():
        raise ValueError('--target must be an absolute home directory')
    source = ROOT / 'agents/memory/about-me.md'
    seed = source.read_bytes()
    plans = []
    for directory in ('.codex', '.config/opencode'):
        memory = target / directory / 'memory.md'
        preflight(memory)
        if memory.exists():
            print(f'Keep existing memory: {memory}')
        else:
            plans.append((memory, None, seed))
    config = target / '.codex/config.toml'
    preflight(config)
    original = config.read_bytes() if config.exists() else None
    directive = ('Read ' + json.dumps(str(target / '.codex/memory.md'), ensure_ascii=False)
                 + ' at session start for personal context. Keep durable personal updates in that local memory file.')
    updated = codex_config((original or b'').decode('utf-8'), directive).encode('utf-8')
    if updated != original:
        plans.append((config, original, updated))
    config = target / '.config/opencode/opencode.json'
    if config.with_suffix('.jsonc').exists():
        config = config.with_suffix('.jsonc')
    preflight(config)
    original = config.read_bytes() if config.exists() else None
    local_memory = str(target / '.config/opencode/memory.md')
    updated = opencode_config((original or b'{}\n').decode('utf-8'), local_memory).encode('utf-8')
    if updated != original:
        plans.append((config, original, updated))
    for path, before, after in plans:
        print(f'{"Initialize" if before is None else "Update loading config"}: {path}')
    if not args.apply:
        return
    backup = None
    for path, before, after in plans:
        path.parent.mkdir(parents=True, exist_ok=True)
        preflight(path)
        if before is not None:
            if path.read_bytes() != before:
                raise ValueError(f'File changed during setup; rerun: {path}')
            if backup is None:
                parent = target / '.local/state/dotfiles'
                parent.mkdir(parents=True, exist_ok=True)
                backup = Path(tempfile.mkdtemp(prefix='backup.memory-config.', dir=parent))
            saved = backup / path.relative_to(target)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, saved)
        # Complete the write beside the destination before making it visible.
        # A failed/interrupted write cannot leave a partial "existing" memory.
        fd, staged = tempfile.mkstemp(prefix='.memory-write-', dir=path.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(after)
                stream.flush()
                os.fsync(stream.fileno())
            if before is None:
                # Unlike replace, link refuses to overwrite a concurrent file.
                os.link(staged, path)
            else:
                if path.is_symlink() or path.read_bytes() != before:
                    raise ValueError(f'File changed during setup; rerun: {path}')
                os.chmod(staged, stat.S_IMODE(path.stat().st_mode))
                os.replace(staged, path)
        finally:
            if os.path.exists(staged):
                os.unlink(staged)
    if backup:
        print(f'Memory configuration backups: {backup}')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit(f'Memory setup failed: {error}')
