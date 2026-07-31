# Resolve handoff

## Supported package

When available, include:

- `master.mov`: flattened high-quality master, preferably ProRes 422.
- `graphics-alpha.mov`: optional verified ProRes 4444 overlay.
- `dialogue.wav`, `music.wav`, and `sfx.wav`: separate stems when used.
- `captions.srt`: final output-timed captions.
- `edit-plan.normalized.json`: source-to-output map.
- Kinocut receipts and QA reports.
- Optional FCPXML.

Resolve can import the flattened master and supporting media. This is the reliable fallback.

## FCPXML boundary

Generate FCPXML only for one local source, constant speed, straight cuts, source time starting at zero, and embedded linked audio. Do not claim effects, captions, reframes, transitions, retiming, external audio, or nonzero camera timecode are represented.

Validate with `xmllint --noout`. Label the result best-effort until it imports successfully. If import or relinking takes more than a quick correction, use the flattened package.

