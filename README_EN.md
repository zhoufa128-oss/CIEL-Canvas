# CIEL Canvas

CIEL Canvas is a non-commercial public source release based on and iterated from [Infinite-Canvas](https://github.com/hero8152/Infinite-Canvas). Current version: **1.0.0**.

## Downloads

Download the assets from the [v1.0.0 release](https://github.com/zhoufa128-oss/CIEL-Canvas/releases/tag/v1.0.0):

- **Windows x64 Portable**: extract and run. The Windows executable is currently unsigned, so SmartScreen may require manual confirmation.
- **macOS Apple Silicon BuildKit**: build tools for a real Apple Silicon Mac, not a prebuilt `.app`. macOS 11+, Python 3.11–3.14, and Xcode Command Line Tools are required.

Verify every downloaded asset with the published `SHA256SUMS.txt`.

## Build on macOS

```zsh
cd CIEL_Canvas_1.0.0_macOS_arm64_BuildKit
python3 Build/build_macos_arm64_release.py --self-check
python3 Build/build_macos_arm64_release.py
```

See [`Docs/macOS_AppleSilicon_构建说明.md`](Docs/macOS_AppleSilicon_构建说明.md). Windows can run static checks only; it cannot produce a runnable Mach-O application.

## Configuration and data

Users must configure their own API keys. This repository contains only empty examples and public provider endpoints. Never commit `.env`, `UserData/`, logs, caches, uploads, or diagnostics.

## Attribution and license

The upstream project is Infinite-Canvas (`hero8152/Infinite-Canvas`). CIEL Canvas is a modified and iterated version; the original code is not claimed as wholly created by CIEL. Keep the supplied [`LICENSE`](LICENSE) unchanged and follow its non-commercial, source-disclosure, and attribution requirements. Do not describe this project as MIT, Apache, GPL, BSD, or freely commercial software. Commercial packaging, sales, or other commercial use requires the appropriate authorization.

See [`SOURCE_AND_ATTRIBUTION.md`](SOURCE_AND_ATTRIBUTION.md) and [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
