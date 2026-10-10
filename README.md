# Workflows

Reusable GitHub Actions workflows for michidk repositories.

## Publish a Rust crate

Call `.github/workflows/publish-rust-crate.yml` from a release workflow:

```yaml
jobs:
  publish-cratesio:
    uses: michidk/workflows/.github/workflows/publish-rust-crate.yml@main
    secrets:
      CARGO_REGISTRY_TOKEN: ${{ secrets.CARGO_REGISTRY_TOKEN }}
```

The calling repository must have a `publish-crates.io` environment containing
the `CARGO_REGISTRY_TOKEN` secret. The workflow accepts `vX.Y.Z` tags and runs
`cargo publish` for the tagged commit.
