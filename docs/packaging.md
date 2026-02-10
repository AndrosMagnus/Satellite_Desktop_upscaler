# Packaging and Distribution

## Current Build Assets
- PyInstaller spec: `packaging/pyinstaller/satellite_upscale.spec`
- Windows packaging script: `scripts/package_windows.ps1`
- macOS packaging script: `scripts/package_macos.sh`
- Linux packaging script: `scripts/package_linux.sh`
- Release checksum script: `scripts/generate_release_checksums.py`
- Release workflow: `.github/workflows/release_build_sign_attest.yml`

## Windows
- Build app bundle:
  - `powershell -File scripts/package_windows.ps1`
- Build MSI (requires WiX):
  - `powershell -File scripts/package_windows.ps1 -BuildMsi`

## macOS
- Build app bundle + optional DMG:
  - `bash scripts/package_macos.sh`
- Requires `create-dmg` for DMG packaging.

## Linux
- Build app bundle + optional AppImage:
  - `bash scripts/package_linux.sh`
- Requires `linuxdeploy` for AppImage packaging.

## Signing
- A no-cost signing/provenance path is automated in CI:
  - Keyless Sigstore signing (`cosign sign-blob`) for release artifacts.
  - GitHub artifact attestations (`actions/attest-build-provenance@v3`).
- This provides supply-chain integrity and provenance verification without buying a certificate.

## Free Verification Flow (for users)
1. Download release artifact(s), matching `SHA256SUMS-<platform>.txt`, and `*.sigstore.json` bundles.
2. Verify checksum:
   - `sha256sum -c SHA256SUMS-<platform>.txt` (Linux/macOS)
   - `Get-FileHash` + compare manually on Windows.
3. Verify Sigstore bundle:
   - `cosign verify-blob --bundle <artifact>.sigstore.json --certificate-identity-regexp \"^https://github.com/<OWNER>/<REPO>/.github/workflows/release_build_sign_attest.yml@refs/tags/.*$\" --certificate-oidc-issuer https://token.actions.githubusercontent.com <artifact>`
4. Optionally verify GitHub attestation:
   - `gh attestation verify <artifact> --repo <OWNER>/<REPO>`

## What Free Signing Does Not Cover
- It does not replace Authenticode reputation on Windows SmartScreen.
- It does not replace Apple notarization on macOS Gatekeeper.
- If you need native trust dialogs (fewer warnings), you still need:
  - Windows code-signing certificate (OV/EV).
  - Apple Developer Program account for codesign + notarization.

## Installer Isolation
- Target is per-user install location.
- Scripts do not modify global PATH.
- Model/runtime files remain app-local or user-data local.
