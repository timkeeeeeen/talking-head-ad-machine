# Troubleshooting

Ask the agent to run `./bin/ad-machine doctor --json` first. Missing optional Docker, TTS, music, or Resolve integrations do not block the core workflow.

If setup is incomplete, ask: `Repair the required Talking-Head Ad Machine setup and rerun the demo.`

If a render duration is wrong, the agent must reject it and use the timestamp-reset fallback rather than manually stretching or trimming the output.

If a designed preview fails, ask the agent to inspect the generated HyperFrames `check.json` and snapshots. It must repair runtime, layout, motion, contrast, or safe-zone defects before rendering another preview.

If a job stops, ask: `Resume this job without repeating valid expensive work: [job folder].`

If support is needed, ask the agent to create a sanitized support report. It excludes footage and transcripts by default.
