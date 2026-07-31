# Job and cache contract

Treat the job directory as an append-only evidence package around mutable status.

Required stages are `initialized`, `preflighted`, `transcribed`, `planned`, `clean-cut-rendered`, `designed`, `qa-complete`, `awaiting-review`, `approved`, `delivered`, `failed-recoverable`, and `failed-terminal`.

Each recorded artifact includes its hash, producer, product version, input hashes, and creation time. A filename without a matching hash is not reusable evidence.

Invalidate downstream artifacts when their inputs change:

- Changed source invalidates everything.
- Changed edit plan invalidates clean A-roll, output-timed transcript, graphics, captions, audio mix, QA, and review.
- Changed clean cut invalidates output-timed transcript and every timed layer.
- Changed caption or CTA styling invalidates only the associated composition and downstream QA/review.
- Changed brand aesthetics do not alter approved evidence or factual claims.

Preserve failed receipts and last errors. Resume from the latest stage whose required artifact hashes match. Never silently downgrade a requested mode or claim completion after a partial render.

