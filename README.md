# Workflows

This repository is the central [Orcastrate](https://github.com/michidk/orcastrate)
template repository for GitHub Actions workflows used by michidk repositories.

## How updates reach repositories

1. Change a template in `templates/` and merge the change into `main`.
2. The scheduled sync runs each weekday at 08:00 UTC. You can also run it
   manually from GitHub Actions.
3. Orcastrate renders each managed workflow and opens or updates a pull request
   when the target repository differs from the template.
4. Merge the generated pull request to apply the workflow change.

Template changes do not modify target repositories directly.

## Repository layout

- `orchestrator.toml` lists the managed repositories.
- `templates/` contains the canonical Tera workflow templates.
- `.github/workflows/sync.yml` runs Orcastrate.
- `.github/workflows/actionlint.yml` validates this repository.

## Onboard a repository

1. Open your [fine-grained personal access tokens](https://github.com/settings/personal-access-tokens)
   and edit the token stored as `ORCASTRATE_TOKEN`.
2. Add the new repository under **Repository access**. Keep these repository
   permissions set to read and write: **Contents**, **Pull requests**, and
   **Workflows**.
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
Formatting and clippy run once on Ubuntu, independently of the test matrix.

Redguard uses the three-platform test matrix. `vscli` uses Ubuntu with coverage.
CI renders and lints fixtures for the defaults and both consumer configurations.

## Rust crate publishing

The `publish-rust-crate` template validates `vX.Y.Z` tags, checks that the root
Cargo package has the same version, and publishes through crates.io Trusted
Publishing.

The target repositories do not need a crates.io API token.

To test Trusted Publishing, run **Publish to crates.io** manually and leave
**auth-only** enabled. This obtains and revokes a temporary token without
uploading a crate. Release events always perform normal publication. Rerunning
a release skips versions already present on crates.io.
