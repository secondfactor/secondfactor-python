# Releasing

Releases are published to PyPI under the project name `secondfactor` by the
`publish` GitHub Actions workflow. The workflow never runs on its own: a
maintainer starts it by hand from the Actions tab, and it publishes only from
`main`.

## How the repository is protected

These settings live on GitHub rather than in this repository, so they are
recorded here. Keep them in place; the release process depends on them.

- **`main`** accepts changes only through a pull request whose `ci` check has
  passed on every supported Python version (3.9 to 3.13). Force-pushes and
  deletion are blocked, and nobody can bypass the rule.
- **Tags** cannot be moved or deleted once created, so a release tag always
  names the commit that was published.
- **The `pypi` environment** deploys only from `main` and waits for a required
  reviewer to approve each upload.
- **Actions** may use only GitHub's own actions, `astral-sh/setup-uv` and
  `pypa/gh-action-pypi-publish`, each pinned to a full commit SHA. Workflows
  from first-time and outside contributors wait for approval before they run.
- **Secret scanning** with push protection, **Dependabot** alerts and security
  updates, and **private vulnerability reporting** are on.

PyPI must trust the workflow: on the `secondfactor` project, under
**Publishing**, a GitHub trusted publisher names owner `secondfactor`,
repository `secondfactor-python`, workflow `publish.yml` and environment
`pypi`. No PyPI API token exists for this project, and none should be created.

## Each release

1. Choose the version under [Semantic Versioning](https://semver.org/). Set it
   in **both** `pyproject.toml` (`uv version <version>` does this) and
   `src/secondfactor/__init__.py` (`__version__`); they must match, because
   `__version__` is what the `User-Agent` header reports. The workflow refuses
   to publish when they differ.
2. Move the `unreleased` heading in `CHANGELOG.md` to the version and today's
   date.
3. Open a pull request titled `chore: release <version>` and merge it once
   `ci` is green.
4. Open **Actions → publish → Run workflow** and run it on `main`. The workflow
   runs the full test matrix again, checks that the two versions agree and
   that the version has not been tagged before, and builds the package.
5. Approve the `pypi` deployment when GitHub asks. The workflow then uploads
   to PyPI with signed attestations and creates the `v<version>` tag.
6. Create a GitHub release from the new tag, pasting the changelog section.
   Releases are immutable once published.

To check a build locally before releasing, confirm the wheel holds only
`secondfactor/__init__.py` and the licence:

```bash
rm -rf dist
uv build
python -m zipfile -l dist/*.whl
```

A published version can never be uploaded again with different contents. If a
release is broken, yank it on PyPI and publish the next patch version.
