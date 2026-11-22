# Changelog

## 1.2.0

- New `/restructure-docs` skill: a one-time audit and optimization of a project's Claude Code knowledge base. It distinguishes observable behavior (implementation, tests, build configuration and CI) from intended behavior (owner decisions and architectural records), audits root and nested `CLAUDE.md` files, `.claude/rules/`, agents and skills, then corrects, consolidates, removes and adds knowledge with evidence. It reports disagreements, prioritizes high-value knowledge over completeness, preserves human documentation and orchestrator operations, and changes nothing before the owner approves the audit and the plan. Owner-invoked only; works on a dedicated branch and opens a draft PR only when the repository supports it.
- Four standard-library Python helpers in the skill: `analyze_docs.py` (section and paragraph inventory plus referenced files), `split_docs.py` (optional mechanical move of sections that are already correct), `check_rules.py` (simulated dead-glob, shared-file and per-file matching), `verify_move.py` (review aid for lines and facts that disappeared; `--strict` as a gate for an unchanged move).
- The approval boundary distinguishes editorial changes from material ones; a second gate is needed for new facts, removals, destination moves, path-coverage changes and rule merges/splits. Rule loading is reported as simulated matching, not verified runtime loading, and the independent reviewer inspects implementation, tests and configuration directly.
- `/orchestrator-init` now detects hand-read documentation and points the owner at `/restructure-docs` after the first setup; it never runs it.
- README and `docs/how-it-works.md` describe the new skill.

## 1.1.0

- `analyze.py receipt`: a shareable cost receipt of your latest session, a session id, or the last N days (`--since`), for one project or all (`--all-projects`). Terminal text, `--svg`, or a 1080-px `--png` (Pillow). `--redact` hides file names and commands.
- `analyze.py` works on its own (one `curl`, Python 3 standard library) and prices every turn at its model's published API rates; `metrics` gains an "API $" column next to the relative units.
- Carry cost: what each large tool result cost by being re-read on every later turn.
- Cache misses: turns whose cache read dropped below half the previous context, split into misses after an idle pause longer than the cache lifetime and other misses; priced as the earlier context written again minus a warm read. Checked against Claude Code's own `total_cost_usd` (exact match on two sessions).
- `runs` tolerates JSON written with spaces.
- Tests: synthetic transcripts and template contract checks.
## 1.0.0

- First public version: `/write-plan`, `/execute-plan`, `/retro`, `/workflow-review`, `/orchestrator-init`, five agents, installers.
