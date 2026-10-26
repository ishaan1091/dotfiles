"""Exercise the real installer in isolated homes and repository copies."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
LINKS = {".zshrc": "shell/zshrc", ".zprofile": "shell/zprofile",
         ".aliases": "shell/aliases", ".utils": "shell/utils",
         ".gitconfig": "git/gitconfig", ".codex/AGENTS.md": "codex/AGENTS.md"}
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
                                env={**os.environ, 'DOTFILES_TARGET': str(self.home), **env},
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
        original = (self.repo / 'codex/AGENTS.md').read_bytes()
        (self.home / '.codex').symlink_to(self.repo / 'codex', target_is_directory=True)
        self.run_install()
        self.assert_installed()
        self.assertEqual((self.repo / 'codex/AGENTS.md').read_bytes(), original)
        self.assertFalse((self.repo / 'codex/AGENTS.md').is_symlink())

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

    def test_script_symlink_and_help(self):
        launcher = self.root / 'installer'
        launcher.symlink_to('repo/install.sh')
        result = subprocess.run(['bash', str(launcher), '--apply'],
                                env={**os.environ, 'DOTFILES_TARGET': str(self.home)},
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed()
        for flag in ('-h', '--help'):
            self.assertIn('Usage:', self.run_install(flag).stdout)


if __name__ == '__main__':
    unittest.main()
