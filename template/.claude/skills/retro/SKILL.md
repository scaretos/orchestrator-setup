---
name: retro
description: Run after a finished piece of work, once the gate is green and before the final report or PR, to propose what it taught for the matching .claude/rules/ file or CLAUDE.md. Not in a stage agent.
---

Look back over this session's work while it is still in context, and propose updates to the Claude Code context. Write nothing before the owner agrees.

You run this yourself at the end of a piece of work (CLAUDE.md *The gate*), or the owner types `/retro`. A stage agent never runs it: the `/execute-plan` orchestrator runs it once at the finish, from the *Learned* lines in its log and the reviewers' *Rules out of date*, without reading code. If the work taught nothing new, say so in one line and stop.

This skill improves what agents **know** (facts about the code). `/workflow-review` improves how the workflow **works** (cost, rounds, rework); a finding about the workflow itself goes there, not into a rule file.

1. List what this session had to find out the hard way: a fact that took several searches, a trap that cost a failed build or test, a rule the owner stated, a statement in a rule file that turned out wrong or out of date.
2. For each, name its home:
   - the `.claude/rules/` file whose `paths:` cover the code involved, or a new one if no rule covers it;
   - a folder's `CLAUDE.md` only if it holds for every file in that folder;
   - root `CLAUDE.md` only for a trap that applies to every task;
   - memory for owner facts that are not about the code.
3. Leave out what the code or git history already says, and what mattered only for this task.
4. Show each proposal as a short diff (file, the sentence to add or change, why). Comments in these files follow the same key as code comments: say why, not what.
5. Check that every `paths:` you add or touch hits at least one file (`git ls-files`).
6. Apply only what the owner approves, in the same branch as the work.

## Periodic review

The owner is responsible for the Claude Code setup: the root `CLAUDE.md`, folder `CLAUDE.md` files, `.claude/rules/`, skills, agents, hooks and settings. Review it every 3–6 months and after a new model release: drop rules that compensate for a limit the model or tool no longer has, check that every rule's `paths:` still hit files, and keep the root `CLAUDE.md` to pointers and traps.
