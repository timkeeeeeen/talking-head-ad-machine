# Troubleshooting

Ask the agent to run `./bin/ad-machine doctor --json` on macOS or `powershell -ExecutionPolicy Bypass -File .\bin\ad-machine.ps1 doctor --json` on Windows first. Missing optional Docker, TTS, music, or Resolve integrations do not block the core workflow.

If setup is incomplete, ask: `Repair the required Talking-Head Ad Machine setup and rerun the demo.`

On macOS, the agent should inspect `./install.sh --plan` before rerunning `./install.sh`. On Windows, it should inspect `powershell -ExecutionPolicy Bypass -File .\install.ps1 -PlanOnly` before rerunning the installer. Restart Codex or Claude Code if Winget installed a command successfully but the current process cannot see its updated PATH.

If a render duration is wrong, the agent must reject it and use the timestamp-reset fallback rather than manually stretching or trimming the output.

If a designed preview fails, ask the agent to inspect the generated HyperFrames `check.json` and snapshots. It must repair runtime, layout, motion, contrast, or safe-zone defects before rendering another preview.

If a job stops, ask: `Resume this job without repeating valid expensive work: [job folder].`

If support is needed, ask the agent to create a sanitized support report. It excludes footage and transcripts by default.
