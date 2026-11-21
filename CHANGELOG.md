# Changelog

## 1.1.0

- `analyze.py receipt`: a shareable cost receipt of your latest session, a session id, or the last N days (`--since`), for one project or all (`--all-projects`). Terminal text, `--svg`, or a 1080-px `--png` (Pillow). `--redact` hides file names and commands.
- `analyze.py` works on its own (one `curl`, Python 3 standard library) and prices every turn at its model's published API rates; `metrics` gains an "API $" column next to the relative units.
- Carry cost: what each large tool result cost by being re-read on every later turn.
- Cache misses: turns whose cache read dropped below half the previous context, split into misses after an idle pause longer than the cache lifetime and other misses; priced as the earlier context written again minus a warm read. Checked against Claude Code's own `total_cost_usd` (exact match on two sessions).
- `runs` tolerates JSON written with spaces.
- Tests: synthetic transcripts and template contract checks.
## 1.0.0

- First public version: `/write-plan`, `/execute-plan`, `/retro`, `/workflow-review`, `/orchestrator-init`, five agents, installers.
