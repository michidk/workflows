"""Run the release version step against real Git histories and git-cliff."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / 'templates/common/release.yml').read_text()
START = TEMPLATE.index('          set -euo pipefail', TEMPLATE.index('      - name: Calculate version'))
END = TEMPLATE.index('\n      - name: Create release App token', START)
SCRIPT = textwrap.dedent(TEMPLATE[START:END])
CLIFF = os.environ.get('GIT_CLIFF', shutil.which('git-cliff'))
CONFIG = r'''
[changelog]
body = "{% for commit in commits %}{{ commit.message }}\n{% endfor %}"
[git]
conventional_commits = true
filter_unconventional = true
protect_breaking_commits = true
commit_parsers = [{ message = "^chore", skip = true }]
tag_pattern = '^v[0-9]+[.][0-9]+[.][0-9]+$'
[bump]
initial_tag = "v0.1.0"
features_always_bump_minor = true
breaking_always_bump_major = true
'''


class ReleaseTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(CLIFF, 'Install git-cliff 2.14.2 or set GIT_CLIFF')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        binary = self.path / 'git-cliff/bin/git-cliff'
        binary.parent.mkdir(parents=True)
        binary.symlink_to(Path(CLIFF).resolve())
        self.git('init', '-b', 'main')
        self.commit('feat: initial application')
        (self.path / 'cliff.toml').write_text(CONFIG)

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.path, text=True).strip()

    def commit(self, message):
        self.git('-c', 'user.name=Release test', '-c', 'user.email=test@example.invalid',
                 'commit', '--allow-empty', '-m', message + '\n\n'
                 'Co-authored-by: Michael Lohr <michael@lohr.dev>\n'
                 'Co-authored-by: Codex <codex@openai.com>')

    def calculate(self, bump='auto'):
        output = self.path / 'output'
        output.write_text('')
        script = SCRIPT.replace('/tmp/release-notes.md', str(self.path / 'notes'))
        result = subprocess.run(['bash', '-euo', 'pipefail', '-c', script],
            cwd=self.path, env={**os.environ, 'RUNNER_TEMP': str(self.path),
                'GITHUB_OUTPUT': str(output), 'GITHUB_SHA': self.git('rev-parse', 'HEAD'),
                'BUMP_TYPE': bump}, text=True, capture_output=True)
        return result, dict(line.split('=', 1) for line in output.read_text().splitlines())

    def test_first_release(self):
        result, output = self.calculate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output['tag'], 'v0.1.0')
        self.assertIn('initial application', (self.path / 'notes').read_text())

    def test_automatic_bumps(self):
        self.git('tag', 'v0.1.0')
        for message, expected in [('fix: bug', 'v0.1.1'), ('feat: addition', 'v0.2.0'),
                                  ('feat!: breaking API', 'v1.0.0')]:
            self.commit(message)
            result, output = self.calculate()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output['tag'], expected)

    def test_explicit_overrides(self):
        self.git('tag', 'v1.2.3')
        self.commit('fix: bug')
        for bump, expected in [('patch', 'v1.2.4'), ('minor', 'v1.3.0'), ('major', 'v2.0.0')]:
            result, output = self.calculate(bump)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output['tag'], expected)

    def test_repeated_release_reuses_tag_and_notes(self):
        self.git('tag', 'v1.2.3')
        result, output = self.calculate('minor')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output, {'existing': 'true', 'tag': 'v1.2.3'})
        self.assertIn('initial application', (self.path / 'notes').read_text())

    def test_auto_skips_maintenance_but_explicit_bump_releases_it(self):
        self.git('tag', 'v1.2.3')
        self.commit('chore: housekeeping')
        result, output = self.calculate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output, {'skip': 'true'})
        result, output = self.calculate('patch')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output['tag'], 'v1.2.4')

    def test_breaking_maintenance_is_not_filtered(self):
        self.git('tag', 'v0.1.0')
        self.commit('chore!: require a new runtime')
        result, output = self.calculate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output['tag'], 'v1.0.0')

    def test_unrelated_latest_tag_is_rejected(self):
        self.git('checkout', '-b', 'other')
        self.commit('fix: other branch')
        self.git('tag', 'v2.0.0')
        self.git('checkout', 'main')
        result, output = self.calculate()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output, {})
        self.assertIn('ancestor', result.stdout)

    def test_invalid_override_fails_without_output(self):
        self.git('tag', 'v1.2.3')
        self.commit('fix: bug')
        result, output = self.calculate('invalid')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output, {})


if __name__ == '__main__':
    unittest.main()
