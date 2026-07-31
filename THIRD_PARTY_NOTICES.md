# Third-party notices

Talking-Head Ad Machine integrates with third-party software rather than claiming ownership of it.

## Kinocut

- Initial pinned version: `1.11.1`
- Source: <https://github.com/KyaniteLabs/kinocut>
- License: Apache License 2.0

## HyperFrames

- Initial pinned version: `0.7.86`
- Package: <https://www.npmjs.com/package/hyperframes>
- License: Apache License 2.0

## FFmpeg

- Project: <https://ffmpeg.org/>
- License varies by build configuration. The product does not redistribute a Homebrew FFmpeg binary; setup installs or locates the buyer's system copy.

## whisper.cpp

- Source: <https://github.com/ggml-org/whisper.cpp>
- License: MIT

## Model Context Protocol Python SDK

- Initial compatibility pin: `mcp==1.29.0`
- Source: <https://github.com/modelcontextprotocol/python-sdk>
- License: MIT
- Reason for pin: Kinocut `1.11.1` imports the MCP 1.x `fastmcp` package path and is not compatible with MCP 2.0.

The release process must recheck versions and notices whenever dependency pins change.
