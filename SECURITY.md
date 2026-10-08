# Security policy

## Reporting a vulnerability

Please do not report security vulnerabilities through public GitHub issues,
discussions or pull requests.

Report them privately through GitHub instead: open the **Security** tab of this
repository and choose **Report a vulnerability**. Include the affected version,
a description of the issue, and the steps to reproduce it.

We will acknowledge the report, keep you informed while we work on a fix, and
credit you in the release notes unless you would prefer not to be named.

## Supported versions

Security fixes are released for the latest published version only.

## Verifying a release

Every release is built and uploaded by the `publish` workflow in this
repository through PyPI trusted publishing, and each file on PyPI carries a
PEP 740 attestation that links it to the exact workflow run and commit that
produced it. Releases are never uploaded from a personal machine.
