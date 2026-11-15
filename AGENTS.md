# Agent instructions

This repository holds generic, reusable Orcastrate templates for GitHub Actions
workflows and Renovate presets. Read `README.md` before changing it.

## Scope: reusable templates only

- A template belongs here only when several repositories run the same workflow
  and differ just in a few parameters (for example Rust releases, crate
  publishing, PR title checks, or actionlint).
- A project's own CI (its build and test commands, services, databases,
  browsers, images, and deployment) is an ordinary GitHub Actions workflow in
  that project's repository, without Orcastrate frontmatter. Do not bring it
  here, neither as a project template (no `templates/projects/`) nor as
  project-specific parameters, step lists, or options on a generic template.
- Extract a template only when the workflow is genuinely shared. When unsure,
  keep it in the project repository.
- Do not name projects or repositories in templates, fixtures, comments, commit
  messages, or branch names. Fixtures use placeholders such as `example`.
  Repository lists live in repository secrets (`ORCASTRATE_REPOS*`,
  `SECRET_SYNC_REPOS`).

## Validation

- Every template needs a fixture in `fixtures/`; `tests/test_runners.py`
  enforces this.
- Render every fixture with Orcastrate, run actionlint on the output, and run
  `python3 -m unittest discover -s tests`, as `.github/workflows/actionlint.yml`
  does. The prebuilt `ghcr.io/michidk/orcastrate:main` image works for local
  rendering.
