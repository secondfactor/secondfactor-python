# Releasing

Releases are published by hand from this repository to PyPI under the project
name `secondfactor`. Only maintainers with access to the PyPI project can
publish.

## One-time setup

1. Have a PyPI account with two-factor authentication on, added as an owner or
   maintainer of the `secondfactor` project.
2. Create an API token scoped to that project and store it in your keychain or
   in `~/.pypirc`, never in this repository.
3. `python -m pip install --upgrade build twine`

## Each release

1. Make sure `main` is green in CI and `python -m unittest -v` passes locally.
2. Choose the version under [Semantic Versioning](https://semver.org/). Set it
   in **both** `pyproject.toml` (`version`) and `secondfactor.py`
   (`__version__`); they must match, because `__version__` is what the
   `User-Agent` header reports.
3. Move the `unreleased` heading in `CHANGELOG.md` to the version and today's
   date.
4. Commit: `chore: release <version>`.
5. Build and check:

   ```bash
   rm -rf dist
   python -m build
   python -m twine check dist/*
   ```

6. Optionally publish to TestPyPI first and install from there in a clean
   virtual environment:

   ```bash
   python -m twine upload --repository testpypi dist/*
   ```

7. Publish: `python -m twine upload dist/*`
8. Tag and push: `git tag v<version> && git push origin main v<version>`.
9. Create a GitHub release from the tag, pasting the changelog section.

A published version can never be uploaded again with different contents. If a
release is broken, yank it on PyPI and publish the next patch version.
