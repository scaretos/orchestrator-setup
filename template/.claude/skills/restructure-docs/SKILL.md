---
name: restructure-docs
description: Audit and optimize a project's Claude Code knowledge base once, after /orchestrator-init. Verifies root and nested CLAUDE.md files, .claude/rules/, agent-only guides and the factual context in agents and skills against implementation, tests, build configuration, CI and owner decisions; corrects, consolidates, removes and adds knowledge with evidence; moves procedures into skills; proposes hooks and deny rules where an instruction should be enforced. Owner-invoked only; writes nothing before the audit and the mapping are approved.
argument-hint: "[areas or paths to focus on; default: the whole project]"
disable-model-invocation: true
---

Audit and optimize this repository's Claude Code knowledge base. The aim is the one every later session pays for: agents that know where to look and what not to break, without searching guides by hand or rediscovering the same facts.

Two kinds of truth stay separate. Implementation, tests, build configuration and CI establish **observable behavior**; explicit owner decisions and architectural records establish **intended behavior**. Existing documentation is historical context, not automatic authority: every instruction is a claim to verify, not text to preserve. When observable and intended behavior disagree, report the discrepancy; do not silently pick one.

This runs once. `/retro` maintains the result from real work; `/workflow-review` measures and improves the workflow. "The owner" is the user of this session; you never start this skill yourself.

Focus: `$ARGUMENTS` (empty means the whole project).

## 0. Warn, ask, scope

Before reading any file, send this message, filled in:

> **What this does:** audits every Claude Code instruction against the code, tests, build configuration and CI, then corrects, consolidates, removes and adds knowledge, moves procedures into skills, and restructures context so it loads by path. It may rewrite the root and folder `CLAUDE.md` files and `.claude/rules/`, add project skills, and remove agent-only guides once they are replaced. All on a branch.
> **What it does not change:** product code, tests, settings, hooks, CI, `CLAUDE.local.md`, your user configuration and memory, human documentation, and the workflow logic of the orchestrator's skills and agents. Where a hook, a deny rule or a workflow change would help, it proposes one for you to decide.
> **The risk:** a rewrite can lose a fact; a `paths:` glob that is too broad loads text into unrelated work, one too narrow leaves a fact unloaded. Every removal and correction is backed by evidence and shown to you before it is applied.
> **Two approvals:** now, for a read-only audit; later, for the findings and the plan, before anything is written.

Then one `AskUserQuestion` call with two questions:

1. **Start the read-only audit** (recommended) / **Cancel**.
2. **Where does work cost the most or go wrong most often?** Options such as *one kind of feature or change*, *finding the right docs or code*, *build, test or release*, *don't know: audit everything*. The owner's answer, together with `$ARGUMENTS`, decides where the audit looks first and hardest.

If the owner cancels or hesitates, stop and change nothing.

## 1. Inventory (read-only)

Sort every instruction source into three buckets:

1. **May change, after approval:** the root `CLAUDE.md`, every folder `CLAUDE.md`, documents whose only consumer is agents, `.claude/rules/`, and the project's own skills and agents. In the orchestrator's skills and agents (`write-plan`, `execute-plan`, `retro`, `workflow-review`, `orchestrator-init`, this skill, and the agents they use), only project-specific factual context, such as a wrong path or command; never workflow logic, stage contracts, permissions or responsibilities.
2. **Read and report, never change:** `CLAUDE.local.md` (personal and usually gitignored: an edit would escape the branch, the PR and git), `.claude/settings*.json` (permissions, deny rules, hooks), `.claude/orchestrator/profile.md` (`/orchestrator-init` re-applies it), user-level `~/.claude/CLAUDE.md` and settings, the project's auto memory (`MEMORY.md` and its notes), human documentation, and open plans in `{{PLANS_DIR}}`.
3. **Injected every session:** hook output (a `SessionStart` or `UserPromptSubmit` hook that adds context), and the descriptions of always-on plugin and MCP skills. These instruct the model too, and they can contradict `CLAUDE.md`. Read the hooks in the settings files to see what they inject.

Preserve the orchestrator-managed sections in the root `CLAUDE.md`: the headings in `.claude/orchestrator/claude-md-sections.md`, `ADAPT` blocks and the workflow instructions.

Classify every document before judging it:

| Class | Examples | Treatment |
|---|---|---|
| **Agent-only** | A guide whose only consumer is agents, confirmed by references and ownership, not by a `*-GUIDE.md` filename | Audit, then replace and remove |
| **Human** | `README.md`, user or contributor documentation | Keep and leave authoritative |
| **Mixed** | A document people read that also carries facts agents need | Keep; extract only the agent-facing facts, with the owner's OK |
| **Generated or vendored** | `node_modules/`, `vendor/`, build output, generated docs | Check whether an instruction references it; never rewrite it |

Measure each document and the change history:

```bash
{{PYTHON}} .claude/skills/restructure-docs/analyze_docs.py --repo . <documents>
{{PYTHON}} .claude/skills/restructure-docs/analyze_docs.py --repo . <document> --section "<heading>"
{{PYTHON}} .claude/skills/restructure-docs/analyze_docs.py --repo . --history 6
```

The first prints every section's size and the repository files its backticked names resolve to; the second lists one large section's paragraphs; the third lists the folder sets that change together most often, with example commits. A folder set that recurs is a kind of change the team makes again and again: the best candidate for a checklist skill (step 3).

Record for each document its size, who reads it and how (loaded automatically, or only because an instruction says to read it) and when it last changed (`git log -1 --format=%cs -- <path>`; `untracked` if it is not tracked). A guide read by hand costs turns in every session that needs it; a rule loaded for half the repository costs context in every session that does not.

Note, without resolving them yet: duplicated facts, contradictions, instructions that look outdated, unsupported claims, missing knowledge, `must`/`never` instructions nothing enforces, and deny rules that may match nothing.

## 2. Investigate (read-only)

Start where the value is: the owner's answer and `$ARGUMENTS`, the claims the documents make, and the recurring kinds of change from `--history`. Then check this list for gaps; it is a checklist, not a mandate to describe each area:

| Area | What to capture |
|---|---|
| Architecture | Components, layers, boundaries, entry points, data flow |
| Build, test, release | Commands per folder, filters, slow or flaky areas, release-only steps |
| Conventions | Patterns confirmed across files, naming, layering |
| Composition | Where services, routes, registrations or switches must be added |
| Contracts | Names or attributes that serialization, reflection, trimming or obfuscation depend on |
| Errors and logging | Patterns, places errors are swallowed |
| Security and data | Trust boundaries, secrets, schemas, migrations, invariants |
| Integrations and environment | External services, local substitutes, required tools and variables |
| Constraints and traps | Platform quirks, known pitfalls; a workaround is not an intended design |

Investigate cheaply: start from build files, CI, entry points, tests and the folders with the most cross-references; use `Explore` for breadth and LSP `documentSymbol`/`findReferences` when available; for a workflow, follow the call path from entry point to persistence. Read enough to confirm a pattern across layers, not every file. Stop an area when its claims are checked and no high-value gap is left.

**Evidence rule.** A convention seen in one file is a hypothesis. Mark each finding **verified** (seen in code, tests, configuration, a command, or stated by the owner), **assumption** or **unknown**, and record the evidence (paths, commands). Only verified facts become instructions; assumptions go to the owner; unknown stays out.

### Value over completeness

| Priority | Knowledge |
|---|---|
| **High** | Architectural boundaries, critical invariants, non-obvious dependencies, dangerous pitfalls, the files a recurring change must touch |
| **Medium** | Build and test commands per folder, conventions, integration behavior, important configuration |
| **Low** | What an agent finds in seconds: obvious structure, generic language or framework knowledge |

Add knowledge only when its expected value exceeds its context cost. A project that obviously uses TypeScript needs no note saying so; a package that must not be minified because a plugin loader reads its export names does.

Know what each place costs:

- The root `CLAUDE.md` and rules without `paths:` load at launch in every session, and in every subagent that does not skip `CLAUDE.md`.
- A folder `CLAUDE.md` or a path-scoped rule loads when a matching file is read or edited, and then **stays for the rest of the session**. A long session that touches many areas collects many rules.
- Agents set to skip `CLAUDE.md`, such as a cheap `Explore` scout, **still load path-scoped rules** for the files they read. There is no setting to exclude rules per agent; a narrow glob is the only lever.
- The template's `explore.md` already holds the codebase map (*Where things are*). Do not write a second one into the root `CLAUDE.md`.

## 3. Findings, destinations, approval

Build one findings table:

| Claim or gap | Where | Doc class | Content class | Evidence | Status | Verdict | Action |
|---|---|---|---|---|---|---|---|

`Content class`: architecture, command, convention, constraint, workflow, procedure, trap, navigation, reference. `Status`: verified, assumption, unknown.

| Verdict | Meaning | Usual action |
|---|---|---|
| correct | Matches the evidence | keep (and maybe move) |
| incorrect / outdated | The evidence says otherwise | correct, with evidence |
| contradictory | Two sources, or observable and intended behavior, disagree | flag and ask the owner |
| duplicated | The same fact in several places | consolidate to one home |
| unsupported | No evidence either way | flag; never state as fact |
| missing | A high-value fact no file holds | add, with evidence |
| obsolete workaround | An instruction that compensates for a model or tool limit that may be gone, such as "split every refactor into single-file changes" | ask the owner; newer models can be held back by it |
| unenforced | A `must`/`never` a hook or deny rule could enforce, or a deny rule that matches nothing | propose enforcement (report only) |
| procedure | Step-by-step instructions for one kind of task, sitting in context files | move into a skill |

A removal needs a justification: wrong, redundant, irrelevant or replaced. An addition needs support from the code, a record or the owner; never invent one.

Knowledge, procedures and workflow constraints are different things: "Orders are persisted through the outbox table" is knowledge; "to add a payment provider, touch these six files" is a procedure; "the orchestrator never reads source files" is a workflow constraint.

Decide where each surviving or new fact belongs:

| Content | Destination |
|---|---|
| Pointers, critical traps, essential commands, universal context | Root `CLAUDE.md`: pointers and critical traps only; everything else drifts into noise |
| Instructions and traps true for every file in one folder, including its test command and filter | That folder's `CLAUDE.md` (aim for at most ~4 KB) |
| Technical facts, constraints and conventions for a topic or feature | `.claude/rules/<topic>.md` with `paths:` |
| A procedure or checklist for one kind of task | A new project skill, `.claude/skills/<name>/SKILL.md` |
| An instruction that must always hold | A hook or deny rule: proposed to the owner, not written |
| Project facts inside the orchestrator's skills and agents | Correct in place; workflow problems go to `/workflow-review` |
| Human documentation | Stays; agent-facing facts are copied into rules with the owner's OK |

**New skills.** Two kinds pay off most:

- A **checklist for a recurring change** (from `--history`): every file that kind of change touches, in order, with one or two earlier commits to copy from (`git show <commit> -- <file>`). Verify it against the current tree: an older exemplar commit can predate a switch, registration or test list that every new change now needs. It saves the discovery phase of every future change of that kind.
- A **procedure moved out of context**: release, publish or migration steps that sit in the root `CLAUDE.md` and are paid for in every session.

Each new skill gets a `description` that says what it does and when to use it. Set `disable-model-invocation: true` when it is slow, costly or the owner's call (a release); then the root `CLAUDE.md` says when Claude should *suggest* it, not run it. Otherwise Claude may start it itself when the task matches.

**Placement rules.**

- A folder `CLAUDE.md` only where there is meaningful folder-wide content. Do not create one per folder for structure's sake.
- A rule covers one topic or feature, and may span folders: the library part, the UI part and the tests that pin it. It must read correctly as the only file loaded: no "see above" into another file.
- Each fact has one home. A critical invariant may be restated for a consumer the loading model cannot otherwise reach; keep one canonical version.
- Keep each rule's reason (why it exists, what broke). Without it, the next review cannot tell whether a constraint or workaround still applies.
- The orchestrator works from plans and reports and does not read code, so path-scoped rules never reach it: coordination facts go in the root `CLAUDE.md`, the profile or the plan.

Choose `paths:` from the references the analyser found. Check both directions: every file the fact matters for is covered, and unrelated files do not pull it in. Prefer the narrowest set; use forward slashes as `git ls-files` prints them; brace groups such as `src/**/*.{ts,tsx}` are allowed. A shared file that loads several rules is acceptable when listed in the report.

**Probes and budget.** Pick probe files: one per project or rule boundary, the shared files that load the most, a typical file for the recurring change, and one that should load no rule. For each, record what an agent pays **now** (the `CLAUDE.md` files above it plus the guides it is told to read) and agree a budget with the owner for what it may load afterwards.

**The approval package.** Write it to `{{PLANS_DIR}}/restructure-docs/<date>/audit.md`, outside the repository, so it survives a compaction or a new session and the reviewer can read it: the owner's answer and scope, the findings table, the mapping table below, new skills, enforcement proposals, probes with before-totals and budget, and open questions.

| Item | Doc class | Content class | Destination (with `paths:`) | Consumer | Evidence | Change | Original |
|---|---|---|---|---|---|---|---|

`Change`: corrected, added, kept, consolidated, removed, moved, flagged. `Original`: stays, removed after replacement, or human/mixed and stays.

In the chat, show a short summary: verdict counts, the ten most important changes, new skills, enforcement proposals, before/after size totals, open questions, and the path to `audit.md`. Then ask with `AskUserQuestion`: **Apply the audit on a branch** (recommended), **Change the plan**, or **Cancel**. Nothing is written before **Apply**; after **Change**, revise `audit.md` and ask again.

**The approval boundary.** Every material change must trace to an approved row. Inside the boundary, no new approval is needed:

| Change | New approval? |
|---|---|
| Grammar, clarity, formatting, rewording that keeps the meaning | No |
| Correcting a factual error the approval covers | No |
| Narrowing a glob, or splitting a rule in two, when the probes show every intended file still loads it | No |
| Adding a fact or a skill, or removing a fact not listed for removal | Yes |
| Moving content to another destination, or widening a rule's coverage | Yes |
| Merging rules | Yes |

## 4. Branch and apply

- `git status --porcelain` must be clean, or ask the owner what to do. Never mix this work with anything else.
- Find the default branch: `git symbolic-ref --short refs/remotes/origin/HEAD` (strip `origin/`), else `{{DEFAULT_BRANCH}}`. With a remote, `git fetch origin` and take `git rev-parse origin/<default>` as the base; without one, `git rev-parse <default>`.
- Always branch from that base, not from whatever branch is checked out: `git switch -c docs/context-audit-<date> <base>`, or a worktree from it if the owner works in parallel. Confirm `git branch --show-current` is not the default branch and `git rev-parse HEAD` equals the base. Write the base into `audit.md`. If either check fails, stop and ask.

Write the result:

- Correct, consolidate, remove, move and add content according to `audit.md`, with Edit.
- For a section that is already correct and only needs a new home, `split_docs.py` can move it verbatim (dry run, then `--write`); keep its config under `{{PLANS_DIR}}/restructure-docs/<date>/`:
  ```bash
  {{PYTHON}} .claude/skills/restructure-docs/split_docs.py <config.json> --repo .
  {{PYTHON}} .claude/skills/restructure-docs/split_docs.py <config.json> --repo . --write
  ```
  It refuses to leave a non-empty section without a home or an explicit `drop`, and to replace an existing file that is not a source.
- Create the approved skills. When a procedure leaves the root `CLAUDE.md`, leave a one-line pointer saying when it applies.
- Update references in Claude Code files: every `CLAUDE.md`, rules, skills and agents. References elsewhere change only when a removed agent-only document makes them invalid, and only with approval.
- Remove replaced agent-only guides with `git rm`. The verification reads the originals from the base commit.
- Check that git does not ignore the new files: `git check-ignore -v <new files>`. If `.gitignore` hides `.claude/rules/` or a folder `CLAUDE.md`, add the narrow exception (`!/.claude/rules/`); `.gitignore` is the only non-documentation file this skill edits. An ignored rule never reaches another machine or worktree.

The scripts accept `/` or `\` in paths. In PowerShell, list files explicitly: it does not expand `*` or `**` for them.

## 5. Verify

1. **Facts.** Check every instruction that remains against the code, tests, configuration or a command: paths, type names, commands, contracts, workflows. A sentence that survived because it was in the old document is not verified.
2. **Simulated coverage.**
   ```bash
   {{PYTHON}} .claude/skills/restructure-docs/check_rules.py --repo .
   {{PYTHON}} .claude/skills/restructure-docs/check_rules.py --repo . --shared
   {{PYTHON}} .claude/skills/restructure-docs/check_rules.py --repo . --budget <bytes> <probe files>
   ```
   The first fails on a dead glob or an empty `paths:` and lists rules without `paths:` as loaded at launch, with their size. The second lists files that load several rules. The third prints what each probe loads and flags a probe over the budget.
3. **Real loading.** Simulation is not proof. Spawn one fresh `Explore` agent with the probe list: "Read the first 20 lines of each file. For each, list the `.claude/rules/` and `CLAUDE.md` files whose content appeared in your context after that read." Compare with the simulation and report any difference. Do not read the probe files in this session yourself: every rule they load would stay in your context for the rest of the run. The agent loads rules from the working tree, so run it in the tree that holds the new files.
4. **Consistency.** No two files contradict each other; the root file holds pointers, commands, universal context and critical traps.
5. **Knowledge preservation.** Compare old and new at the level of facts, decisions, invariants, workflows, measurements and traps, with the originals from the base commit:
   ```bash
   {{PYTHON}} .claude/skills/restructure-docs/verify_move.py loss --strict --base <base> --old <moved docs> --new <new files>
   {{PYTHON}} .claude/skills/restructure-docs/verify_move.py facts --base <base> --old <old docs> --new <new files>
   ```
   `loss --strict` is a gate only for sections moved unchanged. For rewritten ones, `facts` lists identifiers, numbers, paths and quoted names that disappeared: restore each, or justify it as wrong, redundant or irrelevant. Neither proves that meaning survived; the reviewer checks that.
6. **Readability.** Each rule makes sense as the only file loaded; each new skill's description says when it applies.
7. **References and tracking.** Every reference to a removed or renamed file is repointed; every new file is tracked.

## 6. Independent review

Commit the applied changes first, so the review starts from a clean tree. Then, for a first audit or more than about 15 changed files, spawn one fresh `general-purpose` agent with `model: opus`. It has no knowledge of your reasoning. It is read-only by instruction: tell it to report findings with file locations and evidence and to edit nothing. Afterwards, `git status --porcelain` must still be clean; if it is not, report what it changed and restore those files.

Give it the path to `audit.md`, the base commit, the list of changed files, and the verification output. Require it to inspect the implementation, tests and configuration itself and to read the originals with `git show <base>:<path>`; it must not trust your summary. It checks:

- every stated path, type, command, contract and workflow against the code;
- that disagreements between observable and intended behavior are reported, not silently resolved;
- placement (folder-wide content in a folder `CLAUDE.md`, the rest in rules), `paths:` coverage in both directions, and consumer fit, including the orchestrator, which reads no code;
- that each new checklist skill names every file a change of its kind touches today;
- that decisions, invariants, measurements and traps survived, were corrected with evidence, or were removed with a justification;
- high-value knowledge that is still missing, and contradictions or stale claims that remain.

Evaluate each finding yourself. Apply what stays inside the approval boundary; anything that crosses it needs the owner's approval first. Re-run the affected checks, then commit.

## 7. Gate, commit, report

Run `{{GATE_CMD}}` when it is cheap enough to justify; documentation-only changes do not need expensive integration or deployment tests unless those tests read the changed files. If the gate is skipped, say why. A failure that already exists on the default branch is reported, not fixed here.

Commit on the branch. With a remote and the tooling, push and open a draft PR (`{{PR_CMD}}`); otherwise the branch stays local, and the report says so. Never merge.

Report, in this order:

- **Audit:** the verdict counts; what was corrected, consolidated, removed, moved and added, with evidence; every disagreement between observable and intended behavior.
- **Structure:** old document or section → new file, with sizes; totals before and after; the number of rules (with and without `paths:`), folder `CLAUDE.md` files and new skills.
- **Loading:** dead globs, shared files, each probe's total before and after against the budget, and whether the real-loading check matched the simulation.
- **For the owner to decide:** enforcement proposals (hook or deny rule, with the instruction it enforces and the exact setting), obsolete workarounds, workflow problems for `/workflow-review`, contradictions with `CLAUDE.local.md`, user configuration, memory or injected hook context, and unresolved questions.
- **Review:** what the reviewer found, what was applied, what still needs the owner.
- **Gate and branch:** the gate result or why it was skipped; branch or PR.
- **After the merge:** the new context takes effect in new sessions on a branch that contains it; worktrees made earlier keep the old docs, and open plans in `{{PLANS_DIR}}` that cite removed headings must be updated (list them). Run `/workflow-review` after the next 2–3 executions to measure what agents actually loaded and their turns before the first edit, against the probe totals; `/retro` keeps the rules current; review the setup every 3–6 months or after a major model release.

## Rules

- **Verified facts only.** Never invent an architectural fact, convention or requirement. Unverifiable information is flagged, not stated.
- **Knowledge preservation, not verbatim preservation.** Correct information survives; incorrect is corrected with evidence; redundant is consolidated; irrelevant is removed with a justification.
- **Read, don't change,** settings, hooks, `CLAUDE.local.md`, user configuration, memory and the orchestrator's workflow logic. Propose instead.
- **Never on the default branch,** and never without the two approvals.
- **Protect your own context.** Use `Explore` and the scripts for breadth; never read probe files yourself.
- **If the repository is already well structured,** do not restructure it: audit it and propose targeted corrections.
