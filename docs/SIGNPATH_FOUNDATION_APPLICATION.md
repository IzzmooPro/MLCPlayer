# SignPath Foundation application draft

**Submission status: SUBMITTED - AWAITING DECISION**

This public record captures the SignPath Foundation Open Source application
submitted on 23 August 2026. It does not claim acceptance, an account, a
certificate, a signing request or a signature. Only SignPath Foundation can
decide eligibility.

## Applicant details

- Project: MLC Player
- Maintainer/contact name: provided privately in the submitted form; not
  published in this repository
- Contact email: provided privately in the submitted form; not published in
  this repository
- Source repository: <https://github.com/IzzmooPro/MLCPlayer>
- Public releases: <https://github.com/IzzmooPro/MLCPlayer/releases/latest>
- License: GPL-3.0-only ([LICENSE](../LICENSE))
- Current released version: v0.39

MLC Player is an actively maintained Windows desktop media player for local
audio and video playback. Website playback is delivered by a separately
installed, optional Internet Video add-on. The main player does not contain
advertising, telemetry or analytics.

## Submitted form summary

- Maintainer type: Individual maintainer(s)
- Build system: GitHub Actions
- Tagline: An open-source Windows media player focused on local playback,
  subtitles and verified updates.
- Description: MLC Player is a GPL-3.0-only desktop media player for Windows.
  It provides local audio and video playback, subtitle management, playlists
  and user-controlled update checks, without advertising, telemetry or
  analytics.
- Reputation statement: seven public GitHub releases, 63 recorded asset
  downloads and PR #15 CI with 4,804 passed / 30 skipped / 0 failed; the
  application explicitly described the project as early-stage and did not
  claim media coverage, a Wikipedia page or broad adoption.
- Discovery source: AI / LLM tools; OpenAI Codex
- Download URL, Wikipedia URL and company name: left blank rather than making
  an unsupported claim

## Project ownership and roles

- Committer and reviewer: [IzzmooPro](https://github.com/IzzmooPro)
- Signing approver: [IzzmooPro](https://github.com/IzzmooPro)
- Repository MFA: the maintainer confirmed on 23 August 2026 that MFA is
  enabled. This is a user attestation, not independently verifiable repository
  evidence. SignPath MFA will be enabled before any signing access is used.
- Every signing request will require a separate manual approval.

Project policies:

- [Code signing policy](../CODE_SIGNING_POLICY.md)
- [Privacy policy](../PRIVACY.md)
- [Release process](RELEASE_PROCESS.md)

## Eligibility declarations

- The project is released, documented and licensed under the OSI-approved
  GPL-3.0-only license without commercial dual licensing.
- The project does not intentionally contain malware, potentially unwanted
  programs, advertising, telemetry or analytics.
- MLC Player has no proprietary maintainer-owned component. Included runtime
  dependencies are upstream Open Source components with notices and tracked
  corresponding-source records.
- Installation and system changes are disclosed, and an uninstaller is
  provided. Local data and network behavior are disclosed in `PRIVACY.md`.
- Upstream Open Source DLLs may be included unsigned in the installer but will
  not be individually signed as if they were maintained by MLC Player.

These declarations are written against the published
[SignPath Foundation conditions](https://signpath.org/terms.html). They are
application evidence, not a self-issued eligibility decision.

## Requested initial signing scope

The initial scope is only the MLC Player main Windows installer produced by
the approved GitHub-hosted workflow from an exact repository commit. The
optional Internet Video add-on is outside the initial signing scope. Local
builds and upstream dependency binaries are not eligible for project signing.

The expected artifact pattern is `MLCPlayer_Setup_v*.exe`. Product name and
version metadata must be enforced by the future SignPath artifact
configuration. Authenticode signing must finish before the existing detached
Ed25519 signature is produced for the final installer bytes.

## Verified unsigned-build evidence

- Exact source commit:
  `1f01633bd7b008dba6faec8362ddff66e0d6d009`
- Workflow source at that commit:
  <https://github.com/IzzmooPro/MLCPlayer/blob/1f01633bd7b008dba6faec8362ddff66e0d6d009/.github/workflows/build-unsigned-main.yml>
- GitHub Actions run:
  <https://github.com/IzzmooPro/MLCPlayer/actions/runs/32634062651>
- Runner boundary: GitHub-hosted Windows 2025, Python 3.13.15 and Inno Setup
  6.7.1
- Installer: `MLCPlayer_Setup_v0.39.exe`, 57,255,931 bytes, SHA-256
  `cab8c89ba614dcf3589410d345248b831439beacaecad3db6994af9a0f436066`,
  Authenticode status `NotSigned`
- Installer artifact:
  `mlcplayer-unsigned-main-1f01633bd7b008dba6faec8362ddff66e0d6d009`
- Provenance artifact:
  `mlcplayer-unsigned-main-provenance-1f01633bd7b008dba6faec8362ddff66e0d6d009`

The exact installer and provenance archives were independently downloaded and
matched against GitHub's recorded archive sizes and SHA-256 digests. This is
hosted unsigned-build evidence only; it is not installed-artifact, native
playback, Authenticode or release evidence.

## Configuration only after acceptance

No SignPath account, GitHub App, API token, organization, project, policy,
artifact configuration, certificate or signing action has been created for
this project. After acceptance and separate approval:

1. Create the assigned organization/project and connect the repository to the
   predefined GitHub.com Trusted Build System.
2. Install the SignPath GitHub App with access limited to this repository.
3. Create a CI submitter and an interactive approver with MFA.
4. Configure the main EXE artifact and enforce project/version metadata.
5. Resolve the SignPath submission action to an immutable commit before adding
   it to the workflow; do not rely on a floating tag.
6. Keep every signing request under manual approval and verify the exact
   commit, version and uploaded GitHub Actions artifact.

Official integration reference:
<https://docs.signpath.io/trusted-build-systems/github>.
