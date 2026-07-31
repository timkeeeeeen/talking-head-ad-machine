# Release acceptance evidence

The macOS records certify the exact `0.2.0` buyer artifacts at SHA-256 `5888fcab0f47aa0f04c5bf8e85acac6f431f30176cea43aa2f95935156cf9f00` on both Apple Silicon and Intel hardware.

Windows x64 has repeatable full-runtime evidence on GitHub's Windows Server runner. It is not yet a Windows 11 buyer-platform acceptance because the real Winget installer has not run on a clean Windows 11 x64 client. Do not advertise Windows support until `windows11InstallerAccepted` is true in a matching artifact record.

These records are excluded from buyer ZIPs, so adding evidence cannot change the artifact hash it certifies.
