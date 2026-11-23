---
name: write-plan
description: Create and review a staged implementation plan for a {{PROJECT_NAME}} feature, for later execution by /execute-plan.
argument-hint: "[feature description]"
disable-model-invocation: true
---

Create an implementation plan for: $ARGUMENTS

The plan is executed later by an orchestrator that hands each stage to a fresh agent with no access to this conversation or to the owner's memory. Every decision that matters goes into the plan; implementers make only local choices. `plan-reviewer` is the review: do not add another.

"The owner" below is the person who decides about this project: the user of this session.

## First: does this need the workflow?

Agents pay for themselves only when the work does not fit one session: each starts cold and reads its share of the plan and the code again. If the work is at most 3 stages and needs no measurement of an external system, write no staged plan. Plan it in this session, implement it here or in one fresh session, run the gate, and spawn one `stage-reviewer` in mode `final` at the end only if the change is risky (external behaviour, security, data loss). Tell the user which you chose.

If that one session is a fresh one, or runs in another repository, it starts as cold as an agent: still write the plan file with the template and run steps 9 and 10, but leave out the `Model` and `Review` tags, and say in the header how it runs (which folder, which branch base, commit per stage).

## Steps

1. **Explore.** Read the key files yourself where a decision depends on them. A single lookup is one Grep or LSP call: do it yourself. Use `Explore` only for sweeps across many files or naming variants, with concrete questions, independent questions in one parallel batch.
2. **Design the architecture.** Answer every item of the template's *Architecture* section before staging anything. The goal: no stage implementer has to make a choice that another stage, the user or a reviewer would notice. Ask the user about every decision with more than one reasonable answer and real consequences: options plus your recommendation. Do not ask what the code already answers.
   - Decide what can be known now. What depends on a measurement or on code not yet built becomes an *open decision*: the stage that settles it, the criteria, the options and what each leads to. Never write a guess as a decision.
   - Decisions say what and why. Contracts give exact signatures and shapes. No method bodies: the plan is not the implementation.
   - **Ask, don't park.** When two of the owner's sources disagree (the brief, a memory rule, the code), or a decision changes a value the owner gave, ask now: the options, what each leads to, your recommendation. The plan never carries "to confirm with the owner"; *Risks* holds only what nobody can answer before the code exists. A parked conflict comes back after the owner's first real look as a fix stage that reopens finished stages (measured once at a quarter of a whole build).
   - Values the owner judges by eye or feel (durations, spacing, colours, wording) are decisions with their source, and the plan puts all of them in one named place in the code (one token block, one constants file), so a later "slower, please" is one edit, not a stage.
3. **Carry the owner's rules.** Agents never see memory. Copy every memory rule that bears on this feature into Decisions, with its reason. Check each against the current code and `.claude/rules/` first: a memory is a note from the day it was written. Copy only what still holds, and tell the user about a memory that no longer does.
4. **Measure, don't assume.** <!-- ADAPT: external -->Behaviour the plan relies on that an external system has ({{EXTERNAL_SYSTEMS}}) and the code does not show: measure it now with a temporary probe (deleted afterwards), or make an early probe stage that pins it with a test against the real system before other stages build on it.<!-- /ADAPT --> Record results under *Measured facts* when two or more stages use them, otherwise in the one stage's *Facts*: forms and counts, no private data.
   - **Check what you make.** A probe file, fixture or sample a stage will rely on is checked when it is made, the way that stage will use it: it opens in the real tool, its parts agree, it holds the forms the tests expect. Record the check in *Facts*. A probe you could not check is an open decision, not a fact.
   - **No flaky default.** When the plan knows a tool is unreliable for a job and a fallback exists, the fallback is the stage's path, not a risk to escalate later. (Measured once: a probe stage built on a known-flaky automation path cost three review rounds and a rebuild agent before it switched to the fallback.)
5. **Size.** More than 8 stages: split into milestones that each end mergeable and working; one plan per milestone, the first in detail.
6. **Stage it.** Group the work by concern first, then by the files it touches. A stage is one concern; a concern that makes a small change in many files (a rename, one call added at twelve sites) stays one stage. Concerns that read or edit the same files go into one stage, so no agent reads again what another already read. Size a stage by what its agent must read and understand, not by its file count: one agent finishes it from a fresh start. Every turn re-reads the agent's whole context, so split a concern too large for one agent along file groups that do not overlap, and never merge unrelated concerns to save starts. Define the contracts between stages up front. Stages run in the order listed, except the groups step 7 makes. For each stage fill in the template's fields:
   - *Depends on:* only the stages whose results this stage builds on (a type, a contract, a measured answer): its agent reads their handoff notes. A stage that only has to come later needs no entry.
   - *Decisions used:* the id of every decision this stage's files touch, so its agent reads only those. A stage that owns an open decision names it and is `Model: opus`.
   - *Facts:* the measurements, counts and line ranges only this stage needs. They belong here, not under *Measured facts*, which every agent reads.
   - *Read first:* exact line ranges for files no earlier stage changes; member names for files that do.
   - *Tests:* only the cases CLAUDE.md *New tests* allows, each with its source and inputs → expected result taken from the decision or the measured fact. They are written before the code, so they stay independent of it. No list of every rule, no plumbing.
   - *Same piece of work:* user docs to add or re-check, notices, `.claude/rules/` and `CLAUDE.md` sections.
   - *UI check:* <!-- ADAPT: ui-check -->{{UI_CHECK}}<!-- /ADAPT -->, with the design's values (spacing, sizes, colours per state, texts) read now, so the implementer needs no design source.
   - *Verify:* when the feature has an automated behaviour check (an end-to-end scenario, a render comparison, a test against an external system), the stage that builds or extends the check comes before the stages it checks, and every stage that produces checked behaviour runs its part of the check here. A defect then surfaces in the stage that made it, while that stage's context is loaded; a late "check everything" stage has to reopen other stages' files.
   - *Owner check:* the first stage that makes owner-judged behaviour visible in the real product (motion, layout, wording) ends with a short check for the owner: what to open, what to look at, which decision it confirms. Later stages that build on that behaviour list the stage under *Depends on*. "none" where tests decide.
   - Several stages that apply the same rules to different files (a sweep, a pruning pass, one change across many components) get one shared block with the common steps, edge cases and acceptance criteria. Each stage then gives only what differs.
7. **Group what is independent.** Stages that provably do not touch each other's work may run at the same time, each in its own worktree; this saves time, not tokens, and costs one extra worktree prep (`{{WORKTREE_PREP}}`) per member after the first. The execution has no way to resolve a clash, so independence is settled here, with evidence, or the stages stay sequential. Stages form a group (`P<n>`, written under *Parallel groups*, members listed next to each other under *Stages*) only when all of these hold:
   - **No dependency:** no member lists another under *Depends on*, directly or through a stage between them, and none needs another's handoff note.
   - **Disjoint files:** the files each member changes do not overlap. Count every file, not only *Files owned*: test files, fixtures, *Same piece of work* files (a changelog, a docs page, a `.claude/rules/` file and `CLAUDE.md` are the usual shared ones), and what its tools change as a side effect: lockfiles when it adds a dependency, generated code, snapshots, migrations and their sequence numbers, registrations, index or barrel files, project and solution files. A file two members need goes to one stage before the group, or the members stay sequential.
   - **No shared code:** no member calls, extends, tests or reads under *Read first* code whose signature, visibility or behaviour another member changes. The callers you looked up for the *Quality bar* show this.
   - **Separate runtime:** the members' *Verify* commands can run at the same time on one machine: no shared port, database, external account or state, device, or fixed temp path. A worktree separates files, nothing else.
   - **Nothing decided during the group:** no member owns an open decision or has an *Owner check*: either can change a decision another member is building on.
   - **Worth it:** each member is a full implement-and-review cycle; a `Review: tests` stage of a few lines gains less than the worktree prep costs. At most 3 members per group: the usage limit is shared, and every running agent interrupts the orchestrator.
   A stage that comes after a group starts only when the whole group is merged, so a stage may depend on any member. When grouping would need a stage split or merged differently from what step 6 chose by concern, keep step 6's stages: never trade a clean concern for parallelism.
8. **Write** the plan to `{{PLANS_DIR}}/<feature-slug>/plan.md` with [template.md](template.md) and create `handoffs/` beside it. It lives outside the repo on purpose: a worktree cannot see untracked files, and plans are not committed. Run `git fetch origin` and put `origin/{{DEFAULT_BRANCH}}`'s commit in the header. Agents find what to read by its heading (Grep `^##` lists `##` and `###` with line numbers), then read only those lines:
   - every decision and open decision is its own `### D<n> <title>` / `### O<n> <title>` heading, so an agent can read just the ids its stage lists;
   - each fact is written once, where its reader reads: shared sections hold only what two or more stages need; a stage refers to a decision by id instead of restating it.
9. **Self-check before the review.** Each check below caught a Must fix that a review round had to find in an earlier plan; do them yourself and fix what they find:
   - **Filters:** every test in each stage's test files matches the stage's test filter (a second class or `describe` block in the same file is the usual miss), and a substring filter that also catches other tests is stated where counts depend on it.
   - **Checks after earlier stages:** run each acceptance check and verify command in your head on the tree as it will be when that stage starts, with every earlier stage committed. A diff or count from the plan's base fails once an earlier stage changed those files: use the stage's start commit. A comparison that includes `file:line` fails once lines shift: compare symbols.
   - **No contradictions:** every hint, step and edge case agrees with the decisions it touches. A hint you did not verify says so ("unverified: check").
   - **Nothing pointed to:** every rule an agent needs is written in the plan. "See memory X" or "see plan Y §1" without the rule itself is a gap: agents cannot read memory, and another plan costs them a read.
   - **Numbers and ranges:** spot-check each count, `file:line` and line range against the base with Grep or a range read.
   - **Shell:** every command runs as written in {{SHELL}} from the worktree root. Each command stands alone: a variable, `cd` or function from one tool call is gone in the next.
   - **Expected values:** recompute every expected count, total and row of each test from its inputs and the decisions, not from your picture of the design.
   - **Produced names:** every file name, prefix or test name a check looks for is the one the tool actually produces.
   - **Owner, fixtures, checks:** no "to confirm with the owner" is left (step 2); every probe and fixture was checked when made, and every known fallback is the path (step 4); every checked behaviour is checked in the stage that produces it (step 6).
   - **Parallel groups:** check each group against every rule of step 7 on the stages as now written, by Grep, not from memory: the files of each member (its *Files owned*, test files, *Same piece of work* and side-effect files) against every other member's, each member's *Read first* and the callers of what it changes against the other members' files, each *Verify* command's ports, databases and paths. A member's checks run on the tree with the stages before the group committed and without the other members: a count or diff that includes another member's files fails in its worktree.
10. **Review.** Spawn `plan-reviewer` with the plan path. Apply every Must fix and the Should fix items you agree with. If the verdict was REVISE, send the same reviewer via `SendMessage` the list of sections you changed; it checks those and its findings, not the whole plan again. A fix that adds a file, a doc or a dependency to a member of a parallel group can break the group: check that group against step 7 again and name it among the changed sections. At most 2 rounds; then list what remains for the user.
11. **Hand over.** Summary: stages with their tags and parallel groups, key decisions, open risks, remaining findings. Tell the user to read the plan, then run `/execute-plan {{PLANS_DIR}}/<feature-slug>/plan.md` in a new session.

## Stage tags

- `Model: sonnet` when every choice in the stage that another stage, the user or a reviewer would notice is decided in the plan (its *Decisions used* cover it) and it owns no open decision: wiring, resources, mechanical refactors, encoding listed test cases, code whose design the plan fixes. Local choices (private names, loop shape) stay with the implementer. `Model: opus` when the implementer still has to reason: algorithms, external behaviour, concurrency, unclear existing code, security, an open decision. When unsure, opus.
- `Review: full` for every stage with logic, Sonnet stages included, and for stages others depend on. `Review: tests` only for stages without logic: strings, docs, registrations. When unsure, full.

## Quality bar

- Every file to create or change is named; every new public member has its signature.
- Every caller of a member whose signature, visibility or behaviour changes is in a stage's *Files owned* or named as unaffected.
- Every stage has acceptance criteria a reviewer can check and verification commands that exist, and each passes when the stage is done right (step 9).
- Edge cases are listed per stage, not left for the implementer to discover.
- Reuse is explicit: similar code is pointed to (`file:line`) with "reuse" or "extend".
