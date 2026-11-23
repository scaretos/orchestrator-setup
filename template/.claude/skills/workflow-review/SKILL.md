---
name: workflow-review
description: Measure the most recent /write-plan and /execute-plan runs from their transcripts and propose changes to the workflow itself (skills, agents, plan template, CLAUDE.md workflow sections) that cut token usage without costing correctness. Investigates and proposes; changes nothing without the owner's OK.
argument-hint: "[plan slugs to review, or a number of recent runs; default 3]"
disable-model-invocation: true
---

Review the workflow's own performance for: $ARGUMENTS (empty: the 3 most recent finished executions).

The goal is the lowest practical usage **without** lowering code quality, precision or reliability. Never trade correctness for tokens, and measure it too: **escaped defects** are bugs fixed after a run finished, in code the run built, that one of its checks should have caught. Count the main session and every subagent together: delegation does not save tokens by itself, since every agent starts cold and reads its share again.

This is the workflow's improvement loop. `/retro` improves what agents *know* about the code; this skill improves how the workflow *works*: where the tokens went, which rounds and rewrites were avoidable, which rules paid off and which did not. The ledger at `.claude/orchestrator/ledger.md` is its memory: what earlier reviews changed, what they expected, and what the owner rejected and why.

## Rules

- Investigation first. Do not change any file before the owner approves a proposal; never touch source code or existing plans, at any point.
- Measured beats estimated. Every number you report says which it is; every estimate says how it was computed.
- Do not read transcripts yourself: the analyser and the analysts do. Your context stays small, because you hold the whole review.
- A proposal that removes a review, a test or a check needs evidence that it found nothing over several runs **and** that a cheaper check covers the same failure. Bugs caught by a review are value, not cost.
- Prefer removing waste (idle cache expiry, re-reads, rounds caused by plan defects, polling, oversized outputs) over removing safety.
- A defect a reviewer had to catch, that the planner could have caught, moves left: into the `/write-plan` self-check, not into a longer review.
- A rejected proposal in the ledger comes back only with new evidence that answers the owner's reason.

## Steps

1. **Read** `.claude/orchestrator/ledger.md` and `.claude/orchestrator/profile.md` (the Python command and the plans folder are there).
2. **Pick the runs.** `{{PYTHON}} .claude/skills/workflow-review/analyze.py runs` lists the workflow sessions grouped by plan, newest first, with each plan's execution-log state. Take the runs the argument names, or the most recent finished ones (a log with a finish entry or a PR). Include each run's planning session. Also take the previous `/workflow-review` session if there is one: this skill is part of the workflow under review. Tell the user the selection in one line and go on. Fewer than 2 executions since the last review: say that the sample is thin, and continue only if the user asked for this review.
3. **Measure.** For each run: `{{PYTHON}} .claude/skills/workflow-review/analyze.py metrics <planning session> <execution sessions> > <scratch>/m_<slug>.md`. Read the role table and the per-agent table of each (they are short). Run `analyze.py ttl <sessions>` only when a question about cache lifetime comes up.
4. **Research.** Spawn one `workflow-analyst` per run, all in one message (they are read-only and independent), at most 3. Give each: the plan path, the session ids, its metrics file, `analyze.py`'s path, the ledger entries whose effect this run can show, and the questions below. Give the analyst of the newest run also the plan paths of the runs the last review covered, for the escaped-defects question only: defects surface over weeks, so older runs show more. Add nothing else: they find their own evidence.
   - token use, context growth and turns per agent; where the peak contexts came from;
   - planning and implementation efficiency: turns before the first edit, reads of plan and shared markdown, re-reads;
   - tool calls and redundant operations: duplicate reads, single-call turns, oversized tool results, polling;
   - subagent use and communication overhead: rounds, follow-ups, agents that did not pay for themselves;
   - repeated research and unnecessary context loading;
   - errors, rework and verification overhead: failed commands, fix rounds and their root cause (plan defect, instruction gap, environment, model);
   - cold cache rewrites and the idle gaps that caused them;
   - quality: what each review caught, and whether a cheaper or earlier check would have caught it;
   - escaped defects: fixes since the run finished to code it built, and which check missed each.
5. **Check earlier changes.** For each ledger entry adopted since the last review, compare its *Verify* metric with its *Baseline*, using the metrics and the analysts' ledger checks. Mark it confirmed, no effect or regressed; a change whose metric improved while escaped defects rose is regressed. No effect or regressed: propose to rework or revert it.
6. **Consolidate.** Group the analysts' findings that share a cause, across runs. A pattern seen in one run only is a candidate, not a finding: say so. For each proposal:
   - **Problem:** what happened, with evidence (run, agent, turn range; measured or estimated).
   - **Change:** the exact file and the replacement text, as a short diff. Workflow files only: `.claude/skills/write-plan/`, `execute-plan/`, `retro/`, `workflow-review/`, `.claude/agents/`, `.claude/orchestrator/`, the workflow sections of `CLAUDE.md`, and settings.
   - **Expected saving:** in units and as a share of a typical run, with how you estimated it.
   - **Effort**, and **quality risk**: what could get worse, and which check would catch it.
   - **Verify:** the metric the next review compares, and its value now (the baseline).
   Rank by expected saving × confidence, discounted by quality risk. Keep proposals small and independent, so the owner can take a subset.
7. **Present** to the owner: one table (rank, proposal, expected saving, risk, confidence), the earlier changes' results, then each proposal's details. Ask with `AskUserQuestion` (multi-select) which to apply; with more than 4 proposals, ask about the top 4 and list the rest for a typed answer.
8. **Apply** the approved proposals in a worktree branch (`EnterWorktree`), with Edit. Settings changes only with their own explicit OK.
9. **Ledger.** Add a row to *Reviews* (date, runs, total units, units per stage, escaped defects, the main finding). Add each proposal under *Changes* (adopted) or *Rejected* (with the owner's reason in their words), with its evidence, baseline, expected effect and verify metric. Fill *Result* of the earlier entries you checked in step 5.
10. **Finish.** Commit the workflow files and the ledger, push, open a draft PR (`{{PR_CMD}}`). Report: what was measured (totals per run and role), what earlier changes did, what was applied, what was rejected or deferred. Suggest the next review after 2–3 more executions.
