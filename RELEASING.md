# Releasing

Releases are published by hand from this repository to PyPI under the project
name `secondfactor`, with [uv](https://docs.astral.sh/uv/). Only maintainers
with access to the PyPI project can publish.

## One-time setup

1. Have a PyPI account with two-factor authentication on, added as an owner or
   maintainer of the `secondfactor` project.
2. Create an API token scoped to that project. Keep it in your password manager
   or keychain, never in this repository; `uv publish` reads it from the
   `UV_PUBLISH_TOKEN` environment variable.
3. Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`.

## Each release

1. Make sure `main` is green in CI and
   `uv run python -m unittest discover -s tests -v` passes locally.
2. Choose the version under [Semantic Versioning](https://semver.org/). Set it
   in **both** `pyproject.toml` (`uv version <version>` does this) and
   `src/secondfactor/__init__.py` (`__version__`); they must match, because
   `__version__` is what the `User-Agent` header reports.
3. Move the `unreleased` heading in `CHANGELOG.md` to the version and today's
   date.
4. Commit: `chore: release <version>`.
5. Build, and check that the wheel holds only `secondfactor/__init__.py` and
   the licence:

   ```bash
   rm -rf dist
   uv build
   python -m zipfile -l dist/*.whl
   ```

6. Optionally publish to TestPyPI first and install from there in a clean
   environment:

   ```bash
   uv publish --publish-url https://test.pypi.org/legacy/ --token "$TEST_PYPI_TOKEN"
   uv run --no-project --with secondfactor==<version> \
     --index https://test.pypi.org/simple/ -- python -c "import secondfactor; print(secondfactor.__version__)"
   ```

7. Publish: `UV_PUBLISH_TOKEN=<token> uv publish`.
8. Tag and push: `git tag v<version> && git push origin main v<version>`.
9. Create a GitHub release from the tag, pasting the changelog section.

A published version can never be uploaded again with different contents. If a
release is broken, yank it on PyPI and publish the next patch version.

Publishing from GitHub Actions with PyPI trusted publishing, which needs no
token at all, is a follow-up once releases are frequent enough to automate.
