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
- `.github/workflows/actionlint.yml` validates this repository.

## Onboard a repository

1. Open your [fine-grained personal access tokens](https://github.com/settings/personal-access-tokens)
   and check the token stored as `ORCASTRATE_TOKEN`.
2. If the token uses **Only select repositories**, add the new repository under
   **Repository access**. With **All repositories**, no scope update is needed.
   Keep these repository permissions set to read and write: **Contents**,
   **Pull requests**, and **Workflows**.
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
   # template: publish-rust-crate
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

Add an `ORCASTRATE_TOKEN` repository secret. The token needs read and write
access to Contents, Pull requests, and Workflows in every managed repository.
The sync passes this token to Orcastrate for both workflow commits and pull
requests.

## Renovate

Always place repository Renovate configuration at `.github/renovate.json5`.
Create that file with the following content to use the shared preset:

```json5
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["github>michidk/workflows//templates/renovate"]
}
```

Renovate reads `templates/renovate.json` from this repository's default branch
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

The `rust-ci` template runs tests, `cargo fmt`, and clippy on every push and
pull request. It uses stable Rust and pinned checkout, toolchain, and cache
actions. Add its frontmatter to `.github/workflows/ci.yml`:

```yaml
# @orcastrate
# template: rust-ci
# params:
#   test_os: [ubuntu-24.04, macos-latest, windows-latest]
#   coverage: false
# @end-orcastrate
```

`test_os` defaults to `[ubuntu-26.04]`. Set `coverage: true` to run the test
suite through `cargo llvm-cov` with all workspace features and upload LCOV to
Codacy when `CODACY_API_TOKEN` is configured. Coverage defaults to false.
Formatting and clippy run once on `runner_os`, independently of the test matrix.
`runner_os` defaults to `ubuntu-26.04`. For Windows-only crates, set both
`test_os: [windows-latest]` and `runner_os: windows-latest`.

Redguard uses the three-platform test matrix. `vscli` uses Ubuntu with coverage.
CI renders and lints fixtures for the defaults and both consumer configurations.

## Rust crate publishing

The `publish-rust-crate` template validates `vX.Y.Z` tags, checks that every
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

The `rust-bump-version` template provides **Bump Version & Tag**. Run it on the
default branch and enter the next `X.Y.Z` version. It updates the package version,
preserves locked dependency versions, and pushes the commit and tag atomically.
An existing matching version and tag are a no-op.

Both release templates accept `manifest_paths`, defaulting to `[Cargo.toml]`.
List all packages that share the release version. The bump updates their
versions and local dependency requirements together, then commits the changed
Cargo manifests and lockfile. The release checks each selected package's
version against the tag.

The `rust-release` template verifies the tag and Cargo version, runs formatting,
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

Both templates accept `release_token_secret`, defaulting to `RELEASE_TOKEN`.
That repository secret must contain a token with Contents and Workflows write
access to the target repository. Version/tag pushes and automatic release
publication use it because GitHub's default workflow token suppresses downstream
workflow triggers. Draft creation uses the default workflow token.

The `pr-title` template checks Conventional Commit pull request titles without
checking out pull request code.
