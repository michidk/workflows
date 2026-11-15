# Agent instructions

This public repository holds generic, reusable Orcastrate templates for GitHub
Actions workflows and Renovate presets. Read `README.md` before changing it.

## Scope: generic templates only

- Add a template only when it is parameterized for any repository of its kind.
  It must not encode a single project's names, services, image names,
  credentials, infrastructure, or deployment details.
- Never add project-specific templates or directories such as
  `templates/projects/`. A workflow that only fits one project belongs in that
  project's repository as a repository-owned workflow without Orcastrate
  frontmatter.
- When a project needs something the templates cannot express, extend the
  matching family template (`node/`, `rust/`, `python/`, `docker/`, `common/`)
  with an optional parameter. Keep the default rendering unchanged so existing
  consumers do not receive sync pull requests, and verify that by diffing
  renders before and after.

## Keep private information out

- This repository and its Actions logs are public, and some consumers are
  private. Do not write repository or project names in files, fixtures,
  comments, commit messages, branch names, or pull requests. Use placeholders
  such as `example` or `app` in fixtures.
- Repository lists live in repository secrets (`ORCASTRATE_REPOS*`,
  `SECRET_SYNC_REPOS`), never in workflow files.

## Validation

- Every template needs a fixture in `fixtures/`; `tests/test_runners.py`
  enforces this.
- Render every fixture with the pinned Orcastrate, run actionlint on the output,
  and run `python3 -m unittest discover -s tests` as `.github/workflows/actionlint.yml`
  does. The prebuilt `ghcr.io/michidk/orcastrate:main` image works for local
  rendering.
