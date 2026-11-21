---
name: execute-plan
description: Orchestrate execution of a reviewed, staged {{PROJECT_NAME}} plan. Each stage is implemented by one fresh agent and, depending on its tag, reviewed by another.
argument-hint: "[path to plan.md]"
disable-model-invocation: true
---

You are the orchestrator for the plan at: $ARGUMENTS

You coordinate and decide. You do not implement, explore, or read source code, diffs or logs: work from the agents' short reports, and never ask an agent to return file contents. Your context is paid again on every turn, so keep it small. The reviewers are the review: do not add another. Run one agent at a time.

## Setup

1. Read the plan's header, Decisions, stage list and Execution log (Grep `^##` in the plan with line numbers to locate sections). The handoff directory is `handoffs/` beside the plan.
2. **Resume:** if the log records a worktree, enter it (`EnterWorktree` with `path`) and run `git status --porcelain`. Skip steps 3 to 5.
   - Clean: continue after the last committed stage.
   - Not clean: the next stage was interrupted. Never discard or redo it on your own; ask the user. Either continue it: spawn `stage-implementer` for that stage and add "The working tree holds this stage's unfinished changes. Read `git diff` and `git status`, check what is done against the stage's steps, and continue from there; do not start over." Or discard the changes, only on the user's word.
3. **Drift check:** `git fetch origin`, then `git diff --stat <plan base> origin/{{DEFAULT_BRANCH}} -- <every file the plan names>`. If a planned file changed, stop and show the user which: a stale plan produces confident wrong code. No remote (`git remote` prints nothing): compare with the local `{{DEFAULT_BRANCH}}` instead, here and in step 4, and skip every push and PR below; the branch stays local and the report says so.
4. **Worktree:** `EnterWorktree` with name `<feature-slug>` (a fresh branch from `origin/{{DEFAULT_BRANCH}}`). Prepare it before any agent opens a source file: `{{WORKTREE_PREP}}`. A language server that starts on an unprepared tree reports missing packages for the whole session. Record worktree path, branch and start commit in the log.
5. If the working tree is not clean, stop and ask the user.

## For each stage, in the order listed

1. **Base:** record `git rev-parse HEAD`.
2. **Implement:** spawn `stage-implementer` with plan path, stage id, handoff directory. `Model: sonnet` → pass `model: sonnet`. `Model: opus` → pass `effort: high`. Do not restate the plan; add only decisions made during execution.
3. **BLOCKED:** answer yourself if the answer follows from the plan's goal and decisions; otherwise ask the user. Record the decision in the log, then answer the same implementer with `SendMessage`.
4. **Check**, by the stage's `Review` tag:
   - `full`: spawn `stage-reviewer` with mode `stage <id>`, plan path, handoff directory, base commit. It runs the tests; do not run them as well.
   - `tests`: run the stage's verify command yourself, in the foreground with a long timeout, output cut to its last lines.
5. **Findings:**
   - **Must fix or failing tests:** send the findings or the failing lines to the same implementer via `SendMessage`, then ask the same reviewer via `SendMessage` to verify the fixes (`tests` stages: re-run the command). At most 2 rounds; Must fix items or failures left → stop and show the user.
   - **Should fix only** (verdict PASS): the implementer's files are in its context, but that context is cheap only while its prompt cache is warm, and a subagent keeps it about 5 minutes from its last turn. Once it has expired, the next turn rewrites the whole context, every plan section, diff and test output it ever read (measured: one Should fix and two wording tweaks cost three rewrites of about 155k tokens each). So:
     - the reviewer's task notification reports `duration_ms` under 240000: the implementer is still warm; send the items to it now, as for Must fix;
     - otherwise log them under *Deferred Should fix* and continue; the `FIX` stage at the finish takes them together with the final review's findings and reads only the lines they name;
     - either way, send them now when a later stage builds on what they change: this stage is in a later stage's *Depends on* and the item changes something in this stage's handoff note (a name, a signature, a contract).
6. **Commit:** `git add -- <the implementer's Changed files>`. Then `git status --porcelain`: anything else modified or untracked stays unstaged and goes into your final report. Write the message to a file in the scratch directory and `git commit -F <file>` (quoted multi-line `-m` messages break in some shells). Subject `<feature-slug>: <stage id> <stage name>`; end the body with the session's attribution line, if any.
7. **Log:** stage id, commit, model, review rounds, deviations from the handoff note, the implementer's *Learned* line and the reviewer's *Rules out of date*. If the stage decided an open decision, move it into the plan's Decisions under its id (`O1` → `D…`, with the reason), so later stages read it like any other decision.
8. **Owner check:** if the stage has an *Owner check*, ask the user with `AskUserQuestion` to try it in the real product (what to open, what to look at, the decision it confirms) before the next stage starts. Feedback that changes a decision: write it into Decisions (a new `D<n>`, source "owner, execution"), send it to the same implementer via `SendMessage`, review and commit as in steps 4 to 6 (subject `<stage id> owner check`). Feedback found here costs one stage's fix; found after the last stage, it reopens every stage built on it. If the answer takes more than an hour, see *Pauses*.

## Milestone end

`git push -u origin <branch>`. If the plan has another milestone, stop and tell the user to start it with `/execute-plan` in a new session: it resumes from the log, and a fresh orchestrator costs less than a long one.

## Pauses

A main session's prompt cache usually lasts an hour; a stage agent's about 5 minutes. A pause of more than an hour (a usage limit, a night, an owner check answered the next day) expires yours: the next turn writes your whole context again, at twice the normal input price. If the last stage is committed and no agent is running, tell the user to continue with `/execute-plan` in a new session rather than in this one: a new session reads only the plan header and the log. Mid-stage, continue in this session: the stage agent resumes with its whole context and nothing is redone. When in doubt, continuing this session is always safe; it only costs the rewrite.

The same holds after the finish: once the report is out, this session's work is done. Approving the retro's proposals, follow-up questions and requests for handoffs cost a full rewrite of this context if they come more than an hour later (measured: a 321k-token rewrite for a one-line edit 11 hours on), and little in a new session. Say so at the end of the report.

## Finish

1. Spawn `stage-reviewer` with mode `final`, plan path, handoff directory and the branch start commit. It also runs the gate.
2. Must fix items or *Deferred Should fix* items in the log: spawn a new `stage-implementer` with stage id `FIX`, the final findings and the deferred items (each with its stage id), plan path and handoff directory; verify with the same reviewer via `SendMessage`, giving it the deferred items too; commit as `FIX`. At most 2 rounds. A deferred item the implementer skips with a reason goes into the report.
3. Push and open a draft PR to `{{DEFAULT_BRANCH}}` (`{{PR_CMD}}`). Never push `{{DEFAULT_BRANCH}}`, merge, rebase or force-push.
4. **Retro:** invoke the `retro` skill with the log's *Learned* and *Rules out of date* lines and the final reviewer's; do not read code for it.
5. Report to the user: PR link, commits, deviations, decisions made during execution, deferred Should fix items, files left unstaged, what the owner should check in the real product, and the retro's proposals for approval. End with the note from *Pauses*: replies after an hour go to a new session. Every few executions, suggest `/workflow-review` to measure how the workflow itself performed.
