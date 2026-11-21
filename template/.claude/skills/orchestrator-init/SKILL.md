---
name: orchestrator-init
description: Adapt the installed plan-and-execute orchestrator setup to this project. Detects build, test, shell and layout, fills every {{PLACEHOLDER}} and ADAPT block in .claude/, merges the CLAUDE.md sections, creates a gate script if there is none, and wires settings with the owner's OK. Run once after installing, and again after upgrading the setup or changing .claude/orchestrator/profile.md.
disable-model-invocation: true
---

Adapt the orchestrator setup in `.claude/` to this repository. The installed skills and agents are generic: they hold `{{KEY}}` placeholders and `<!-- ADAPT: name -->…<!-- /ADAPT -->` blocks that only fit once they name this project's real commands, layers and traps. The result must read as if it had been written for this project: agents follow it literally, and every vague line costs them searches on every run.

Spend little: this runs once. Detect from files, not from long explorations; ask the owner only what the files cannot answer.

## 1. Inventory

In one message: Grep `\{\{[A-Z_]+\}\}` and `ADAPT:` under `.claude/` (files with matches), read `.claude/orchestrator/profile.md`, and check for an existing root `CLAUDE.md`, `.claude/settings.json` and `.claude/rules/`. A profile that already has values means a re-run: reuse them, ask only about empty ones, and skip to step 4.

## 2. Detect

One parallel batch of Glob, Read (small files, or ranges) and short read-only commands:
- **Stack and commands:** build files at the root and one level down (`package.json`, `*.sln`/`*.csproj`, `Cargo.toml`, `go.mod`, `pyproject.toml`/`setup.cfg`, `pom.xml`, `build.gradle*`, `Makefile`, `CMakeLists.txt`), and CI workflows (`.github/workflows/*`, `.gitlab-ci.yml`, `azure-pipelines.yml`): CI usually holds the project's true build and test commands. Find the test framework and its filter syntax (`--filter`, `-k`, `-t`, `--grep`, `-run`).
- **Environment:** OS and shell (Windows PowerShell 5.1, PowerShell 7, bash, zsh), Python 3 command (`python3 --version`, `python --version`, `py -3 --version`), Node (`node --version`, for the optional hook), `git remote -v` and `git symbolic-ref refs/remotes/origin/HEAD` (default branch; with no remote, the current branch), the remote's host and whether `gh` (or `glab`) is installed, `git config core.autocrlf`. No remote is fine: `/execute-plan` then works on local branches and skips pushes and PRs; set `PR_CMD` to "none (no remote)" and say so in the report.
- **Layout:** the top-level folders and what each holds (one line each), build output folders, existing folder `CLAUDE.md` files.
- **Language tooling:** whether a language server is active: an `LSP` tool in your own tool list means a plugin is installed; call its `documentSymbol` on one source file to see that it serves this language. The agents use `findReferences` and fall back to Grep without one; if none is active, name the Claude Code LSP plugin for the main language in the report.

In a large monorepo, one `Explore` call with concrete questions (packages, their test commands, shared libraries) is cheaper than many reads.

## 3. Decide the values

Fill every key of the profile table. Rules:
- **Commands are quiet and filtered.** `BUILD_CMD` builds one project or package and keeps the last lines (`2>&1 | tail -5` in bash, `2>&1 | Select-Object -Last 5` in PowerShell). `TEST_CMD` runs one filtered test set the same way, with `<project>` and `<filter>` left as literal placeholders for plans to fill. Agents pay for every output line on every later turn.
- **`TEST_FAIL_HINT`:** one sentence on how a failed run shows in that cut output (the summary word, the exit line), so an agent sees failure without reading the log. Language of the tool's output included (a localised SDK prints localised words).
- **`SHELL`:** the shell agents' commands run in. Windows: name `PowerShell 5.1` or `7` exactly; 5.1 has no `&&`, no ternary, and breaks quoted multi-line `git commit -m`. Set `EXTRA_TOOLS` to `, PowerShell` on Windows, else empty.
- **`WORKTREE_PREP`:** what makes a fresh checkout buildable before any agent opens a source file (dependency restore, first build, code index), as one line of commands.
- **`PLANS_DIR`:** default `~/.claude/plans`: outside the repo, because a worktree cannot see untracked files and plans are not committed.
- **`EXTERNAL_SYSTEMS`:** systems whose behaviour the code does not show and plans must measure (a third-party application, a database engine, a payment API, a browser engine). None: write "none so far" and simplify step 4 of `/write-plan` to the probe rule only.
- **`UI_CHECK`:** how a UI change is seen without a person (a screenshot or render command, a storybook, visual tests). None: "none: the owner check decides".
- **`LAYERS`:** the project's real layers and what each may and may not do, in one line.
- **`MACHINE_TRAPS`:** known environment traps (locked files while the app runs, services that must be up, slow commands and their real duration, localised tool output). None known: one line "none known yet: `/retro` adds them as they turn up".

Show the owner the filled table in one message and ask with one `AskUserQuestion` (at most 4 questions) only about what detection could not settle: usually the gate's contents if there is no CI, the external systems, the UI check. Offer your detected value as the first, recommended option.

## 4. Fill the files

- Replace every `{{KEY}}` in `.claude/` with its value, using Edit (not in this skill's own folder, which keeps them for re-runs).
- Rewrite each ADAPT block for this project, then remove its two marker comments: *architecture* (the plan template's Architecture checklist: keep the generic items that apply, name this project's layers, entry points and data stores, add the items its reviews will need), *layout* (`Explore`'s folder table), *machine* (the *This machine* lists), *external* and *ui-check* (`/write-plan`).
- Write the values into `profile.md` (keys stay without braces), with the setup version from `.claude/orchestrator/VERSION` and today's date.
- Verify: Grep `\{\{[A-Z_]+\}\}|ADAPT:` under `.claude/` finds nothing outside `orchestrator/claude-md-sections.md` and `orchestrator-init/`.

## 5. The gate

The workflow needs one command that proves a piece of work: build, the test suites that need no special environment, and a quick smoke check if the project has one. If the project has none, write `scripts/gate.sh` (or `scripts/gate.ps1` on Windows) from the CI steps: it runs each step, writes the full output to `GATE_LOG`, prints only a one-line result per step and the failing lines, and exits non-zero on failure. Add `GATE_LOG` to `.gitignore`. Run it once in the foreground with a long timeout and report the result; a failure that exists on the default branch is reported, not fixed.

## 6. CLAUDE.md

Merge the sections of `.claude/orchestrator/claude-md-sections.md` (placeholders filled) into the root `CLAUDE.md`:
- No `CLAUDE.md` yet: create one with a project overview of at most 15 lines (what it is, the folders, the main commands), then the sections.
- Existing one: add only the sections it lacks. Where it already has an equivalent rule, keep the owner's and tell them about the difference. Keep the root file to pointers, commands and traps: it is read on every turn of every agent.

## 7. Settings

Show the owner `.claude/orchestrator/settings.snippet.json` merged into their `.claude/settings.json` (without the `//` notes, deny list cut to the build folders this project has, the hook only if checkouts use CRLF and Node is installed) as a diff, with each part's reason from its note. Write only the parts they approve.

## 8. Starter rules

Propose at most 3 `.claude/rules/<topic>.md` files for the areas where detection showed traps or the most complex code, each with `paths:` frontmatter and a few lines of facts that are not obvious from the code. Check every `paths:` glob hits files (`git ls-files`). Write only those the owner approves; `/retro` grows them from real work.

## 9. Report

The profile table, the files changed, the gate result, what was left for the owner (settings parts declined, a missing LSP plugin, a gate failure). Then how to start: a small change needs no workflow; for a larger one, `/write-plan <feature>`, read the plan, `/execute-plan <plan>` in a new session; after 2–3 executions, `/workflow-review`. Suggest committing `.claude/` and `CLAUDE.md` on a branch.
