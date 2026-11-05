const { readFileSync } = require('node:fs')
const { resolve } = require('node:path')
const { test } = require('node:test')
const assert = require('node:assert/strict')

const template = readFileSync(resolve(__dirname, '../templates/common/notify-dependents.yml'), 'utf8')
const script = template.split('          script: |\n')[1].split('\n      - name:')[0]
  .split('\n').map((line) => line.slice(12)).join('\n')
const execute = new (Object.getPrototypeOf(async function () {}).constructor)('github', 'context', 'core', script)
const sha = 'a'.repeat(40)
const run = {
  id: 12, workflow_id: 34, head_sha: sha, head_branch: 'main', event: 'push',
  status: 'completed', conclusion: 'success', head_repository: { full_name: 'example/app' },
}
async function select(patch = {}, event = {}) {
  const output = {}
  await execute({ rest: {
    actions: {
      getWorkflow: async () => ({ data: { id: 34 } }),
      listWorkflowRuns: async () => ({ data: { workflow_runs: patch.missing ? [] : [{ ...run, ...patch }] } }),
    },
    repos: { getBranch: async () => ({ data: { commit: { sha } } }) },
  } }, {
    repo: { owner: 'example', repo: 'app' }, eventName: 'workflow_run', ref: 'refs/heads/main',
    payload: { repository: { default_branch: 'main' }, workflow_run: { id: 12 } }, ...event,
  }, { setOutput: (name, value) => { output[name] = value } })
  return output
}
test('notifies the current successful main push and supports a manual retry', async () => {
  assert.deepEqual(await select(), { revision: sha, 'run-id': 12 })
  assert.deepEqual(await select({}, { eventName: 'workflow_dispatch' }), { revision: sha, 'run-id': 12 })
})
test('ignores failures, PRs, forks, stale heads and other workflows or runs', async () => {
  for (const patch of [
    { missing: true }, { conclusion: 'failure' }, { status: 'in_progress' },
    { event: 'pull_request' }, { head_repository: { full_name: 'fork/app' } },
    { head_sha: 'b'.repeat(40) }, { head_branch: 'other' }, { workflow_id: 99 }, { id: 99 },
  ]) assert.deepEqual(await select(patch), {})
})
test('manual retries fail clearly on the wrong branch or before successful CI', async () => {
  await assert.rejects(select({}, { eventName: 'workflow_dispatch', ref: 'refs/heads/feature' }), /default branch/)
  await assert.rejects(select({ conclusion: 'failure' }, { eventName: 'workflow_dispatch' }), /CI must succeed/)
})
