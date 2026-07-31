---
name: talking-head-ad-machine
description: Turn user-owned talking-head recordings into truthful, reviewable Facebook and Instagram ads. Use when the user asks to edit a person speaking, remove mistakes or dead air, find source-backed hooks, add captions or motion graphics, create social crops or variants, normalize audio, resume a prior ad job, review an edit, save a brand treatment, or prepare an optional Resolve handoff.
---

# Talking-Head Ad Machine

Operate the product workspace for the buyer. Protect the camera original, preserve the speaker's meaning, keep creative decisions inspectable, and stop for approval at the preview.

Use `./bin/ad-machine` on macOS and `powershell -ExecutionPolicy Bypass -File .\bin\ad-machine.ps1` on Windows. The examples below use the shorter macOS spelling; translate it to the Windows command surface when required. Do not ask the buyer to run terminal commands, edit JSON, configure MCP, or debug dependencies.

## Non-negotiable rules

- Never overwrite, move, rename, or modify the camera original.
- Never upload media or transcripts without explicit permission.
- Never invent customer results, evidence, product behavior, testimonials, numbers, or compliance claims.
- Preserve complete thoughts, grammar, causal meaning, qualifiers, and natural breath.
- Keep semantic choices in a validated `edit-plan.normalized.json`.
- Render a low-resolution preview before the final.
- Keep approval pending until the buyer explicitly approves.
- Never publish an ad.
- Treat FCPXML as best effort. The flattened master, SRT, edit plan, and receipts are the supported handoff.

Read [creative-rules.md](references/creative-rules.md) before selecting cuts or visuals. Read [job-contract.md](references/job-contract.md) when resuming, repairing, or invalidating cached artifacts. Read [resolve-handoff.md](references/resolve-handoff.md) only when Resolve output is requested.

## 1. Preflight the workspace

Detect the platform first. If the product environment does not exist, explain the installation plan and run `./install.sh` on macOS or `powershell -ExecutionPolicy Bypass -File .\install.ps1` on Windows. Own ordinary prompts and recovery; ask the buyer only when the operating system requires their password or administrator approval.

Then run:

```bash
./bin/ad-machine doctor --json
```

If required checks fail after bootstrap, run `./bin/ad-machine setup` to inspect the repair plan, explain material changes in plain language, then run `./bin/ad-machine setup --apply`. Docker, TTS, generated music, and Resolve are optional and must not block the core workflow. Do not claim platform compatibility until doctor and the included demo both pass.

For first use, run `./bin/ad-machine demo --open`. A passing deterministic demo proves job creation, timestamp-reset rendering, duration verification, receipts, and local review. It does not prove creative quality on the buyer's footage.

## 2. Create or resume a job

For new footage:

```bash
./bin/ad-machine new "/absolute/path/to/video.mov" --mode fast --json
```

Use Fast for the first preview unless the brief clearly requires Designed or Studio. Designed adds evidence-backed graphics. Studio adds cached subject matting and must include an honest time warning.

For an existing job:

```bash
./bin/ad-machine resume "/absolute/path/to/job" --json
```

Trust recorded hashes and stages, not filenames alone. Reuse valid transcript, clean A-roll, masks, graphics, and audio. Invalidate timing-dependent downstream artifacts after a cut change. Do not repeat background removal for a caption or CTA-only revision.

## 3. Complete the brief

Read `brief.json`. Ask only for missing facts the buyer can supply:

- Offer
- Audience
- Desired action
- Allowed evidence
- Prohibited claims
- Target duration and ratio
- Logo, product screens, or brand profile

Flag a weak source instead of decorating it. Recommend rerecording when audio, framing, crop headroom, incomplete thoughts, missing CTA, or unsupported claims make the requested ad unreliable.

## 4. Transcribe and plan

Prefer local HyperFrames transcription with word timestamps:

```bash
./bin/ad-machine transcribe "/absolute/path/to/job" --json
```

Re-conform or re-transcribe the clean cut before captions and graphics.

Build the spoken audio spine before visual polish. Write `plans/edit-plan.json` using [edit-plan.md](references/edit-plan.md), then validate:

```bash
./bin/ad-machine validate-plan \
  "/absolute/path/to/job/plans/edit-plan.json" \
  --output "/absolute/path/to/job/plans/edit-plan.normalized.json" --json
```

Fix every validation error. Highlight semantic cuts below `0.8` confidence in review.

## 5. Render clean A-roll

Prefer a guarded Kinocut straight-cut render and preserve its receipt. Immediately verify the output against the plan:

```bash
./bin/ad-machine verify-duration "/absolute/path/to/job" VARIANT_ID "/path/to/render.mp4" --json
```

If the command fails, reject the render and use the deterministic timestamp-reset fallback:

```bash
./bin/ad-machine render-clean "/absolute/path/to/job" VARIANT_ID --json
```

Listen around every boundary. Repair clipped phonemes, breaths, jump cuts, black frames, and frozen tails before design.

## 6. Design with HyperFrames

Feed clean A-roll to HyperFrames, never the uncut recording. For the default Fast path, create and gate the reusable composition:

```bash
./bin/ad-machine design-fast \
  "/absolute/path/to/job" VARIANT_ID "/path/to/clean-a-roll.mp4" \
  --hook "Source-backed hook" --cta "Desired action" --ratio 4:5 --json

./bin/ad-machine check-design "/absolute/path/to/generated/hyperframes/project" --json
```

Inspect the generated snapshots before paying for a render. Fix visual defects in the generated project or regenerate it with a better hook, CTA, ratio, or brand accent. When the checks and sampled frames are sound, render the low-resolution review preview:

```bash
./bin/ad-machine render-preview \
  "/absolute/path/to/job" VARIANT_ID "/absolute/path/to/generated/hyperframes/project" --json
```

This command produces a preview only and keeps human approval pending. Use the official HyperFrames router and talking-head workflow for more elaborate Designed or Studio treatments.

Every visual must hook, explain, prove, contrast, orient, or direct action. Prefer supplied product screens and evidence over generated or generic imagery. Protect the face, captions, product UI, and platform safe zones.

Fast uses accurate captions, social framing, audio normalization, and restrained hook/CTA treatment. Designed adds useful cards, comparisons, screenshots, and proof annotations. Studio may use proxy subject matting and a virtual set. Cache the mask and report the expected delay.

## 7. Finish and inspect

Require:

- Legible first-frame or first-two-second hook treatment.
- Accurate output-timed captions.
- Clear dialogue and documented loudness.
- No unsafe crop, obscured face, clipped speech, black frame, or frozen tail.
- H.264/AAC `yuv420p` delivery output.
- No more than three evidence-driven repair passes.

Run technical output QA against the planned variant:

```bash
./bin/ad-machine qa "/absolute/path/to/job" VARIANT_ID "/path/to/output.mp4" --json
```

If the designed output has not already been normalized, create a new normalized derivative before QA:

```bash
./bin/ad-machine normalize-audio "/absolute/path/to/job" VARIANT_ID "/path/to/input.mp4" --json
```

Generate the review page:

```bash
./bin/ad-machine review "/absolute/path/to/job" --json
```

Open the review and summarize low-confidence cuts, graphics, evidence, QA, and unresolved uncertainty. Do not approve on the buyer's behalf.

After explicit approval:

```bash
./bin/ad-machine approve "/absolute/path/to/job" --note "Buyer approved preview" --json
```

Offer to save aesthetic treatment to the single brand profile. Never learn factual claims merely because the buyer approved the look.

## 8. Optional modules and handoff

List installed modules with `./bin/ad-machine modules list --json`. Install a purchased module only from the buyer's local ZIP using `./bin/ad-machine modules install "/path/to/module.zip" --json`.

Use Ad Test Lab only for organized variants after a standalone ad works. Use Client Edition only when actually installed. Never imply that an extension is required for the core result.

When Resolve is requested, preserve the flattened master, captions, plan, receipts, and available stems. Generate FCPXML only for its narrow supported case:

```bash
./bin/ad-machine make-fcpxml "/absolute/path/to/job" VARIANT_ID --json
```

Abandon FCPXML quickly if import becomes finicky.
