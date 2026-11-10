"""Exercise the real installer in isolated homes and repository copies."""
import os
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
LINKS = {".zshrc": "shell/zshrc", ".zprofile": "shell/zprofile",
         ".aliases": "shell/aliases", ".utils": "shell/utils",
         ".gitconfig": "git/gitconfig", ".codex/AGENTS.md": "agents/AGENTS.md",
         ".claude/CLAUDE.md": "agents/AGENTS.md",
         ".config/opencode/AGENTS.md": "agents/AGENTS.md",
         ".local/bin/install-agent-skills": "agents/install-skills.sh",
         ".claude/memory": "agents/memory",
         ".claude/settings.json": "agents/integrations/claude-settings.json",
         ".config/opencode/opencode.json": "agents/integrations/opencode.json"}
GIT = '[user]\n name = Test User\n'


def snapshot(root):
    result = {}
    for parent, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(parent) / name
            key = str(path.relative_to(root))
            result[key] = ('link', os.readlink(path)) if path.is_symlink() else (
                ('dir',) if path.is_dir() else ('file', path.read_bytes(), path.stat().st_mode))
    return result


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dotfiles-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.home = self.root / 'home'
        self.home.mkdir()
        shutil.copytree(REPO, self.repo, ignore=shutil.ignore_patterns('.git', '__pycache__'))

    def run_install(self, mode='--apply', expected=0, **env):
        result = subprocess.run(['bash', str(self.repo / 'install.sh'), mode],
                                env={**os.environ, 'DOTFILES_TARGET': str(self.home),
                                     'DOTFILES_SKIP_AGENT_SKILLS': '1', **env},
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def run_skills(self, mode='--dry-run', expected=0):
        result = subprocess.run(['bash', str(self.repo / 'agents/install-skills.sh'), mode],
                                env={**os.environ, 'DOTFILES_TARGET': str(self.home)},
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def assert_rejected_unchanged(self):
        before = snapshot(self.home)
        for mode in ('--dry-run', '--apply'):
            self.run_install(mode, expected=1)
            self.assertEqual(snapshot(self.home), before)

    def assert_installed(self):
        for destination, source in LINKS.items():
            self.assertTrue((self.home / destination).samefile(self.repo / source))

    def test_missing_source(self):
        (self.home / '.aliases').write_text('keep me')
        (self.repo / 'shell/aliases').unlink()
        self.assert_rejected_unchanged()

    def test_missing_memory_index(self):
        (self.repo / 'agents/memory/MEMORY.md').unlink()
        self.assert_rejected_unchanged()

    def test_memory_links_share_writes_and_preserve_conflicts(self):
        destination = '.claude/memory'
        path = self.home / destination
        path.mkdir(parents=True)
        (path / 'original.md').write_text(destination)
        settings = self.home / '.claude/settings.json'
        settings.write_text('{"existing": true}\n')
        before = snapshot(self.home)
        self.run_install('--dry-run')
        self.assertEqual(snapshot(self.home), before)
        self.run_install()
        self.assert_installed()
        backup = next((self.home / '.local/state/dotfiles').glob('backup.*'))
        self.assertEqual((backup / destination / 'original.md').read_text(), destination)
        self.assertEqual((backup / '.claude/settings.json').read_text(), '{"existing": true}\n')
        (self.home / '.claude/memory/learned.md').write_text('shared fact\n')
        self.assertEqual((self.repo / 'agents/memory/learned.md').read_text(), 'shared fact\n')
        before = snapshot(self.home)
        result = self.run_install()
        self.assertEqual(result.stdout.count('Already linked:'), len(LINKS))
        self.assertEqual(snapshot(self.home), before)

    def test_memory_configuration_points_to_shared_files(self):
        self.run_install()
        claude = json.loads((self.home / '.claude/settings.json').read_text())
        claude_memory = self.home / claude['autoMemoryDirectory'].removeprefix('~/')
        self.assertTrue(claude_memory.samefile(self.repo / 'agents/memory'))
        opencode = json.loads((self.home / '.config/opencode/opencode.json').read_text())
        for path in opencode['instructions']:
            self.assertTrue(path.startswith('{env:DOTFILES_DIR}/agents/memory/'))
            resolved = Path(path.replace('{env:DOTFILES_DIR}', str(self.repo)))
            self.assertTrue(resolved.samefile(self.repo / 'agents/memory' / resolved.name))
        self.assertFalse((self.home / '.agents/memory').exists())
        # Never redirect generated Codex state into the curated folder.
        for name in ('memories', 'memories_v2'):
            self.assertFalse((self.home / '.codex' / name).exists())

    def test_memory_paths_follow_relocated_checkout(self):
        moved_repo = self.root / 'checkout with spaces'
        self.repo.rename(moved_repo)
        self.repo = moved_repo
        self.run_install(DOTFILES_DIR='/obsolete/checkout')
        self.assert_installed()
        claude = json.loads((self.home / '.claude/settings.json').read_text())
        native_path = self.home / claude['autoMemoryDirectory'][2:]
        self.assertTrue(native_path.samefile(self.repo / 'agents/memory'))
        opencode = json.loads((self.home / '.config/opencode/opencode.json').read_text())
        for value in opencode['instructions']:
            path = Path(value.replace('{env:DOTFILES_DIR}', str(self.repo)))
            self.assertTrue(path.is_file())
            self.assertTrue(path.samefile(self.repo / 'agents/memory' / path.name))

    def test_parent_is_file(self):
        (self.home / '.codex').write_text('keep me')
        (self.home / '.gitconfig').write_text(GIT)
        self.assert_rejected_unchanged()

    def test_dangling_parent(self):
        (self.home / '.codex').symlink_to(self.root / 'absent')
        self.assert_rejected_unchanged()

    def test_backup_parent_is_file(self):
        (self.home / '.local').write_text('keep me')
        self.assert_rejected_unchanged()

    def test_parent_symlink_into_repo(self):
        original = (self.repo / 'agents/AGENTS.md').read_bytes()
        (self.home / '.codex').symlink_to(self.repo / 'agents', target_is_directory=True)
        self.run_install()
        self.assert_installed()
        self.assertEqual((self.repo / 'agents/AGENTS.md').read_bytes(), original)
        self.assertFalse((self.repo / 'agents/AGENTS.md').is_symlink())

    def test_identical_git_copy_and_repeat(self):
        for name in ('.gitconfig', '.gitconfig.local'):
            (self.home / name).write_text(GIT)
        self.run_install()
        self.assert_installed()
        before = snapshot(self.home)
        result = self.run_install()
        self.assertEqual(result.stdout.count('Already linked:'), len(LINKS))
        self.assertEqual(snapshot(self.home), before)

    def test_differing_git_copy(self):
        (self.home / '.gitconfig').write_text(GIT)
        (self.home / '.gitconfig.local').write_text('different')
        self.assert_rejected_unchanged()

    def test_missing_git_include(self):
        (self.repo / 'git/gitconfig').write_text('# ~/.gitconfig.local\n[user]\n name = Test\n')
        self.assert_rejected_unchanged()

    def test_dry_run_and_backup(self):
        (self.home / '.zshrc').write_text('original shell')
        (self.home / '.gitconfig').write_text(GIT)
        before = snapshot(self.home)
        result = self.run_install('--dry-run')
        self.assertIn('Conflict:', result.stdout)
        self.assertIn('backup.<unique>/.zshrc', result.stdout)
        self.assertEqual(snapshot(self.home), before)
        self.run_install()
        self.assert_installed()
        backups = list((self.home / '.local/state/dotfiles').glob('backup.*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / '.zshrc').read_text(), 'original shell')
        self.assertEqual((self.home / '.gitconfig.local').read_text(), GIT)

    def test_resume_after_runtime_failure(self):
        # Fail ln at different stages, including after the Git backup was moved.
        real_ln = shutil.which('ln')
        bin_dir = self.root / 'bin'
        bin_dir.mkdir()
        wrapper = bin_dir / 'ln'
        for fail_at in ('.zshrc', '.aliases', '.gitconfig'):
            with self.subTest(fail_at=fail_at):
                shutil.rmtree(self.home)
                self.home.mkdir()
                (self.home / '.gitconfig').write_text(GIT)
                wrapper.write_text('#!/bin/bash\nfor arg; do last="$arg"; done\n'
                                   'if [[ "$last" = "$FAIL_DEST" ]]; then exit 1; fi\n'
                                   'exec "$REAL_LN" "$@"\n')
                wrapper.chmod(0o755)
                self.run_install(expected=1, PATH=str(bin_dir) + os.pathsep + os.environ['PATH'],
                                 REAL_LN=real_ln, FAIL_DEST=str(self.home / fail_at))
                self.run_install()
                self.assert_installed()
                self.assertEqual((self.home / '.gitconfig.local').read_text(), GIT)
                before = snapshot(self.home)
                result = self.run_install()
                self.assertEqual(result.stdout.count('Already linked:'), len(LINKS))
                self.assertEqual(snapshot(self.home), before)

    def test_relative_symlink(self):
        (self.home / '.aliases').symlink_to('../repo/shell/aliases')
        self.run_install()
        self.assertEqual(os.readlink(self.home / '.aliases'), '../repo/shell/aliases')

    def test_git_symlink_warning(self):
        old = self.root / 'old-gitconfig'
        old.write_text(GIT)
        (self.home / '.gitconfig').symlink_to(old)
        result = self.run_install()
        self.assertIn('will not be copied', result.stderr)
        self.assertFalse((self.home / '.gitconfig.local').exists())
        self.assertEqual(old.read_text(), GIT)

    def test_skill_list_dry_run_is_offline(self):
        result = self.run_skills()
        self.assertIn('Would install publish-html', result.stdout)
        self.assertFalse((self.home / '.agents').exists())

    def test_skill_list_rejects_unsafe_paths(self):
        for entry in ('owner/repo .. evil', 'owner/repo . -evil',
                      '../repo . evil', 'owner/repo sub ..'):
            with self.subTest(entry=entry):
                (self.repo / 'agents/skills.list').write_text(entry + '\n')
                self.run_skills(expected=1)
                self.assertFalse((self.home / '.agents').exists())

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS bootstrap')
    def test_bootstrap_help_and_invalid_flag(self):
        for flag in ('-h', '--help'):
            result = subprocess.run(['bash', str(self.repo / 'scripts/bootstrap.sh'), flag],
                                    env={**os.environ, 'HOME': str(self.home)},
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Usage:', result.stdout)
        result = subprocess.run(['bash', str(self.repo / 'scripts/bootstrap.sh'), '--bogus'],
                                env={**os.environ, 'HOME': str(self.home)},
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS bootstrap')
    def test_bootstrap_dry_run_does_not_install(self):
        result = subprocess.run(['bash', str(self.repo / 'scripts/bootstrap.sh')],
                                env={**os.environ, 'HOME': str(self.home), 'SHELL': '/bin/zsh'},
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('Summary', result.stdout)
        self.assertIn('GUI applications', result.stdout)
        for app in ('iterm2', 'maccy', 'visual-studio-code', 'postman',
                    'intellij-idea-ce', 'docker', 'ngrok'):
            self.assertRegex(result.stdout, rf'(?m)^  (?:ok|miss) +{app}$')
        self.assertFalse((self.home / '.oh-my-zsh').exists())
        self.assertFalse((self.home / '.iterm2_shell_integration.zsh').exists())
        self.assertFalse((self.home / '.local/bin/code').exists())

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS bootstrap')
    def test_bootstrap_requires_working_java_and_javac(self):
        # Keep discovery and version checks independent of the host's JDK,
        # Homebrew, network, and authentication state.
        bin_dir = self.root / 'bin'
        bin_dir.mkdir()
        (bin_dir / 'dirname').symlink_to(shutil.which('dirname'))
        for command in ('curl', 'xcode-select', 'brew', 'git', 'jq', 'wget',
                        'htop', 'gh', 'go', 'pyenv', 'node', 'code'):
            stub = bin_dir / command
            stub.write_text('#!/bin/bash\nexit 0\n')
            stub.chmod(0o755)
        uname = bin_dir / 'uname'
        uname.write_text('#!/bin/bash\nprintf "Darwin\\n"\n')
        uname.chmod(0o755)
        (self.home / '.nvm').mkdir()
        (self.home / '.nvm/nvm.sh').write_text('# installed\n')
        before = snapshot(self.home)
        for java_status, javac_status, missing in (
                (0, 0, None), (1, 0, 'java'), (0, 1, 'javac'),
                (None, 0, 'java'), (0, None, 'javac')):
            with self.subTest(java=java_status, javac=javac_status):
                for command, status in (('java', java_status), ('javac', javac_status)):
                    stub = bin_dir / command
                    if stub.exists():
                        stub.unlink()
                    if status is not None:
                        stub.write_text('#!/bin/bash\n[[ "$1" == -version ]] || exit 2\n'
                                        f'exit {status}\n')
                        stub.chmod(0o755)
                result = subprocess.run(
                    [shutil.which('bash'), str(self.repo / 'scripts/bootstrap.sh'), '--dry-run'],
                    env={'HOME': str(self.home), 'PATH': str(bin_dir), 'SHELL': '/bin/zsh'},
                    text=True, capture_output=True)
                # Other setup files are intentionally absent in this temporary home.
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                if missing:
                    self.assertIn(f'  miss  CLI tools: {missing}\n', result.stdout)
                else:
                    self.assertIn('  ok    CLI tools\n', result.stdout)
                self.assertEqual(snapshot(self.home), before)

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS bootstrap')
    def test_bootstrap_gui_install_requires_explicit_opt_in(self):
        bin_dir = self.root / 'bin'
        bin_dir.mkdir()
        (bin_dir / 'dirname').symlink_to(shutil.which('dirname'))
        # Missing ngrok guarantees at least one GUI item needs attention.
        for command in ('curl', 'xcode-select', 'git', 'jq', 'wget', 'htop',
                        'gh', 'go', 'pyenv', 'node', 'java', 'javac', 'code'):
            stub = bin_dir / command
            stub.write_text('#!/bin/bash\nexit 0\n')
            stub.chmod(0o755)
        uname = bin_dir / 'uname'
        uname.write_text('#!/bin/bash\nprintf "Darwin\\n"\n')
        uname.chmod(0o755)
        brew = bin_dir / 'brew'
        brew.write_text('#!/bin/bash\nif [[ "$1" == bundle ]]; then\n'
                        '  printf "%s\\n" "$*" >> "$REVIEW_BREW_LOG"\nfi\n')
        brew.chmod(0o755)
        # A known shell conflict stops apply runs before later filesystem changes.
        (self.home / '.oh-my-zsh').mkdir()
        (self.home / '.nvm').mkdir()
        (self.home / '.nvm/nvm.sh').write_text('# installed\n')
        log = self.root / 'brew.log'
        before = snapshot(self.home)
        for mode in (('--dry-run',), ('--dry-run', '--with-apps'),
                     ('--apply',), ('--apply', '--with-apps')):
            with self.subTest(mode=mode):
                if log.exists():
                    log.unlink()
                result = subprocess.run(
                    [shutil.which('bash'), str(self.repo / 'scripts/bootstrap.sh'), *mode],
                    env={'HOME': str(self.home), 'PATH': str(bin_dir),
                         'SHELL': '/bin/zsh', 'REVIEW_BREW_LOG': str(log)},
                    text=True, capture_output=True)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn('  miss  ngrok\n', result.stdout)
                if mode == ('--apply', '--with-apps'):
                    self.assertEqual(log.read_text(),
                                     f'bundle install --file {self.repo.resolve()}/Brewfile.apps\n')
                else:
                    self.assertFalse(log.exists())
                self.assertEqual(snapshot(self.home), before)

    def test_script_symlink_and_help(self):
        launcher = self.root / 'installer'
        launcher.symlink_to('repo/install.sh')
        result = subprocess.run(['bash', str(launcher), '--apply'],
                                env={**os.environ, 'DOTFILES_TARGET': str(self.home),
                                     'DOTFILES_SKIP_AGENT_SKILLS': '1'},
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed()
        for flag in ('-h', '--help'):
            self.assertIn('Usage:', self.run_install(flag).stdout)


if __name__ == '__main__':
    unittest.main()
