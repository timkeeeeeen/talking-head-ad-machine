# Edit plan contract

Use JSON with `schemaVersion: 1`.

```json
{
  "schemaVersion": 1,
  "source": {
    "path": "/absolute/path/recording.mp4",
    "durationSeconds": 92.4,
    "sha256": "..."
  },
  "variants": [
    {
      "id": "hook-demo",
      "label": "Demo-first hook",
      "targetRatios": ["4:5"],
      "segments": [
        {
          "sourceStart": 31.12,
          "sourceEnd": 35.84,
          "text": "Watch what happens when I...",
          "reason": "Strong self-contained demonstration hook",
          "beat": "hook",
          "confidence": 0.94
        }
      ]
    }
  ]
}
```

List segments in output order. Keep source times in seconds. The validator adds output ranges and variant duration.

Valid beats: `hook`, `problem`, `mechanism`, `proof`, `objection`, `cta`, `transition`, and `context`.

Every segment needs an exact nonempty quote, an editorial reason, and confidence from zero to one. Do not overlap ranges unless source reuse is explicit and intentional.

