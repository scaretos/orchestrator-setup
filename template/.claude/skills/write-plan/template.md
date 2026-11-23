# Plan: <feature name>

- **Base:** origin/{{DEFAULT_BRANCH}} @ <sha from `git rev-parse origin/{{DEFAULT_BRANCH}}` after `git fetch origin`>
- **Milestone:** <1 of N, or "single">

## Goal
<What the user gets when this is done. 2 to 4 sentences.>

## Non-goals
- <Explicitly out of scope>

## Architecture
<Short overview first: the parts of the feature, where each lives, who calls whom, how data flows. Then answer every item; write "not affected" where it does not apply. Each answer is a decision (refer to its D id) or an open decision (its O id).>
<!-- ADAPT: architecture -->
- **Layer:** which layer, package or project each part belongs to, and what each layer may and may not do ({{LAYERS}}).
- **New and changed types:** each with its one responsibility and its home; the public members are under *Contracts*.
- **Entry points:** how the user or another system reaches the feature (UI, CLI flags, API routes, jobs), and what older saved data or clients load as.
- **Data and state:** what is stored (settings, database tables, files, caches), its shape, defaults and migration, when caches are released.
- **Errors:** what the user sees for each failure; one bad input never takes the whole operation down.
- **Concurrency and lifetime:** threads, async boundaries, cancellation, what must not run in parallel.
- **Security and privacy:** what may never reach logs, errors or output; input validation; secrets.
- **Reuse:** existing code this builds on (`file:line`), reused or extended.
- **Shipping:** dependencies and their licences, build or deploy changes, size.
<!-- /ADAPT -->

## Decisions
<Each decision under its own heading, so a stage reads only the ids it lists: what, why in 1 to 2 sentences, and its source. What and why only, never method bodies. Implementers must not revisit these.>

### D1 <short title>
... (source: owner <date> | memory `<name>` | measured | codebase)

## Open decisions
<Only what cannot be known before a stage has measured or built something. Each under its own heading: the question, the stage that decides it, the criteria, the options and what each leads to. The owning stage is `Model: opus`; no stage before it depends on the answer. The orchestrator moves each answer into Decisions.>

### O1 <question>
Decided by S<n>; criteria: ...; if A → ..., if B → ...

## Measured facts
<External behaviour and other facts measured for this plan that two or more stages use: what, how, result. Forms and counts only, no private data. A fact only one stage needs goes into that stage's *Facts*.>

## Contracts
<Exact signatures, types and shapes shared between stages, including error cases and null/empty.>

```
<code>
```

## Conventions to follow
- <pattern> : see `path/File:LINE`

## Verification (whole feature)
- `{{GATE_CMD}}` (the final reviewer runs it)
- <checks the gate leaves out that this feature needs, e.g. a slow or environment-bound suite; the final reviewer runs them after the gate>

## Stages
<Stages run in the order listed.>

### S1: <name>
- **Depends on:** none | S<n> (only stages whose results this one builds on; its agent reads their handoff notes. Coming later is not a dependency.)
- **Model:** opus | sonnet
- **Review:** full | tests
- **Goal:** <one sentence>
- **Decisions used:** D2, D5 (every decision this stage's files touch) | **Open decision owned:** none | O1
- **Files owned:** `path/A` (new), `path/B` (change)
- **Read first:** `path/X:10-60` (why) | `path/Y` member `Z` (changed by an earlier stage)
- **Facts:** <measurements, counts and line ranges only this stage needs>, or "none"
- **Steps:**
  1. ...
- **Edge cases:** ...
- **Tests (pin these, before the code):**
  - `<TestName>`: <inputs> → <expected> (source: external system | real input form | D2 | user-facing promise | bug | contract list | table)
- **Same piece of work:** user docs (add / re-check), notices, rule `.claude/rules/<file>.md` *<heading>*, or "none"
- **UI check:** <what to run and look at; the design's values>, or "none"
- **Owner check:** <what the owner opens in the real product, what to look at, which decision it confirms>, or "none"
- **Acceptance criteria:**
  - [ ] ...
- **Verify:** `{{TEST_CMD}}`; plus this stage's part of the behaviour check, if the feature has one

### S2: <name>
- **Depends on:** S1
...

### S3–S5: <series name> (shared)
<Only for stages that apply the same rules to different files. The common steps, edge cases and acceptance criteria, once. Each stage of the series then gives its fields, with "the shared steps, plus:" for what differs.>

## Risks / open questions
- ...

## Execution log
<Filled in by the orchestrator: worktree path, branch, start commit; per stage: commit, model, review rounds, changed files, decisions made during execution, deferred Should fix items, Learned lines; at the finish: date and PR.>
