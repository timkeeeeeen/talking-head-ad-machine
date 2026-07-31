# Platform acceptance

A platform is a release candidate until its exact buyer ZIP passes on a matching clean machine. Structural archive checks, mocked unit tests, and CI do not authorize a sales claim by themselves.

Windows Server CI uses `--acceptance-class runtime-ci`. It proves the Windows x64 media runtime, `.cmd` launch paths, and render stack, but it does not prove the Windows 11 installer or authorize the Windows 11 sales claim.

Run the release gate from a clean machine with Codex or Claude Code and internet access:

```text
python scripts/build_release.py
python scripts/verify_release.py --fresh-setup --golden --full-workflow
```

The gate must prove:

- The platform-specific installer completes from the extracted buyer ZIP.
- Doctor finds the locked Python, Kinocut, MCP, HyperFrames, Node, FFmpeg, FFprobe, and whisper.cpp contract.
- The deterministic demo passes.
- The included synthetic talking-head fixture is freshly transcribed locally.
- The inspectable plan validates and the clean edit renders at the expected duration.
- HyperFrames checks and renders the designed preview.
- Audio normalization and final technical QA pass.
- Review and sanitized support archives are created.
- The source-media hash remains unchanged.
- Re-running installation succeeds without destructive cleanup.

Retain `dist/acceptance-report-PLATFORM.json` and `acceptance/PLATFORM/latest-report.json` as evidence. Record the accepted artifact SHA-256 under `docs/acceptance` and update funnel claims only after reviewing both reports. Acceptance records are intentionally excluded from buyer ZIPs so recording evidence cannot change the artifact it certifies.
