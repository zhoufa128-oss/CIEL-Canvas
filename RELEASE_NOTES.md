# CIEL Canvas 1.0.0

## Assets

- **Windows x64 Portable**: extract and run on Windows x64. The executable is not currently code-signed; SmartScreen may show a warning.
- **macOS arm64 BuildKit**: run the build on an Apple Silicon Mac. This asset is not a prebuilt application and does not include a finished `.app`.
- **SHA256SUMS.txt**: checksums for the two release assets.

## Important notes

- Configure API keys yourself; no real secrets are included.
- The macOS build requires macOS 11+, Python 3.11–3.14, and Xcode Command Line Tools. Intel Macs are not supported.
- The Windows Portable package creates `UserData/` for local configuration, logs, canvases, and outputs. Keep it private.
- The supplied license is non-commercial and requires continued source disclosure and attribution. It is not MIT, Apache, GPL, BSD, or a free-commercial-use license.
- CIEL Canvas is based on Infinite-Canvas (`hero8152/Infinite-Canvas`) and includes modifications and CIEL branding.
- Verify the downloaded archives against `SHA256SUMS.txt` before use.

