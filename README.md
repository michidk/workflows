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

## Authentication

The sync workflow authenticates with the `michidk-orcastrate` GitHub App. Its
App ID is the repository variable `ORCASTRATE_APP_ID`. The token action
discovers the installation using `owner: michidk`; installation ID variables
are not required. Store the downloaded PEM
key as the `ORCASTRATE_PRIVATE_KEY` repository secret in `michidk/workflows`.

## Renovate

Always place repository Renovate configuration at `.github/renovate.json5`.
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

## Secret synchronization

The manual **Sync Actions secrets** workflow uses `vars.SECRET_SYNC_APP_ID`
and `secrets.SECRET_SYNC_APP_PRIVATE_KEY`. Store the Releaser App credentials
in `vars.RELEASER_APP_ID` and `secrets.RELEASER_APP_PRIVATE_KEY`. It defaults
to a dry run and only targets the explicit repository and secret allowlists in
`.github/workflows/sync-secrets.yml`.
The App needs repository **Secrets: read and write** permission.
