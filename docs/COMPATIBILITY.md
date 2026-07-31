# Compatibility

Version `0.2.0` targets Windows 11 x64, Apple Silicon macOS, and Intel macOS. Codex or Claude Code is required as the operating agent. Linux and Windows ARM are out of scope.

| Platform | Artifact | Distribution gate |
| --- | --- | --- |
| Apple Silicon macOS | `talking-head-ad-machine-macos-arm64-v0.2.0.zip` | Publish only with acceptance evidence matching the artifact SHA-256 |
| Intel macOS | `talking-head-ad-machine-macos-x64-v0.2.0.zip` | Publish only with acceptance evidence matching the artifact SHA-256 |
| Windows 11 x64 | `talking-head-ad-machine-windows-x64-v0.2.0.zip` | Publish only with acceptance evidence matching the artifact SHA-256 |

Structural checks and mocked platform tests are necessary but are not platform acceptance. Sales copy may call a platform supported only when that exact artifact has completed setup, doctor, demo, transcription, clean cutting, HyperFrames rendering, QA, review generation, and support-report creation on a matching clean machine.

Acceptance records live outside the buyer ZIP in the repository's `docs/acceptance` directory and release attachments. Keeping evidence outside the payload allows a report to certify an immutable artifact without changing that artifact's hash.

The locked runtime uses Kinocut `1.11.1`, MCP Python SDK `1.29.0`, HyperFrames `0.7.86`, Python `3.12`, Node `22` or newer, FFmpeg, FFprobe, and whisper.cpp. MCP Python SDK 2.0 is intentionally excluded because Kinocut `1.11.1` still imports the MCP 1.x `fastmcp` package path. Docker, local TTS, generated music, and DaVinci Resolve are optional.

Planning guidance is 16 GB memory and 10 GB free disk. Public minimum operating-system, memory, disk, and installation-time claims remain provisional until clean-machine acceptance supplies evidence.
