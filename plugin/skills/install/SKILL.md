---
name: install
description: Install or upgrade the orchestrator setup (/write-plan, /execute-plan, /retro, /workflow-review, /restructure-docs and their agents) in this project's .claude/ folder, then adapt it with /orchestrator-init. Run once per project, and again after updating the plugin.
disable-model-invocation: true
---

Install the orchestrator setup into the project open in this session. The plugin only delivers it: the skills and agents are copied into the project's `.claude/`, because `/orchestrator-init` fills them with this project's commands and `/workflow-review` improves them over time. Both edit the files in place, and those edits belong in the project's repository, not in the plugin's folder, which every plugin update replaces.

Plugin files: the template is `${CLAUDE_PLUGIN_ROOT}/template/.claude`, its version `${CLAUDE_PLUGIN_ROOT}/template/.claude/orchestrator/VERSION`, the changes per version `${CLAUDE_PLUGIN_ROOT}/CHANGELOG.md`.

## 1. Where and what

In one message: `git rev-parse --show-toplevel` (the target; outside a git repository the current folder is the target, and warn that `/execute-plan` needs git worktrees), read the plugin's `VERSION`, and read the target's `.claude/orchestrator/VERSION` if it exists. If the target is the plugin's own folder or the orchestrator-setup repository itself, stop: there is nothing to install into.

- **No version file:** a fresh install. Go to step 2 without overwriting.
- **Same version:** already installed. Say so and stop; the owner re-runs `/orchestrator-init` only to re-apply an edited `profile.md`.
- **Newer in the project than in the plugin:** the plugin is out of date. Tell the owner to run `claude plugin update orchestrator-setup@orchestrator-setup` and then this skill again, and stop.
- **Older:** an upgrade. Show the owner the `CHANGELOG.md` entries newer than the project's version, in a few lines. An upgrade overwrites every installed file, including the ones `/orchestrator-init` adapted and `/workflow-review` or the owner improved; only the project's data, `profile.md` and `ledger.md`, is kept. `/orchestrator-init` then re-applies `profile.md`, and the diff shows what to restore. So check `git status --porcelain -- .claude CLAUDE.md`: uncommitted changes there must be committed or set aside first, so that the diff shows only the upgrade. Ask with one `AskUserQuestion`: upgrade on a new branch `orchestrator-setup-<version>` (recommended), upgrade on the current branch, or cancel. A changelog entry that says the template did not change is a reason to recommend cancel.

## 2. Copy

Run the plugin's installer in the foreground with the target as its argument, adding the overwrite flag only for an approved upgrade:
- Bash: `bash "${CLAUDE_PLUGIN_ROOT}/install.sh" "<target>"` (upgrade: add `--force`).
- PowerShell only (no Bash tool): `powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/install.ps1" -Target "<target>"` (upgrade: add `-Force`). The bypass applies to this one process, so a machine whose policy blocks unsigned scripts still runs the plugin's installer.

Its last lines say how many files were copied and kept. Report a non-zero exit with its output and stop. Ignore its "Next:" line: step 3 runs `/orchestrator-init` now.

## 3. Adapt

Read `<target>/.claude/skills/orchestrator-init/SKILL.md` and carry out its steps in this session. The owner asked for the setup by running this skill, so this is not invoking `/orchestrator-init` on your own. On an upgrade it finds the filled `profile.md` and re-applies it.

At the end, add to its report:
- The skills are project skills, typed without a prefix: `/write-plan`, `/execute-plan`, `/retro`, `/workflow-review`, `/restructure-docs`, `/orchestrator-init`. If they do not appear in the `/` menu, restart Claude Code in the project.
- Upgrade: `git diff -- .claude CLAUDE.md` shows the upgrade together with what it overwrote. Lines the owner or `/workflow-review` had improved show as removed: restore those they want to keep (the ledger in `.claude/orchestrator/ledger.md` names the adopted changes), then commit.
- After a later `claude plugin update orchestrator-setup@orchestrator-setup`, run `/orchestrator-setup:install` again to bring the project up to the new version.
