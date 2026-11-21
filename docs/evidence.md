# Evidence

The numbers behind the rules, measured on the project this setup comes from: a commercial C#/.NET 10 desktop application with seven projects (core library, WPF app, CLI, licensing, two test suites, a dev tool). Every number here comes from Claude Code's own transcripts, run through [`analyze.py`](../template/.claude/skills/workflow-review/analyze.py), the same script `/workflow-review` uses on your project.

**Units** are relative cost: input tokens of the strongest model = 1, with cache writes at 1.25× (5 min) or 2× (1 h), cache reads at 0.1×, output at 5×, and Sonnet at 0.6× and Haiku at 0.2× of Opus. These are price ratios, not money, and they compare across plans.

**Caveat.** These are different features, built over several weeks, not a controlled experiment. The comparison shows where the tokens went and how the shape of the work changed. It doesn't show that the same feature would have cost exactly X without the workflow.

## Before: one long build with ad-hoc subagents

A large feature was built with a main session directing general-purpose subagents and Haiku scouts, before this workflow existed.

| | |
|---|---|
| Agents | main + 24 implementing agents + 25 scouts |
| Turns | 2,767 |
| Total | 87.5M units; hit the usage limit 5 times |
| Split | implementing agents 70%, main session 28%, scouts 1% |
| Cost by token type | cache reads 68%, cache writes 29%, output 2% |
| Cold rewrites | 9.3M tokens of context written again after the cache expired |
| Median implementing agent | 87 turns, peak context 297k, 2.34M units |

Measured in more depth at the time:
- Before its first code edit, a median stage agent had read mostly **shared markdown** (plan, handoff, guides: 53% of what it read). The plan was read 79 times and the 1,900-line handoff 96 times.
- The main session peaked at a **765k** context and re-ran every stage's tests itself.
- About **20% of usage** went into writing, reading and running tests, and most product fixes came from tests against the real external system rather than from unit tests written alongside the code. This is where the *New tests* rule comes from.
- 27 turns rewrote a whole context after a pause longer than the cache lifetime, about **11% of the cost**. Three quarters of that came after pauses of over an hour (usage-limit resets, nights).
- 67% of tool-using turns made a single call. This is where the *batch independent calls* rule comes from.

## With the workflow

| Run | Shape | Total | Split |
|---|---|---:|---|
| Refactor milestone (first run) | 8 stages | 11.9M | implementers 43%, main (planner + orchestrator) 27%, stage reviewers 18%, plan reviewer 10%, scouts 2% |
| Feature, milestone 2 | 7 stages, external-system probe | 18.1M | implementers 40%, main 40%, stage reviewers 13%, plan reviewer 5%, other 3% |
| UI page rebuild | 8 stages + 1 inserted + owner-feedback fix | 26.2M | implementers 44%, main 30%, stage reviewers 20%, plan reviewer 6% |
| UI motion, small | ≤3 stages: one session, no agents | 7.4M | main 90%, plan reviewer 10% |

Per agent, across the three staged runs:

| | median turns | median peak context | median units |
|---|---:|---:|---:|
| Before: implementing agent | 87 | 297k | 2.34M |
| Workflow: stage implementer | 28 | 156k | 0.70M |
| Workflow: stage reviewer | 14.5 | 97k | 0.31M |

A stage with its review costs about 1.0M units where an implementing agent alone cost 2.3M before. Stages are smaller units of work than the old agents' tasks, so read this as "contexts stay small", not as a 57% saving per feature.

## Findings that became rules

Each of these came from a `/workflow-review`-style analysis. The rule is in the skill or agent named.

| Finding (measured) | Rule |
|---|---|
| The first plan review took 2 rounds and found 8 Must fixes, at least 5 of them mechanical (wrong filters, checks that fail once earlier stages land). Every round-2 finding sat in a section the revision had changed. | `/write-plan` step 8 self-check; follow-up review rounds only check the changed sections. |
| Agents read 534k characters of plan through Read, 32% of it outside their own needs. | Decisions under their own `###` headings, stage-local *Facts*, *Decisions used* per stage. |
| A late "check everything" stage found 22 violations in four earlier stages' work and needed an inserted fix stage. | `/write-plan` step 6 *Verify*: checks run in the stage that produces the behaviour. |
| An owner conflict parked as "to confirm" came back after the owner's first real look as a fix stage of 130 turns and 4.5M units, 17% of that build. | `/write-plan` step 2 *Ask, don't park*; *Owner check* after the first visible stage. |
| A probe stage built on an automation path the plan itself called flaky cost three review rounds and a rebuild agent. | `/write-plan` step 4 *No flaky default*. |
| One Should fix and two wording tweaks sent to an implementer whose cache had expired cost three rewrites of about 155k tokens each. | `/execute-plan` step 5: Should fix items go to a warm implementer only, otherwise to the final `FIX` stage. |
| A replay of three runs' subagents on a 1-hour cache: implementers −0.41M, stage reviewers +1.04M, plan reviewers +0.40M, **net +1.1M**. Only 16 turns sat in the 5–60 minute window. | Subagents stay on the 5-minute cache (ledger entry I1). |
| A one-line follow-up 11 hours after an orchestrator finished cost a 321k-token rewrite. | `/execute-plan` *Pauses*: replies after an hour go to a new session. |
| Long renders and test runs polled in the background with sleep: every look was a turn that re-read the agent's whole context. | Foreground commands with long timeouts, narrowed to the stage's scope, in every agent. |
| A language server started before a fresh worktree's first build reported missing packages for the whole session. | `/execute-plan` setup: prepare the worktree before any agent opens a source file. |

## Measure your own

```bash
python .claude/skills/workflow-review/analyze.py runs
python .claude/skills/workflow-review/analyze.py metrics <planning session> <execution session>
python .claude/skills/workflow-review/analyze.py timeline <transcript.jsonl> --grep "Read|test"
python .claude/skills/workflow-review/analyze.py ttl <session>
```

Or just run `/workflow-review`. If you publish your numbers (the metrics tables, not your code), please open an issue: evidence from other stacks is the best way to improve the defaults.
