# SignPath Foundation readiness

This is an engineering checklist, not proof of acceptance and not legal
advice. MLC Player is currently **not application-ready** for SignPath. No
application has been submitted and SignPath has not accepted the project.

## Conditions already supported by current evidence

- The repository is public and licensed under OSI-approved GPL-3.0-only.
- MLC Player is actively maintained, documented and already released.
- The Windows packages include notices and corresponding-source records for
  their Open Source components.
- The product has uninstallers and does not contain telemetry or analytics.
- Upstream Open Source binaries are included as dependencies rather than
  represented as MLC Player-owned binaries.
- `CODE_SIGNING_POLICY.md` and `PRIVACY.md` document the intended signing
  roles, current unsigned status, network behavior and local-data behavior.

These facts make an application plausible; only SignPath Foundation can make
the eligibility decision.

## Open gates before an application

1. Confirm that every maintainer account used for GitHub and SignPath has
   multi-factor authentication enabled. This cannot be proven from source.
2. Add a manual, GitHub-hosted unsigned-installer build whose inputs come from
   the repository or immutable, hash-verified artifacts.
3. Ensure the unsigned installer is uploaded as a GitHub Actions artifact
   before it is submitted through SignPath's GitHub connector.
4. Keep every signing request under manual approval and bind it to one exact
   commit and version.
5. Obtain SignPath acceptance before adding its action, token or certificate
   claims to the active release workflow.
6. Add the required code-signing-policy link to the release/download page only
   when the first accepted signed release is being prepared.

## Why the hosted build is not added yet

The current product build needs native runtime files that are intentionally
not committed to Git. The established release flow also creates detached
Ed25519 signatures with a private key kept outside the repository. Moving the
whole chain into CI without first defining immutable runtime acquisition and
the signing boundary would weaken the existing release evidence.

The safe future sequence is:

1. GitHub-hosted runner builds the exact unsigned installers.
2. The unsigned artifact is stored by GitHub Actions.
3. After SignPath acceptance and manual approval, SignPath applies
   Authenticode to the installer bytes.
4. The final Authenticode-signed installer is downloaded to the controlled
   release environment.
5. The existing Ed25519 process signs the final installer's SHA-256 and
   produces the detached `.sig` file.
6. Existing install, upgrade, uninstall, native-smoke and release-parity gates
   run against those final bytes.

Until all gates exist and pass, SignPath is a planned option only. The current
release process remains authoritative and unchanged in behavior.
