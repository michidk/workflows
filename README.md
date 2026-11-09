# Workflows

This repository is the central [Orcastrate](https://github.com/michidk/orcastrate)
template repository for GitHub Actions workflows and Renovate configuration
used by michidk repositories.

## How updates reach repositories

1. Change a template in `templates/` and merge the change into `main`.
2. The push to `main` starts the sync. You can also run it manually from
   GitHub Actions.
3. Orcastrate renders each managed workflow and opens or updates a pull request
   when the target repository differs from the template.
4. Merge the generated pull request to apply the workflow change.

Template changes do not modify target repositories directly.

## Repository layout

- `orchestrator.toml` lists the managed repositories.
- `templates/` contains the canonical Tera workflow templates and Renovate preset.
- `.github/workflows/sync.yml` runs Orcastrate.

The templates are grouped by workflow family:

```text
templates/
  common/   # workflows shared by any repository
  docker/   # OCI image build and publication
  node/     # Node.js and Bun checks
  python/   # Python projects using uv
  rust/     # Rust CI, release, publishing, and version bump workflows
  presets/  # reusable configuration files, such as Renovate
```
- `.github/workflows/actionlint.yml` validates this repository.

## Onboard a repository

1. Open the `michidk-orcastrate` GitHub App installation and add the new
   repository. Grant the App read and write access to **Contents**, **Pull
   requests**, and **Workflows**.
3. Add the repository to `orchestrator.toml`:

   ```toml
   [[repos]]
   name = "michidk/example"
   ```

4. Add the initial managed workflow under `.github/workflows/` in the target
   repository. Copy an existing workflow that uses the required template and
   keep its Orcastrate frontmatter:

   ```yaml
   # @orcastrate
   # template: rust/publish-crate
   # @end-orcastrate

   # The rendered workflow starts here and must be valid GitHub Actions YAML.
   ```

5. Merge the initial workflow into the target repository's default branch.
   Orcastrate discovers existing workflow files but does not create the first
   file.
6. Run **Sync workflows** manually in this repository. Orcastrate opens a pull
   request if the initial workflow differs from its template.

Orcastrate preserves the frontmatter and manages the complete file below it.
To change template parameters, edit the `params` map in the frontmatter.

GitHub expressions in templates must escape Tera expressions. For example:

```yaml
TAG_NAME: ${{ "{{ github.ref_name }}" }}
```

## Runner selection

Every workflow template defaults to GitHub-hosted runners. To override every
job in a managed workflow, set `custom_runner` in its Orcastrate frontmatter:

```yaml
# @orcastrate
# template: common/actionlint
# params:
#   custom_runner: ubicloud-standard-2
# @end-orcastrate
```

The parameter accepts a runner label, a label list such as
`[self-hosted, linux, x64]`, or a GitHub Actions expression. Orcastrate preserves
this frontmatter during sync, so subsequent template updates keep the override.
Omit `custom_runner` to keep each job's default selection. Existing `runner_os`,
`test_os`, and release `targets[].os` parameters still work when it is omitted.

`custom_runner` takes precedence over all of those settings, including matrix
jobs. The runner must support each job's commands, operating system, and CPU
architecture. For native multi-architecture builds, use an expression to select
matching runners, for example in `projects/codetend/ci`:

```yaml
#   custom_runner: "${{ contains(toJSON(matrix), 'linux/amd64') && 'ubicloud-standard-2' || 'ubicloud-standard-2-arm' }}"
```

That expression also selects ARM for jobs without `matrix.platform`, matching
CodeTend's default checks and merge architecture. For mixed Windows, macOS, and
Linux workflows, preserve platform-specific selection or provide an expression
that maps each matrix entry to a compatible runner.

When using custom labels, list them under `self-hosted-runner.labels` in the
consumer's `.github/actionlint.yaml` so actionlint recognizes them:

```yaml
self-hosted-runner:
  labels: [ubicloud-standard-2, ubicloud-standard-2-arm]
```

## Authentication

The sync workflow authenticates with the `michidk-orcastrate` GitHub App. Its
App ID is the repository variable `ORCASTRATE_APP_ID`. The token action
discovers the installation using `owner: michidk`; installation ID variables
are not required. Store the downloaded PEM
key as the `ORCASTRATE_PRIVATE_KEY` repository secret in `michidk/workflows`.

## Renovate

Always place repository Renovate configuration at `.github/renovate.json5`.
Remove root Renovate configs after preserving their repository-specific rules;
Renovate reads the root config first and does not merge it with this file.
For existing configs written as strict JSON, preview consolidation with
`python3 scripts/migrate-renovate-config.py ../repository` and add `--write`
to apply it. The script uses the shared preset and preserves local settings,
with the existing `.github` settings taking precedence on conflicts.
Create that file with the following content to use the shared preset:

```json5
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["github>michidk/workflows//templates/presets/renovate"]
}
```

Renovate reads `templates/presets/renovate.json` from this repository's default branch
on each run. Changes to the preset apply without a sync PR. Orcastrate continues
to manage the GitHub Actions workflows. Configure repository-specific settings
alongside `extends` and enable the Renovate GitHub App for the repository.

The preset delays npm package updates by three days and groups minor and patch
dependency updates separately for JavaScript and Rust. The npm manager also
handles Bun projects; Rust dependencies use the Cargo manager. Major updates
remain outside these groups. Lockfile maintenance runs before 04:00 UTC
on Mondays and automerges after checks pass.

Libraries extend `github>michidk/workflows//templates/presets/renovate-library`
instead. It builds on the shared preset but keeps compatible version ranges
(`^1.2`, `0.25.1`) rather than pinning exact versions, so projects that depend
on the library can share dependency versions with it. Peer dependency ranges
are widened on major updates, and the lockfile still pins the versions CI tests.
Applications keep the shared preset, which pins development dependencies.

For a fork you maintain, also set `"forkProcessing": "enabled"` in that
repository's `.github/renovate.json5`. Renovate otherwise skips forks when the App has
access to all repositories.

## Rust CI

The `rust/ci` template runs tests, `cargo fmt`, and clippy on every push and
pull request. It uses stable Rust and pinned checkout, toolchain, and cache
actions. Add its frontmatter to `.github/workflows/ci.yml`:

```yaml
# @orcastrate
# template: rust/ci
# params:
#   test_os: [ubuntu-24.04, macos-latest, windows-latest]
#   coverage: false
# @end-orcastrate
```

`test_os` defaults to `[ubuntu-26.04]`. Set `coverage: true` to run the test
suite through `cargo llvm-cov` with all workspace features and write an LCOV
report. Set `codacy: true` to upload that report to Codacy; uploads are
best-effort and require the repository's `CODACY_API_TOKEN` secret. Both
options default to false.
Formatting and clippy run once on `runner_os`, independently of the test matrix.
`runner_os` defaults to `ubuntu-26.04`. For Windows-only crates, set both
`test_os: [windows-latest]` and `runner_os: windows-latest`.

Redguard uses the three-platform test matrix. `vscli` uses Ubuntu with coverage.
CI renders and lints fixtures for the defaults and both consumer configurations.

## Rust crate publishing

The `rust/publish-crate` template validates `vX.Y.Z` tags, checks that every
selected Cargo package has the same version, and publishes through crates.io
Trusted Publishing. `manifest_paths` defaults to `[Cargo.toml]`. For a workspace,
list the package manifests in dependency order, with libraries before their
dependent CLI crates. All versions are checked before any crate is uploaded.
Cargo waits for each published crate to appear in the registry index before
the next package is uploaded.

The target repositories do not need a crates.io API token.
Set `runner_os: windows-latest` for crates that require Windows to compile.
It defaults to `ubuntu-26.04`.

For each crate, open its **Settings** page on crates.io and add a GitHub Trusted
Publisher. Use the target repository owner and name, the publishing workflow's
filename, and the environment `publish-crates.io`. For example, a workflow at
`.github/workflows/publish.yml` uses the filename `publish.yml`. Every published
crate in a workspace needs its own Trusted Publisher with the same settings.
Create the `publish-crates.io` GitHub environment if it does not exist. Do not
remove an existing API token until Trusted Publishing has been verified.

To test Trusted Publishing, run **Publish to crates.io** manually and leave
**auth-only** enabled. This obtains and revokes a temporary token without
uploading a crate. Release events always perform normal publication. Rerunning
a release skips versions already present on crates.io.

## Rust releases

The `rust/bump-version` template provides **Bump Version & Tag**. Run it on the
default branch and choose an automatic, patch, minor, or major bump, defaulting
to automatic. The automatic option uses git-cliff and Conventional Commit messages
to choose the bump. The workflow calculates the next `X.Y.Z` version, updates
the package version, preserves locked dependency versions, and pushes the commit
and tag atomically. If git-cliff finds no unreleased changes, the workflow is a
no-op. An existing next-version tag at another commit causes it to fail.

Both release templates accept `manifest_paths`, defaulting to `[Cargo.toml]`.
List all packages that share the release version. The bump updates their
versions and local dependency requirements together, then commits the changed
Cargo manifests and lockfile. The release checks each selected package's
version against the tag.

The `rust/release` template verifies the tag and Cargo version, runs formatting,
clippy, and tests, and builds every configured target before creating a release.
It uses the repository's `cliff.toml` to generate the release body with git-cliff.
Archives retain their existing names and include a `SHA256SUMS` file.

Configure its frontmatter with `bin_name` and a `targets` list. Each target needs
`os` and `target`; use `cross: true` for Linux cross compilation and `lib_file`
to include a separate native-library archive.

For a Rust library without a CLI, set `library_only: true` instead of `bin_name`
and `targets`. The release still verifies the package and generates a git-cliff
body, but does not build or attach binary archives. `runner_os` selects the
release verification runner and defaults to `ubuntu-26.04`. Use `windows-latest`
if the package requires Windows.

Commit `Cargo.lock` so the release and publishing workflows can use `--locked`.
Tests that require hardware or a local WSL distribution must be marked with
`#[ignore]`. Document how to run them manually; CI still compiles ignored tests.

Set the Orcastrate parameter `publish_release: true` to publish immediately after
all artifacts are uploaded. It defaults to false, which creates a draft. A
published release triggers the local crates.io workflow and any other
`release: published` workflows, including Homebrew.

The release and version bump templates use the `RELEASER_APP_ID` and
`RELEASER_APP_PRIVATE_KEY` repository secrets to mint short-lived GitHub App
tokens. The App needs Contents and Actions write access to each target
repository. GitHub's default workflow token suppresses downstream workflow
triggers, so releases use the App token when publishing.

The `common/pr-title` template checks Conventional Commit pull request titles without
checking out pull request code.

## Node and Bun CI

The `node/ci` template supports Bun projects and installs dependencies with
`bun install --frozen-lockfile`. Biome is the required TypeScript and
JavaScript formatter and linter; it runs through Reviewdog, producing PR
annotations and failing the check when diagnostics remain. The command
parameters are optional so repositories can keep their existing test,
verification, and build commands.

FRND BOOK uses the project-specific `projects/frndbook/ci` template. It preserves
Prettier formatting alongside Biome and Expo ESLint, then checks types, licenses,
Expo compatibility, book tests, web journeys, Storybook canvases, phone previews,
and Android/iOS bundles. `fixtures/frndbook-ci.yml` covers rendering and linting
of this template. The repository is listed in both `orchestrator.toml` and the
sync workflow's App-token repository list.

## Python CI

The `python/uv-ci` template uses a locked `uv sync`, runs pytest by default,
and optionally runs linting, type checking, and Hadolint. It is intended for
Python services with a committed `uv.lock`.

## OCI image publishing

The `docker/oci-publish` template builds and publishes a multi-platform image
to GHCR on version tags or manual dispatch. It centralizes the Docker action
versions, QEMU/Buildx setup, metadata, registry login, and GitHub Actions cache.
Application checks and multi-job digest assembly remain repository-owned when
they need more than this basic publish path.

## Roastbook CI

`projects/roastbook/ci` preserves the PostgreSQL integration suite, Docker and
Helm validation, migration drift checks, browser asset boundaries, and
multi-platform image build. The static demo has its own repository-owned workflow. Its fixture is
`fixtures/roastbook-ci.yml`. Application checks remain project-specific.

`projects/roastbook-infra/verify` runs the private infrastructure repository's
credential-free verification command with pinned Bun, Node, and OpenTofu tools.
Concrete infrastructure and deployment controllers remain private. Its fixture
is `fixtures/roastbook-infra-verify.yml`.

Both repositories use `common/actionlint` for workflow and shell validation and
`common/pr-title` for Conventional Commit titles. The actionlint template ignores
only its pinned release's outdated warning about the valid `ubuntu-26.04` runner.

## Repository settings prototype

The manual **Sync repository settings (prototype)** workflow uses
[gh-settings](https://github.com/noirbizarre/gh-settings) to distribute
`settings/common.yml` to exactly the repositories listed in `orchestrator.toml`.
It reads the inventory on each run, including repositories with a nonstandard
default branch. No consumer workflow or settings file is required.

The baseline enables squash merges with the PR title and body as the commit
message, deletes merged branches, allows updating PR branches, defaults Actions
tokens to read access, and prevents workflow tokens from approving PRs.
Existing merge and rebase options remain available. Explicit workflow permissions
continue to override the default token permissions.

The prototype leaves visibility, default branches, security products, branch
rules, labels, topics, environments, and Actions retention unmanaged. Those
settings need repository-specific decisions or depend on GitHub plan support.
Pruning is disabled. Squash commit bodies retain PR text, but contributors must
still include the required co-author trailers in the PR body.

### Setup and trial

1. Give the existing Orcastrate GitHub App **Administration: read and write**
   access and accept the installation permission update for the managed repos.
   This expands the App's privileges beyond workflow synchronization. A dedicated
   settings App can replace it later if those credentials should be separated.
   The existing `ORCASTRATE_APP_ID` variable and `ORCASTRATE_PRIVATE_KEY` secret
   are reused. The workflow requests a token scoped to one target repository.
2. Merge this prototype into the default branch. It deliberately refuses runs
   from other branches and has no push or scheduled trigger.
3. Run the workflow with `command: plan` and one inventory repository such as
   `michidk/vscli`. Review its job summary. Pending changes are reported as drift,
   not workflow failure. Permission and API errors fail the target job.
4. Run with `command: sync` and the same repository to apply the baseline.
   This changes GitHub settings directly; it does not open an Orcastrate PR.
5. Run `plan` again to check convergence. Leave `repository` empty to plan or
   apply across the full Orcastrate inventory. Targets run independently, two
   at a time. A failure does not cancel the other repositories.

Both the upstream action and extension are pinned to gh-settings 0.3.0.
This is a trial baseline; repository overrides and automatic enforcement are
not implemented. Before a fleet apply, check every plan for repos that rely on
workflow approval or default write permissions. To undo an applied value, set
its previous value in the baseline and sync the affected repository. Removing
a key stops managing it and does not restore the previous value.

Preview the target inventory locally without credentials:

```sh
python3 scripts/settings-matrix.py
python3 scripts/settings-matrix.py --repository michidk/vscli
```

## Secret synchronization

The manual **Sync Actions secrets** workflow uses `vars.SECRET_SYNC_APP_ID`
and `secrets.SECRET_SYNC_APP_PRIVATE_KEY`. Store the Releaser App credentials
in `vars.RELEASER_APP_ID` and `secrets.RELEASER_APP_PRIVATE_KEY`. It defaults
to a dry run and only targets the explicit repository and secret allowlists in
`.github/workflows/sync-secrets.yml`.
The App needs repository **Secrets: read and write** permission.

## Web application releases

`common/release` provides **Release**, dispatched on the default branch with
`bump_type` set to `auto`, `patch`, `minor`, or `major`. It requires the latest
push run of `ci_workflow` (default `ci.yml`) for the dispatch revision to have
succeeded. It tags that exact tested commit and publishes a GitHub release with
git-cliff notes. It does not change package manifests or create version commits.
The tag is the application release version.

Each consumer owns `cliff.toml`, including its initial version and pre-1.0 bump
policy. Roastbook starts at `v0.1.0`, bumps features to a minor release and
breaking changes to a major release, including before 1.0. Explicit bump choices
override commit inference and start from `v0.0.0` before the first tag. Automatic
mode skips histories without unreleased changelog entries. Rerunning for an already tagged revision resumes an
incomplete release or leaves the published release unchanged. Tags never move.
Run again after CI succeeds if preparation fails its CI gate.

Configure `RELEASER_APP_ID` and `RELEASER_APP_PRIVATE_KEY`, with the Releaser App
installed on the consumer and Contents write permission. Release publication
uses the App token so downstream tag and release workflows run. The shared
secret-sync allowlist includes both Roastbook repositories; the Secret Sync App
also needs access to both. The Orcastrate App needs access before syncing their
managed files.

`fixtures/common-release.yml` covers the default template. Version-selection
behavior is tested with real temporary Git histories and git-cliff 2.14.2:

```sh
ORCASTRATE=/path/to/orcastrate GIT_CLIFF=/path/to/git-cliff python3 -m unittest discover -s tests
```

Both Roastbook repositories consume this template, `common/actionlint`, and
`common/pr-title`. The private deployment relay remains repository-owned.
