# Releasing

Releases are published to PyPI under the project name `secondfactor` by the
`publish` GitHub Actions workflow. The workflow never runs on its own: a
maintainer starts it by hand from the Actions tab, and it publishes only from
`main`.

## One-time setup

1. On PyPI, open the `secondfactor` project, go to **Publishing**, and add a
   GitHub trusted publisher with owner `secondfactor`, repository
   `secondfactor-python`, workflow `publish.yml` and environment `pypi`. No API
   token is stored anywhere; PyPI trusts the workflow's OIDC token instead.
2. In this repository's **Settings → Environments**, create an environment
   named `pypi`. Add required reviewers to it if a second person should
   approve every upload.
3. In **Settings → Branches**, protect `main` and require the `ci` status
   check, which passes only when the tests pass on every supported Python
   version (3.9 to 3.13).

## Each release

1. Choose the version under [Semantic Versioning](https://semver.org/). Set it
   in **both** `pyproject.toml` (`uv version <version>` does this) and
   `src/secondfactor/__init__.py` (`__version__`); they must match, because
   `__version__` is what the `User-Agent` header reports. The workflow refuses
   to publish when they differ.
2. Move the `unreleased` heading in `CHANGELOG.md` to the version and today's
   date.
3. Commit `chore: release <version>` and merge it to `main`, then wait for the
   `test` workflow to go green.
4. Open **Actions → publish → Run workflow**, choose `main`, and run it. The
   workflow runs the full test matrix again, checks the two versions agree and
   that the version has not been tagged before, builds, uploads to PyPI, and
   pushes the `v<version>` tag.
5. Create a GitHub release from the new tag, pasting the changelog section.

To check a build locally before releasing, confirm the wheel holds only
`secondfactor/__init__.py` and the licence:

```bash
rm -rf dist
uv build
python -m zipfile -l dist/*.whl
```

A published version can never be uploaded again with different contents. If a
release is broken, yank it on PyPI and publish the next patch version.
