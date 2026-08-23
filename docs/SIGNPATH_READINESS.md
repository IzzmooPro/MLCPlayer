# SignPath Foundation readiness

This is an engineering checklist, not proof of acceptance and not legal
advice. The application package is prepared, but its **Submission status is
NOT SUBMITTED**. SignPath Foundation has not accepted the project and is the
only party that can decide eligibility.

The reviewable submission draft is
[`SIGNPATH_FOUNDATION_APPLICATION.md`](SIGNPATH_FOUNDATION_APPLICATION.md).

## Conditions supported by current evidence

- The repository is public and licensed under OSI-approved GPL-3.0-only.
- MLC Player is actively maintained, documented and already released as v0.39.
- Windows packages include notices and corresponding-source records for their
  Open Source components.
- The product provides uninstallers and does not contain telemetry, analytics
  or advertising.
- Upstream Open Source binaries are included as dependencies rather than
  represented as MLC Player-owned binaries.
- `CODE_SIGNING_POLICY.md`, `PRIVACY.md` and `docs/RELEASE_PROCESS.md` document
  roles, unsigned status, network/local-data behavior and the release order.
- The maintainer confirmed on 23 August 2026 that GitHub MFA is enabled. This
  is a user attestation, not independently proven repository evidence.

These facts make an application plausible; only SignPath Foundation can make
the eligibility decision.

## Verified GitHub-hosted unsigned build

`.github/workflows/build-unsigned-main.yml` is manual-only and uses a
GitHub-hosted Windows 2025 runner. Exact master commit
`1f01633bd7b008dba6faec8362ddff66e0d6d009` completed run
<https://github.com/IzzmooPro/MLCPlayer/actions/runs/32634062651> successfully.

The verified boundary includes:

- Python `3.13.15`, Inno Setup `6.7.1`, 24 exact hash-locked Windows wheels
  and the immutable project-owned libmpv OCI digest;
- installer `MLCPlayer_Setup_v0.39.exe`, **57,255,931 bytes**, SHA-256
  `cab8c89ba614dcf3589410d345248b831439beacaecad3db6994af9a0f436066`;
- Authenticode status `NotSigned`, no signer certificate and no detached
  `.sig` in the hosted output;
- Actions artifacts
  `mlcplayer-unsigned-main-1f01633bd7b008dba6faec8362ddff66e0d6d009`
  and
  `mlcplayer-unsigned-main-provenance-1f01633bd7b008dba6faec8362ddff66e0d6d009`.

Both artifact archives were independently downloaded and matched GitHub's
recorded sizes and SHA-256 digests. This is hosted unsigned-build evidence,
not installation, native playback, Authenticode or release acceptance.

The workflow does not call SignPath, access the local Ed25519 key, create a
tag or change a release. The optional Internet Video add-on was deliberately
outside this build and remains outside the initial signing scope.

## Submission-time user actions

1. Supply the maintainer contact name and email in the application draft.
2. Review the public declarations and exact hosted-build evidence.
3. Give separate approval before the application is submitted.
4. Await SignPath Foundation's decision; do not add an action, token,
   certificate or acceptance claim before approval.

## Configuration only after SignPath acceptance

If accepted, connect only the repository's GitHub-hosted workflow to the
predefined GitHub.com Trusted Build System and install the SignPath GitHub App
with repository-limited access. Define separate CI submitter and interactive
approver roles, require MFA and keep every signing request under manual
approval. Resolve the submission action to an immutable commit before it is
introduced; a floating action tag is not an approved release input.

The safe future sequence is:

1. GitHub-hosted runner builds and stores the exact unsigned main installer.
2. After SignPath acceptance, the exact stored artifact is submitted.
3. A human approver checks the commit/version and manually approves signing.
4. SignPath applies Authenticode to the installer bytes.
5. The signed installer is downloaded to the controlled release environment.
6. The existing Ed25519 process signs the final Authenticode-signed bytes.
7. Install, upgrade, uninstall, native-smoke and release-parity gates run
   against those final bytes.

Until these later gates exist and pass, SignPath is not part of the active
release chain. `docs/RELEASE_PROCESS.md` remains authoritative.
