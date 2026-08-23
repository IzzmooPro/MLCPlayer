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
- The maintainer confirmed on 23 August 2026 that multi-factor authentication
  is enabled. This is a user attestation; it is not independently proven by
  repository evidence.

These facts make an application plausible; only SignPath Foundation can make
the eligibility decision.

## Open gates before an application

1. Pass the protected PR gate for the prepared hosted unsigned-build workflow.
2. With separate approval, run it once on exact master and verify that the
   unsigned installer and provenance artifacts match the recorded commit and
   inputs.
3. Keep every signing request under manual approval and bind it to one exact
   commit and version.
4. Obtain SignPath acceptance before adding its action, token or certificate
   claims to the active release workflow.
5. Add the required code-signing-policy link to the release/download page only
   when the first accepted signed release is being prepared.

## Prepared libmpv runtime mirror

`.github/workflows/publish-libmpv-runtime.yml` is a manual, one-time migration
workflow. It does not build libmpv, build MLC Player, invoke SignPath, create a
tag or change a release. It is prepared to:

- download Actions artifact `9452521445` from source-build run `32488810460`
  at commit `4b948676990dde217206b878fca388093a367b61`;
- require that artifact to remain unexpired and retain its exact recorded
  expiry, archive size/hash and DLL size/hash;
- publish the verified `mpv-2.dll` and provenance files once to project-owned
  GHCR storage, refusing to overwrite an existing tag;
- resolve the resulting OCI digest, pull it back by digest and compare every
  byte before emitting `runtime-lock.json`.

The workflow was dispatched once from exact master commit `81f881f` as run
`32620779433`. Its push/readback job passed, and the permanent manifest digest
is recorded in `packaging/libmpv_runtime_lock.json`. Anonymous OCI readback
returned HTTP 200 and the same manifest and DLL digests. The fixed tag must not
be overwritten or dispatched again.

## Prepared hosted unsigned build

`.github/workflows/build-unsigned-main.yml` is manual-only and runs on a
GitHub-hosted Windows 2025 runner. It is intentionally limited to the main
installer:

- actions, Python `3.13.15` and ORAS are pinned; Inno Setup must report
  `6.7.1` or the job stops;
- all 24 Windows wheels are exact-version and SHA-256 locked in
  `requirements-build-windows.txt`;
- libmpv is pulled by the reviewed OCI digest, and its size, SHA-256,
  provenance and tracked runtime manifest are rechecked;
- `packaging/build_unsigned_main.bat` requires an explicit hosted-build guard,
  uses the existing PyInstaller/Inno product path and omits the optional
  Internet Video installer;
- the resulting EXE must report `NotSigned`, no detached `.sig` may exist, and
  the exact EXE plus build provenance are stored as separate Actions artifacts.

The workflow does not call SignPath, access the local Ed25519 key, create a
tag or change a release. It has not been run; source and regression tests are
not installer-build evidence.

## Why the hosted build is not accepted yet

The current product build needs native runtime files that are intentionally
not committed to Git. The established release flow also creates detached
Ed25519 signatures with a private key kept outside the repository. Immutable
runtime acquisition and the hosted unsigned-build source boundary are now
prepared. They still require protected PR acceptance and one separately
approved real hosted build before they can support a SignPath application.

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
