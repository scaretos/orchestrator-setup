# How it works, and why

This page explains the cost model the workflow is built on, then each part of the workflow and the reason behind its rules. The skills and agents state the rules briefly; this is the long form for when you want to change one.

## The cost model

Every turn of a Claude Code session sends the whole conversation again: system prompt, tool definitions, `CLAUDE.md`, every file read, every tool result. Prompt caching makes the repeated part cheaper, but not free:

- **Cache read:** about 0.1× the input price, paid on **every turn** for the whole context.
- **Cache write:** 1.25× (5-minute cache) or 2× (1-hour cache), paid for every new token and for the **whole context again** once the cache has expired.
- **Output:** about 5× the input price.

So the cost of a session is roughly *turns × context size × 0.1*, plus a full rewrite after every idle gap longer than the cache lifetime. In the measured builds, cache reads were 42–68% of all cost. Two levers dominate:

1. **Context size per turn.** Whatever an agent reads stays in its context and is paid again on every later turn. Reading a 2,000-line file to find one method costs those 2,000 lines on every turn that follows.
2. **Number of turns.** Every extra turn re-reads everything. Independent calls sent in one message cost one turn, not three.

Model choice multiplies both: Sonnet costs about 0.6× of Opus per token, Haiku about 0.2×.

## Why not one long session?

A long session's context only grows. By the end of a large feature it carries every file read, every test output and every dead end, and pays for all of it on every turn. Contexts of 300k–765k were measured. Splitting the work keeps each context small, but each agent starts cold and has to learn the code again. The workflow resolves that trade-off by having one session (the planner) learn the code once and write down exactly what each stage needs.

That is also why small work gets no agents. With at most 3 stages, the cold starts cost more than the long context they avoid.

## The planner: `/write-plan`

The planner runs in your main session, because it needs you: every decision with more than one reasonable answer and real consequences is asked, with options and a recommendation. It writes:

- **Decisions** (`### D1 …`), each with what, why and its source (you, a memory, the code, a measurement). Implementers never revisit them. *Why:* a choice made by an implementer is invisible until a reviewer or you notice it, and then it costs a fix round or a rebuild.
- **Open decisions** (`### O1 …`): what can only be known after measuring or building something, with the stage that decides it, the criteria and what each answer leads to. *Why:* a guess written as a decision gives an implementer confidence it shouldn't have.
- **Measured facts:** behaviour of external systems, measured now with a probe. *Why:* "the API returns X" is the most common wrong assumption, and every stage built on it inherits the error.
- **Contracts:** exact signatures and shapes between stages, including error and empty cases.
- **Stages,** each one concern of about 6 files at most, with the decisions it uses, the line ranges to read first, the tests to write before the code (inputs, expected result, source), edge cases, acceptance criteria and a verify command.

### Why the plan's layout matters

Agents read the plan by heading: they grep `^##`, then read only the lines of their own sections. So every decision has its own heading, a fact only one stage needs sits in that stage, and nothing is "see elsewhere". Measured before this layout: a third of the plan text agents read was outside their needs.

### The self-check

Before the plan reviewer sees the plan, the planner runs a checklist. Every item on it is a Must fix that a review round once had to find: test filters that miss a class, checks that pass on the plan's base but fail after earlier stages land, expected values that don't recompute from their inputs, commands that don't run in the target shell. A review round costs a fresh Opus context reading the plan and the code; a self-check costs a few greps. This is the general pattern of the improvement loop: **a defect found late becomes a check earlier.**

### The plan reviewer

An Opus agent with no stake in the plan, told to assume it holds at least one wrong assumption. It verifies claims against the code, checks the design and the tags, and reports READY or REVISE with concrete replacement text. A follow-up round checks only the sections the planner changed, because every measured round-2 finding sat in changed sections.

## The orchestrator: `/execute-plan`

It runs in a **new** session and is deliberately blind. It reads the plan's header, decisions, stage list and log, and from then on only agents' reports (at most 15–30 lines each). It never reads code, diffs or logs. *Why:* the orchestrator lives for the whole build, so anything it reads is paid for on every one of its turns until the end. One early orchestrator re-ran every stage's tests itself, peaked at a 765k context and cost about a quarter of the build.

Per stage it:

1. records the base commit;
2. spawns a `stage-implementer` (Sonnet if the plan tags the stage `Model: sonnet`, else Opus);
3. answers BLOCKED questions from the plan, or asks you;
4. spawns a `stage-reviewer`, or just runs the tests for logic-free stages;
5. sends Must fix items back to the **same** implementer and the **same** reviewer (their context already holds the stage), at most 2 rounds;
6. commits with the implementer's list of changed files;
7. logs the stage, including the implementer's *Learned* line and the reviewer's *Rules out of date*;
8. pauses for your **owner check** when the stage made something you judge by eye visible for the first time.

At the end come a final review of the seams between stages, the gate, a `FIX` stage for whatever is left, a draft PR, and `/retro`.

### Why one agent at a time

Parallel implementers on one branch conflict, and parallel reviews of unfinished work review the wrong thing. Sequential stages also let each one read the previous stages' handoff notes, which describe what was actually built, and those win over the plan's prediction.

### Why Sonnet for some stages, never for reviews

Sonnet is the right tool when no judgment is left: wiring, resources, mechanical refactors, code whose design the plan fixes. The plan reviewer checks for each Sonnet stage that no visible choice remains. Reviews stay on Opus because a review's value is the defect it finds before later stages build on it, and missing one costs far more than the review.

### Why the cache rules

A subagent's cache lives about 5 minutes. A review takes 3–9 minutes, so when it ends the implementer's cache has usually expired, and sending it one more small fix rewrites its whole context (130–300k tokens). Hence: Must fix items go back to it anyway, because correctness comes first. Should fix items go back only if the review was quick (the implementer is still warm) or a later stage depends on them; otherwise they wait for the final `FIX` stage, which reads only the lines they name.

Raising the subagent cache to 1 hour sounds like the fix, but a replay of real runs showed it costs more (+1.1M units net): every cache write gets more expensive, and few turns sit in the 5–60 minute window it would rescue.

## The implementer and the reviewer

**`stage-implementer`** reads only its stage's sections of the plan, its dependencies' handoff notes and its *Read first* ranges. It writes the plan's tests first and watches them fail for the right reason, then implements, runs the verify command and writes a handoff note of at most 30 lines. It stops with BLOCKED instead of guessing when the plan is ambiguous or a choice would be visible to others.

**`stage-reviewer`** reads the stage diff and enough context around it, runs the verify command once, and checks correctness, plan fidelity, tests (would each one fail if the code were wrong?), docs, debt and privacy. Its final mode reviews the seams: contracts on both sides, duplicated helpers across stages, consistent naming and errors, and the gate.

## Tests

"Write tests" is the instruction that costs the most tokens for the least protection, when the tests are written from the same understanding as the code. In the measured pre-workflow build, about 20% of usage went into tests, while most product fixes came from tests against the real external system. So a new test needs an **independent oracle**: a real system, a real input's form, an owner decision, a promise in the docs, a fixed bug, a contract list, or a table of cases. The plan names each test with its source and its expected values, written before the code.

## The knowledge loop: `/retro`

Implementers end with a *Learned* line: a fact or trap that cost them searches or a failed run and that neither the plan nor a rule file had. Reviewers report rule statements the code now contradicts. At the finish, `/retro` proposes where each belongs:

- a `.claude/rules/<topic>.md` file with `paths:` frontmatter, which Claude Code loads automatically when an agent reads or edits a matching file, so the knowledge costs nothing until it's relevant;
- a folder's `CLAUDE.md` only for what holds for every file in that folder;
- the root `CLAUDE.md` only for traps that apply to every task, since it is read on every turn of every agent.

## The workflow loop: `/workflow-review`

`/retro` can't see what the workflow costs. `/workflow-review` can:

1. `analyze.py runs` lists sessions that ran `/write-plan` or `/execute-plan`, grouped by plan, across worktree transcript folders.
2. `analyze.py metrics` measures every agent from its transcript: turns, units, token split, peak context, cold rewrites and the gaps behind them, rounds and verdicts, duplicate reads, rule files loaded, errors, and command classes (build, test, gate, polling).
3. One Sonnet `workflow-analyst` per run investigates the expensive parts with `analyze.py timeline` and returns referenced evidence, never strategy.
4. The main session consolidates the evidence into ranked proposals (exact diff, expected saving, quality risk, verify metric) and checks the ledger: did the last review's changes deliver, and was this idea already rejected?
5. You choose. Adopted changes and rejections both go into the ledger, so the next review starts from what is already known.

Research runs on Sonnet because extracting evidence from transcripts needs care, not judgment. The judgment (what to change, and whether it risks quality) stays with the strongest model, which holds only the short reports.

## Adapting: `/orchestrator-init`

The skills and agents ship with placeholders (`{{TEST_CMD}}`) and ADAPT blocks (the plan template's architecture checklist, the agents' *This machine* traps). `/orchestrator-init` fills them from your build files, CI and environment, and records the values in `.claude/orchestrator/profile.md`. Literal, project-specific instructions matter: an agent told "run the tests" searches for how; an agent given `npm test -- -t "<filter>" 2>&1 | tail -5` doesn't.
