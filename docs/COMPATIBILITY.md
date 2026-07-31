# Compatibility

Version `0.1.0` targets Apple Silicon Macs and supports Codex and Claude Code as the operating agents.

The current development machine passes required checks with Kinocut `1.11.1`, MCP Python SDK `1.29.0`, HyperFrames `0.7.86`, FFmpeg, FFprobe, whisper.cpp, Node, and npm. MCP Python SDK 2.0 is intentionally excluded because Kinocut `1.11.1` still imports the MCP 1.x `fastmcp` package path. Docker, local TTS, generated music, and DaVinci Resolve are optional.

Planning recommendation is 16 GB memory and 10 GB free disk, but public minimum claims remain provisional until the buyer ZIP passes a clean supported-Mac test.

Windows, Intel Mac, and Linux are not supported in version `0.1.0`.
