# Changelog

All notable changes to this package are recorded here. The project follows
[Semantic Versioning](https://semver.org/); while the version is below 1.0.0, a
minor release may change behaviour, and every such change is listed.

## 0.2.0 — unreleased

The first release published to PyPI, and the first from this repository.

### Added

- Verification sessions: `create_session`, `retrieve_session` and
  `verify_session`, for the hosted page and headless mode.
- `send()`, with an optional `idempotency_key`.
- A `User-Agent` of `secondfactor-python/<version>` on every request.
- The Service SID is looked up on first use when it is not given.

### Changed

- `check()` adds a `verified` boolean to the verification it returns.
- `check()` raises `SecondFactorError` with `code` `expired`, `locked` or
  `already_verified` for a verification that can never succeed, instead of
  returning its body.
- Requests are sent as JSON rather than form-encoded.
- Packaged with uv: the module moved to `src/secondfactor/`, built by
  `uv_build`. The import is still `import secondfactor`.

### Security

- Redirects are refused rather than followed. urllib resends the API key to
  whatever host a redirect names, over plain HTTP too; a redirect now raises
  `SecondFactorError` with the redirect's status instead.
- `base_url` must use `https://`. Plain `http://` is accepted only for
  `localhost`, `127.0.0.1` and `::1`, so the key never crosses a network
  unencrypted. Any other value raises `ValueError`.
- `verify_session` raises `SecondFactorError` with `code` `not_verified` unless
  the confirmed session's status is `VERIFIED`, even on a successful answer.
- A `service_sid` passed in is quoted as a single path segment, like every
  other identifier.

### Deprecated

- `start()`. Use `send()`; `start()` still works and emits a
  `DeprecationWarning`.

## 0.1.0

Distributed as a download from the secondfactor.ai dashboard only. `start()`
and `check()` for direct sends.
