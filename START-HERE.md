# Start here

Talking-Head Ad Machine turns a user-owned speaking video into a reviewable Facebook or Instagram ad. It uses Codex or Claude Code to operate local editing tools on your behalf.

## What you need

- Windows 11 x64, an Apple Silicon Mac, or an Intel Mac listed as supported at purchase.
- Codex or Claude Code already available.
- A video you own or have permission to edit.
- Enough free disk space for models, previews, and renders.

The `0.2.0` installers target all three platforms. A platform must pass its published clean-machine acceptance report before the sales page describes it as supported. See `docs/COMPATIBILITY.md` for the current proof status.

## First use

1. Unzip this product into a normal writable folder and open that folder in Codex or Claude Code. On macOS, the included `.command` launchers are also available.
2. Tell the agent: `Install this product, check my computer, repair ordinary setup problems, and render the included demo.`
3. After the demo passes, tell it: `Turn this video into a 4:5 Facebook ad: [drag your video here]. Preserve my meaning, do not invent claims, and open a preview before finalizing it.`
4. Answer the offer, audience, and desired-action questions.
5. The agent will show you a checked, captioned social preview; it will not silently treat an automated check as your approval.
6. Review the preview. Ask for a specific revision or approve it.

The agent runs `install.sh` on macOS or `install.ps1` on Windows. The installer may install Homebrew on a Mac or use Winget on Windows. The product never publishes an ad. Rendering and transcription run locally by default, while your use of Codex or Claude remains subject to that provider's terms.
