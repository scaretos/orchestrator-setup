# Changelog

## 1.6.0

- Installable as a Claude Code plugin: `claude plugin marketplace add scaretos/orchestrator-setup`, `claude plugin install orchestrator-setup@orchestrator-setup`, then `/orchestrator-setup:install` in the project. The plugin only delivers the setup: its one skill copies the template into the project's `.claude/` with the installer and runs `/orchestrator-init`, so the skills stay project skills without a prefix, adapted in place and committed with the project. Run it again after `claude plugin update` to upgrade: it compares versions, shows the changelog entries in between and upgrades on a branch with the owner's OK.
- The installers never overwrite `orchestrator/profile.md` and `orchestrator/ledger.md`, not even with `--force` / `-Force`. Before, an upgrade with `--force` reset the profile that `/orchestrator-init` was meant to re-apply and the ledger's history.
- `install.ps1` warns, instead of failing, when the target is not a git repository (Windows PowerShell 5.1 made git's stderr fatal).
- The template itself did not change: a project on 1.5.0 needs no upgrade.

## 1.5.0

- Parallel groups: stages that provably don't touch each other's work run at the same time, each in its own worktree.
  - `/write-plan` has a new step 7 (the steps after it move up by one). A group needs every one of these: no dependency between members; disjoint files, counting test files, fixtures, *Same piece of work* files and side-effect files (lockfiles, generated code, snapshots, migrations and their numbering, registrations, index and project files); no member calls, extends, tests or reads code another changes; verify commands that can run at the same time; no open decision or owner check inside the group; each member a full implement-and-review cycle, at most 3 per group. A clean concern is never split or merged to make a group.
  - The plan template has a *Parallel groups* section with the evidence per group (files per member, code between members, runtime, merge order). The self-check checks each group by Grep, and a review fix that touches a member means the whole group is checked again.
  - `plan-reviewer` verifies every claim of a group against the plan and the code. It also looks for side-effect files the section does not list. Anything it cannot prove is a Must fix.
  - `/execute-plan` runs the first member in the feature worktree and gives each other member a worktree at the group base, prepared with `WORKTREE_PREP`. It refuses to commit a file outside a member's list, cherry-picks the members in merge order, and runs every member's verify on the merged tree. A conflict or a failing group check stops the run for the owner and is logged as a planning miss. The resume step handles a group that was interrupted.
  - `stage-implementer` and `stage-reviewer` work in the work tree they are given. A parallel member that needs a file outside its list reports BLOCKED.
  - `workflow-analyst` reports the time groups saved, what they cost, and every group failure as a plan defect.
  - A switch turns all of this off. `- **Parallel stages:** on | off` sits under the new *Switches* section of `profile.md`, and the skills read it each time they run, so an edit applies to the next plan or execution without re-running `/orchestrator-init`. `/orchestrator-init` asks the owner, recommending `on` only when `WORKTREE_PREP` is quick. With `off`, `/write-plan` skips step 7 and writes no groups, `plan-reviewer` treats any group as a Must fix, and `/execute-plan` runs the members of a group already written one after another in the feature worktree. `--sequential` on `/write-plan` or `/execute-plan` does the same for one run. A missing switch (a profile from before 1.5.0) counts as off.

## 1.4.0

- `/orchestrator-init` sets up the language server (new step 8). For each main language it finds the plugin in the official marketplace whose `lspServers` serves the language's extensions, checks whether the plugin is installed and its server binary is on PATH, and asks once with the exact commands. It installs what the owner approves: the plugin at project scope by default (recorded in `.claude/settings.json`), the binary with a user-level installer. Commands that need `sudo` or an elevated shell are left to the owner. After `/reload-plugins` it checks that `findReferences` agrees with a Grep.
- New profile key `LSP_SETUP`: the plugin, binary and install command per language, written into the *Reading rules* of `CLAUDE.md` so an agent whose server is missing names the fix.
- Agents that find callers by Grep instead of `findReferences` say so in their report.

## 1.3.0

- Stages are grouped by concern, then by the files they touch, and sized by what the agent must read; the 6-file cap is gone.
- The plan reviewer looks up the callers of every member the plan changes; one that no stage covers is a Must fix.
- `/workflow-review` counts escaped defects (later fixes to code a run built, with the check that missed each); a change that cut cost while they rose counts as regressed. The execution log records changed files per stage and the finish date for this.

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

## 1.1.0

- `analyze.py receipt`: a shareable cost receipt of your latest session, a session id, or the last N days (`--since`), for one project or all (`--all-projects`). Terminal text, `--svg`, or a 1080-px `--png` (Pillow). `--redact` hides file names and commands.
- `analyze.py` works on its own (one `curl`, Python 3 standard library) and prices every turn at its model's published API rates; `metrics` gains an "API $" column next to the relative units.
- Carry cost: what each large tool result cost by being re-read on every later turn.
- Cache misses: turns whose cache read dropped below half the previous context, split into misses after an idle pause longer than the cache lifetime and other misses; priced as the earlier context written again minus a warm read. Checked against Claude Code's own `total_cost_usd` (exact match on two sessions).
- `runs` tolerates JSON written with spaces.
- Tests: synthetic transcripts and template contract checks.
## 1.0.0

- First public version: `/write-plan`, `/execute-plan`, `/retro`, `/workflow-review`, `/orchestrator-init`, five agents, installers.
