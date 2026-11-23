# Changelog

## 1.2.0

- New `/restructure-docs` skill: a one-time audit and optimization of a project's Claude Code knowledge base.
  - It separates observable behavior (implementation, tests, build configuration and CI) from intended behavior (owner decisions and architectural records).
  - It audits root and folder `CLAUDE.md` files, `.claude/rules/`, agent-only guides and the factual context in agents and skills. It then corrects, consolidates, removes and adds knowledge with evidence.
  - It asks the owner where work costs the most and uses the skill's argument to focus.
  - It moves procedures into skills and adds a checklist skill for each recurring kind of change found in the git history.
  - It reports `must`/`never` instructions nothing enforces, and deny rules that match nothing, as hook or deny-rule proposals. It also flags workarounds for old model limits.
  - It reads `CLAUDE.local.md`, settings, hooks, user configuration, auto memory and hook-injected context, but never changes them.
  - The approval package is saved to `audit.md` in the plans folder. Nothing is written to the repository before the owner approves it.
  - Owner-invoked only. It branches from the default branch's commit and opens a draft PR only when the repository supports it.
- Four standard-library Python helpers in the skill:
  - `analyze_docs.py`: section and paragraph inventory with referenced files; `--history` lists folder sets that change together.
  - `split_docs.py`: optional verbatim move of correct sections. It refuses to overwrite a file that is not a source.
  - `check_rules.py`: dead globs, brace expansion, inline and comma-separated `paths:`, rules without `paths:` counted as loaded at launch, shared files, and probes with `--budget`.
  - `verify_move.py`: lines and facts that disappeared; `--base` reads the originals from a commit, and `--strict` is a gate for an unchanged move.
  - Heading parsing ignores headings inside code fences. The helpers have functional tests (`tests/test_restructure_docs.py`).
- Rule loading is checked twice: simulated by `check_rules.py`, and for real by a fresh `Explore` agent that reads the probe files. The approval boundary lets narrowing a glob or splitting a rule with unchanged probe coverage go ahead without a new approval. The independent Opus reviewer is read-only, and the tree is checked to be unchanged after it runs.
- `/orchestrator-init` now detects hand-read documentation and points the owner at `/restructure-docs` after the first setup; it never runs it.
- README and `docs/how-it-works.md` describe the new skill.
- Stages are grouped by concern, then by the files they touch, and sized by what the agent must read; the 6-file cap is gone.
- The plan reviewer looks up the callers of every member the plan changes; one that no stage covers is a Must fix.
- `/workflow-review` counts escaped defects (later fixes to code a run built, with the check that missed each); a change that cut cost while they rose counts as regressed. The execution log records changed files per stage and the finish date for this.

## 1.1.0

- `analyze.py receipt`: a shareable cost receipt of your latest session, a session id, or the last N days (`--since`), for one project or all (`--all-projects`). Terminal text, `--svg`, or a 1080-px `--png` (Pillow). `--redact` hides file names and commands.
- `analyze.py` works on its own (one `curl`, Python 3 standard library) and prices every turn at its model's published API rates; `metrics` gains an "API $" column next to the relative units.
- Carry cost: what each large tool result cost by being re-read on every later turn.
- Cache misses: turns whose cache read dropped below half the previous context, split into misses after an idle pause longer than the cache lifetime and other misses; priced as the earlier context written again minus a warm read. Checked against Claude Code's own `total_cost_usd` (exact match on two sessions).
- `runs` tolerates JSON written with spaces.
- Tests: synthetic transcripts and template contract checks.
## 1.0.0

- First public version: `/write-plan`, `/execute-plan`, `/retro`, `/workflow-review`, `/orchestrator-init`, five agents, installers.
