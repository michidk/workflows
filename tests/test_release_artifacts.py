"""Exercise release publication and completion from rendered shared workflows."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMMAND = shlex.split(os.environ.get('ORCASTRATE', 'orcastrate'))


def render(fixture):
    return subprocess.check_output(COMMAND + ['render', 'fixtures/' + fixture], cwd=ROOT, text=True)


def step(workflow, name):
    section = workflow.split('      - name: ' + name + '\n', 1)[1]
    script = section.split('        run: |\n', 1)[1]
    lines = []
    for line in script.splitlines():
        if line.strip() and not line.startswith('          '):
            break
        lines.append(line)
    return textwrap.dedent('\n'.join(lines))


class ReleaseArtifactsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = render('rust-release-artifacts.yml')

    def test_project_workflow_owns_builds_and_checks(self):
        self.assertIn('uses: ./.github/workflows/build-release.yml', self.workflow)
        self.assertIn('needs: [verify, build, release]', self.workflow)
        self.assertIn('pattern: release-*', self.workflow)
        self.assertNotIn('cargo test', self.workflow)
        self.assertNotIn('cargo clippy', self.workflow)
        self.assertNotIn('BIN_NAME:', self.workflow)
        self.assertIn('ref: refs/tags/${{ env.TAG_NAME }}', self.workflow)

    def test_tag_validation(self):
        script = step(self.workflow, 'Validate release tag and publishing token')
        for tag, valid in [('v1.2.3', True), ('main', False), ('v1.2.3-beta', False),
                           ('v01.2.3', False), ('v1.2', False), ('', False)]:
            with self.subTest(tag=tag):
                result = subprocess.run(['bash', '-euo', 'pipefail', '-c', script],
                    env={**os.environ, 'TAG_NAME': tag}, capture_output=True)
                self.assertEqual(result.returncode == 0, valid)

    def test_completion_rejects_failed_cancelled_and_skipped_dependencies(self):
        script = step(self.workflow, 'Require every release job to succeed')
        for job in ('verify', 'build', 'release'):
            for state in ('success', 'failure', 'cancelled', 'skipped'):
                with self.subTest(job=job, state=state), tempfile.TemporaryDirectory() as tmp:
                    results = {name: {'result': 'success'} for name in ('verify', 'build', 'release')}
                    results[job]['result'] = state
                    summary = Path(tmp) / 'summary'
                    result = subprocess.run(['bash', '-euo', 'pipefail', '-c', script],
                        env={**os.environ, 'RESULTS': json.dumps(results), 'GITHUB_STEP_SUMMARY': str(summary)},
                        capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0 if state == 'success' else 1, result.stderr)
                    self.assertIn(f'{job}: {state}', summary.read_text())

    def test_publication_resumes_drafts_and_preserves_published_releases(self):
        script = step(self.workflow, 'Create or update draft, then publish if enabled')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'artifacts').mkdir()
            for name in ('native.tar.gz', 'browser.tar.gz', 'SHA256SUMS'):
                (root / 'artifacts' / name).write_text(name)
            gh = root / 'gh'
            gh.write_text('''#!/bin/sh
if [ "$1" = api ]; then
    if [ "$STATE" = missing ]; then echo '[]';
    else printf '[{"tag_name":"v1.2.3","draft":%s}]\\n' "$STATE"; fi
else
    printf '%s\\n' "$*" >> calls
fi
''')
            gh.chmod(0o755)
            for state in ('missing', 'true', 'false'):
                for publish in ('true', 'false'):
                    with self.subTest(state=state, publish=publish):
                        (root / 'calls').unlink(missing_ok=True)
                        subprocess.run(['bash', '-euo', 'pipefail', '-c', script], cwd=root,
                            env={**os.environ, 'PATH': f'{root}:' + os.environ['PATH'], 'STATE': state,
                                 'PUBLISH_RELEASE': publish, 'GH_REPO': 'example/example', 'TAG_NAME': 'v1.2.3'},
                            check=True, capture_output=True)
                        calls = (root / 'calls').read_text() if (root / 'calls').exists() else ''
                        if state == 'false':
                            self.assertEqual(calls, '')
                            continue
                        for name in ('native.tar.gz', 'browser.tar.gz', 'SHA256SUMS'):
                            self.assertIn('artifacts/' + name, calls)
                        self.assertIn('--notes-file CHANGELOG.md', calls)
                        self.assertEqual('--draft=false' in calls, publish == 'true')


class SignedBumpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = step(render('rust-bump-version-workspace.yml'), 'Publish signed version commit and tag')

    def test_signatures_coauthors_and_compare_and_swap(self):
        for failure in ('none', 'conflict', 'unsigned', 'missing-author'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / 'Cargo.toml').write_text('version = "1.2.4"\n')
                git = root / 'git'
                git.write_text('#!/bin/sh\nif [ "$1" = rev-parse ]; then echo expected-head; else printf "Cargo.toml\\0"; fi\n')
                git.chmod(0o755)
                gh = root / 'gh'
                gh.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
route = sys.argv[2]
with open('calls', 'a') as output: output.write(route + '\\n')
if route == 'graphql':
    payload = json.load(sys.stdin)
    Path('payload.json').write_text(json.dumps(payload))
    if os.environ['FAILURE'] == 'conflict': sys.exit(1)
    print(json.dumps({'data': {'createCommitOnBranch': {'commit': {'oid': 'signed-head'}}}}))
elif '/commits/' in route:
    message = json.loads(Path('payload.json').read_text())['variables']['input']['message']['body']
    if os.environ['FAILURE'] == 'missing-author': message = ''
    print(json.dumps({'commit': {'verification': {'verified': os.environ['FAILURE'] != 'unsigned'}, 'message': message}}))
else:
    Path('tag.json').write_text(sys.stdin.read())
    print('{}')
''')
                gh.chmod(0o755)
                author = 'Example Contributor <contributor@example.invalid>'
                result = subprocess.run(['bash', '-euo', 'pipefail', '-c', self.script], cwd=root,
                    env={**os.environ, 'PATH': f'{root}:' + os.environ['PATH'], 'FAILURE': failure,
                         'CO_AUTHORS': json.dumps([author, author]), 'GH_REPO': 'example/example',
                         'VERSION': '1.2.4', 'DEFAULT_BRANCH': 'main', 'GITHUB_STEP_SUMMARY': str(root / 'summary')},
                    capture_output=True, text=True)
                self.assertTrue((root / 'payload.json').exists(), result.stdout + result.stderr)
                payload = json.loads((root / 'payload.json').read_text())['variables']['input']
                self.assertEqual(payload['expectedHeadOid'], 'expected-head')
                self.assertEqual(payload['message']['body'], 'Co-authored-by: ' + author)
                self.assertEqual(payload['fileChanges']['additions'][0]['path'], 'Cargo.toml')
                if failure == 'none':
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads((root / 'tag.json').read_text()),
                                     {'ref': 'refs/tags/v1.2.4', 'sha': 'signed-head'})
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse((root / 'tag.json').exists())
