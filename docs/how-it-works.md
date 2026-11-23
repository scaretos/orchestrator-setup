# How it works, and why

The workflow's goal is good work on large codebases: every decision made before the code, each stage on the model it needs, every stage reviewed before it's committed. Keeping each context small serves that goal, and it also makes every turn cheaper. This page starts with how a session's context and cost behave, because many rules follow from it, then explains each part of the workflow and the reason behind its rules. The skills and agents state the rules briefly; this is the long form for when you want to change one.

## How context and cost behave

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
- **Stages,** each one concern, with the decisions it uses, the line ranges to read first, the tests to write before the code (inputs, expected result, source), edge cases, acceptance criteria and a verify command. Concerns that touch the same files share a stage. *Why:* a file read by two stages is paid for twice, and a file count says little about the work: a one-line change in twelve files is a small stage, two files the agent must understand in full can be a large one.

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

## Auditing and optimizing the context: `/restructure-docs`

A large codebase often has two problems at once. Documentation written for agents sits in files Claude Code never loads by itself, and some of it no longer matches the implementation. A per-project `X-GUIDE.md`, a `docs/` folder or a 30 KB root `CLAUDE.md` only gets read because an instruction tells an agent to find it, grep its headings and read a range. That happens in every session that needs it.

`/restructure-docs` is a one-time audit, not a text migration. It treats every instruction as a claim to verify. Implementation, tests, build configuration and CI establish observable behavior. Owner decisions and architectural records establish intended behavior. Where the two disagree, it reports the disagreement instead of picking one. It is owner-invoked, and it asks twice:

1. **Before reading anything**, it explains what it changes and what it doesn't, and asks whether to start. In the same question it asks where work costs the most or goes wrong most often. That answer, plus the skill's argument, decides where the audit looks hardest.
2. **After the read-only audit**, it writes the findings, the mapping, proposed skills, enforcement proposals and probe budgets to `audit.md` in the plans folder, outside the repository, and shows a summary. Nothing is written to the repository before the owner approves.

What it looks at:

- **Instruction sources in three groups.**
  - Files it may change: `CLAUDE.md` files, rules, agent-only guides, project skills, and the project facts inside the orchestrator's agents and skills.
  - Files it only reads and reports on: `CLAUDE.local.md`, settings and hooks, the profile, user configuration, auto memory, human docs and open plans.
  - Context that is injected every session, such as hook output and always-on plugin skills, which can contradict `CLAUDE.md`.
- **The change history.** `analyze_docs.py --history` lists the folder sets that change together most often. A recurring set is a kind of change the team makes again and again.
- **The code**, starting where the value is: the owner's answer, the claims in the documents, and those recurring changes. A list of areas (architecture, build and release, composition, contracts, security, traps) is a gap checklist, not a mandate. A convention seen once is a hypothesis; only verified facts become instructions.

How it judges a finding: correct, incorrect or outdated, contradictory, duplicated, unsupported or missing. It also uses three verdicts taken from practice and from Anthropic's guidance on large codebases:

- **procedure:** step-by-step instructions sitting in context files, paid for in every session. They move into a skill.
- **unenforced:** a `must` or `never` that a hook or deny rule could enforce, or a deny rule that matches nothing. It is proposed to the owner; settings are never edited.
- **obsolete workaround:** an instruction that compensates for a model or tool limit that may be gone. The owner decides, because such rules can hold back newer models.

Where things go:

- the root `CLAUDE.md`: pointers, critical traps and essential commands only;
- a folder `CLAUDE.md`: only where content is genuinely folder-wide, such as the folder's test command and traps;
- `.claude/rules/` with `paths:`: facts, constraints and conventions for a topic or feature, which may span folders. Each rule keeps its reason, so a later review can tell whether it still applies;
- **new project skills:** a checklist for each recurring kind of change (every file it touches, with earlier commits to copy from, checked against today's tree), and procedures such as release steps that move out of the root file;
- hooks and deny rules: proposals for the owner.

Human documentation stays. So do the orchestrator-managed sections of the root `CLAUDE.md` and the workflow logic of its skills and agents.

Each placement weighs what it costs in context:

- the root file and rules without `paths:` load in every session;
- a path-scoped rule stays loaded for the rest of the session once a matching file is opened;
- even agents that skip `CLAUDE.md`, like a cheap `Explore` scout, still load path-scoped rules.

So globs are kept narrow. Probe files, picked for each boundary, each shared file and a typical file for each recurring change, get a byte budget agreed with the owner.

Verification is layered:

- `check_rules.py` expands every glob (including brace groups) against `git ls-files`. It fails on dead globs, lists rules without `paths:` as loaded at launch with their size, lists files that load several rules, and flags probes over the budget.
- **Real loading:** a fresh `Explore` agent reads the probe files and reports which rules actually appeared in its context, compared with the simulation. The main session never reads probe files itself, because the rules would stay in its context for the rest of the run.
- `verify_move.py --base <commit>` reads the originals from the base commit, even for files edited in place or already removed. `loss --strict` is a gate for sections moved unchanged. `facts` lists identifiers, numbers and paths that disappeared from rewritten ones.
- An independent Opus reviewer works from `audit.md`, reads the originals with `git show`, and checks claims against the code itself. It is read-only, and the tree is checked to be unchanged afterwards. A finding that crosses the approval boundary goes back to the owner.

`split_docs.py` is an optional aid for moving a correct section without changing it. It refuses to leave a section without a home, and to overwrite an existing file that is not a source.

The work happens on a branch made from the default branch's commit, never on the default branch itself. It ends with a draft PR where the repository supports one. The report lists what the owner should decide (enforcement, obsolete workarounds, contradictions with personal or user configuration, workflow problems for `/workflow-review`) and the open plans that cite removed headings. It also says how to measure the result: `/workflow-review` after the next 2–3 executions compares what agents actually loaded with the probe totals.

If the repository is already well structured, the skill audits it and proposes targeted corrections instead of restructuring.
