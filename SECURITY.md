# Security Policy

## Reporting a vulnerability

If you find a security issue in this connector — or anywhere in PreHack — please email
**security@prehack.ai**. Do **not** open a public issue or pull request with sensitive details.

When you can, include:

- a description of the issue and its impact;
- the steps (or a proof of concept) to reproduce it;
- the affected version, commit, or URL.

We aim to acknowledge reports within a few business days and to keep you updated while we
investigate and fix. We appreciate coordinated, responsible disclosure and will credit
reporters who want it, once a fix is available.

## Scope

- **This repository** (`prehack-connect`): the public installer/connector. It contains only the
  device-code client and the editor-config writer — no scanning engine, no secrets. See the
  "Security and trust" section of the [README](README.md).
- **The PreHack service** (`prehack.ai`): the servers that run the scans and hold the engine.

## Authorized use only

PreHack is for testing code and targets that you **own** or have **written permission** to test.
Using it against third parties' systems without authorization is not permitted and may be illegal.
