# Code signing policy

## Current status

The MLC Player application was submitted on 23 August 2026 and is awaiting
SignPath Foundation's decision. The project has not been accepted. The current
v0.39 Windows installers are **not Authenticode-signed**. The current release
does not carry a SignPath or Windows code-signing certificate.

If the project is accepted, future eligible Windows installers will use:

> Free code signing provided by SignPath.io, certificate by SignPath Foundation.

Providers: [SignPath.io](https://signpath.io/) and
[SignPath Foundation](https://signpath.org/).

The certificate publisher will therefore be SignPath Foundation, not the
project name or the maintainer's personal name.

## Project and roles

- Source repository: <https://github.com/IzzmooPro/MLCPlayer>
- Committer and reviewer: [IzzmooPro](https://github.com/IzzmooPro)
- Signing approver: [IzzmooPro](https://github.com/IzzmooPro)

Changes from contributors who do not have commit access must be reviewed
before merge. Every signing request requires separate manual approval from
the signing approver. Repository and SignPath access used for signing must be
protected by multi-factor authentication.

## What may be signed

Only MLC Player installers built from this repository by the approved,
GitHub-hosted release workflow may be submitted. Locally produced executables
are not eligible for SignPath submission. A signing request must identify the
exact source commit and version.

The installers may contain unmodified, unsigned binaries from upstream Open
Source projects such as libmpv, yt-dlp and Deno. Those upstream binaries are
packaged dependencies and must not be individually signed as if MLC Player
maintained their source.

MLC Player's existing detached Ed25519 release signature remains a separate
update-integrity layer. It does not replace Authenticode and a future
Authenticode signature must not replace it.

## Privacy and system changes

The project's network and local-data behavior is described in
[PRIVACY.md](PRIVACY.md). Installation, administrator approval, file
associations, updates and uninstallation are disclosed in the README and the
installer. MLC Player must not silently add telemetry or make undisclosed
system changes to qualify for signing.
