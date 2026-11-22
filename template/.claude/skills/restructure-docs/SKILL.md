---
name: restructure-docs
description: Audit, validate and optimize a project's Claude Code knowledge base: root and nested CLAUDE.md files, .claude/rules/, agents and skills. Compares implementation, tests, build configuration and CI with owner decisions and architectural records; finds incorrect, outdated, duplicated and missing instructions; reports disagreements instead of guessing; restructures context by consumer, value and path. Owner-invoked only; writes nothing before the audit and the mapping are approved.
argument-hint: "[areas or paths; default: whole project]"
disable-model-invocation: true
---

Audit and optimize this repository's Claude Code knowledge base. Implementation, tests, build configuration and CI establish observable behavior; explicit owner decisions and architectural records establish intended behavior and design constraints. Existing documentation is historical context, not automatic authority. When the two disagree, report the discrepancy instead of silently treating either as correct. Every instruction is a claim to verify, not text to preserve. The result must let the planner, orchestrator, implementers, reviewers and Explore agent work without rediscovering the same project facts.

This is a one-time optimization after `/orchestrator-init`. `/retro` maintains the result from real work; `/workflow-review` improves the workflow itself. Do not turn this skill into either.

"The owner" is the user of this session. The owner runs this skill; you never start it yourself.

## 0. Warn first, then ask permission

Before reading files, source or configuration, send one message covering:

- **What this does:** audits every Claude Code instruction, reads implementation, tests, build configuration, CI and explicit architectural records, then corrects, consolidates, removes and adds knowledge. It may rewrite the root and nested `CLAUDE.md` files and `.claude/rules/`, update references in Claude Code-related files, and remove agent-only guides that classification proves are replaced. Human documentation stays.
- **What it does not change:** product code, tests, application configuration, settings, hooks, CI, and orchestrator functionality. Operational instructions, stage contracts, permissions, responsibilities and workflow logic are immutable here. Only project-specific factual context inside agents and skills may be corrected or completed, with approval; report an operational problem as a separate recommendation for `/workflow-review`. Work happens on a branch; nothing is pushed to the default branch.
- **The risk:** this is a large change to what every agent knows. Removing or rewriting an instruction can lose a fact; a `paths:` glob that is too broad adds context to unrelated work; one that is too narrow leaves a fact unloaded. Every removal and correction is evidence-backed and shown in the audit before it is applied.
- **The checks:** claims are validated against the code, path coverage and loading are measured, duplication and contradictions are checked, and a fresh reviewer audits the result. Unverifiable claims are flagged, not stated as fact.

Then ask with `AskUserQuestion`: **Start the read-only audit** (recommended) or **Cancel**. If the owner cancels or hesitates, stop and change nothing. Do not read the codebase first: the warning comes before any work.

## 1. Audit the existing knowledge base (read-only)

Inventory in three separate buckets:

1. **Modifiable Claude Code instructions:** the root `CLAUDE.md`, `CLAUDE.local.md` if present, every nested `CLAUDE.md`, files whose only consumer is agents, `.claude/rules/`, `.claude/agents/`, `.claude/skills/`, `.claude/orchestrator/profile.md` and `.claude/settings.json`.
2. **External evidence:** `docs/**/*.md`, `*-GUIDE.md`, generated docs, wikis and tickets that agents are told to read. Read them; do not assume a filename makes them agent-only.
3. **References to update:** instructions that tell an agent to find a guide, grep headings or read a section (`Grep` for "guide", "read this when" and the guide names), plus references to external or generated docs.

Also inventory applicable user-level and project-level instruction references. Read them to understand what loads in a session; never modify user-global configuration.

Preserve the orchestrator-managed sections in the root `CLAUDE.md`: the headings in `.claude/orchestrator/claude-md-sections.md`, `ADAPT` blocks and the workflow instructions.

Classify every document before judging it:

| Class | Examples | Treatment |
|---|---|---|
| **Agent-only** | A guide whose only consumer is agents, confirmed by references and ownership — not merely a `*-GUIDE.md` filename | Audit, then replace or remove after verification |
| **Human** | `README.md`, user or contributor documentation | Keep and leave authoritative; do not turn it into agent context by deleting it |
| **Mixed** | A document people read that also carries facts agents need | Keep the original; extract only the agent-facing facts into rules |
| **Generated or vendored** | `node_modules/`, `vendor/`, `third_party/`, build output, generated docs | First check whether Claude Code instructions reference it; never rewrite generated content, and exclude it only after that check |

Measure each document:

```bash
{{PYTHON}} .claude/skills/restructure-docs/analyze_docs.py --repo . <documents>
```

It prints every section's size and the repository files its backticked names resolve to. For a large section that holds several independent topics, list its paragraphs before deciding its destination:

```bash
{{PYTHON}} .claude/skills/restructure-docs/analyze_docs.py --repo . <document> --section "<heading>"
```

Record for each file: its size, which agent reads it and how (loaded automatically by Claude Code, or only because an instruction says to read it), and when it last changed (`git log -1 --format=%cs -- <path>`; mark untracked files as `untracked` instead of inventing a date). A guide read by hand is the usual source of wasted turns; a rule that loads for half the repository is the usual source of over-broad context.

While reading, note separately: duplicated facts, statements that contradict each other, instructions that look outdated, claims that are unsupported, and knowledge that is missing. Do not resolve them yet.

## 2. Investigate the codebase (read-only)

Implementation, tests, build configuration and CI establish observable behavior; owner decisions and architectural records establish intended behavior. Before deciding what a document should say, establish both. Where they disagree, record the discrepancy. Cover these areas:

| Area | What to capture |
|---|---|
| **Architecture** | Components, layers, dependencies, boundaries, data flows, entry points |
| **Build and publish system** | Build and publish commands, configurations, generated artifacts, release-only steps, required toolchain |
| **Testing** | Test structure, commands, filters, fixtures, what is not covered, slow or flaky areas |
| **Coding conventions** | Patterns actually used across representative files, naming, layering |
| **Dependency injection** | Composition root, service registration, lifetimes, where new services must be added |
| **Serialization and reflection** | Contracts depending on names or attributes, obfuscation/trimming/AOT constraints |
| **Error handling and logging** | Exception patterns, result types, log levels, correlation ids, places errors are swallowed |
| **Security boundaries** | Authorization checks, trust boundaries, tenant isolation, secrets handling |
| **Feature flags and environments** | Flags, configuration gates, local substitutes, staging/production differences |
| **Critical workflows** | Sequences and interactions that are easy to get wrong; where a change must touch several files |
| **Data** | Schemas, models, migrations, persistence conventions, invariants |
| **Integrations** | External APIs, services, authentication, messaging, retries, timeouts, local substitutes |
| **Constraints** | Technical limits, compatibility, platform quirks, known pitfalls, performance boundaries; distinguish a workaround from an intended design |
| **Development environment** | Required tools, environment variables, local setup |
| **Project-specific knowledge** | Anything that otherwise costs agents repeated searches or repeated mistakes |

Investigate cheaply:

- start from build files, CI, entry points, tests and the folders with the most cross-references;
- use `Explore` for breadth and the LSP `documentSymbol` and `findReferences` when available;
- choose files by architectural boundary and cross-reference density, not only by representative sampling across folders;
- read enough files to confirm a pattern across layers; do not read every file;
- run cheap read-only commands to confirm build and test tooling, versions and generated files;
- for a workflow, follow the call path from entry point to persistence and back.

**Evidence rule:** a convention observed in one file is a hypothesis, not a project rule. Confirm it across representative files, tests, configuration or CI before documenting it as project-wide. Record the evidence (paths, commands) for every claim that will become an instruction.

Mark each finding as **verified** (seen in code, tests, a command, or stated explicitly by the owner), **assumption** (plausible but not confirmed), or **unknown**. Only verified facts become instructions. Assumptions are flagged for the owner; unknown stays out.

### Prioritize value over completeness

The goal is to reduce repeated exploration and prevent mistakes, not to describe everything the code contains.

| Priority | Knowledge |
|---|---|
| **High** | Architectural boundaries, critical invariants, non-obvious dependencies, dangerous pitfalls, cross-component workflows |
| **Medium** | Build/test commands, conventions, integration behavior, important configuration |
| **Low** | Easily discoverable implementation details, obvious code structure, generic language/framework knowledge |

Add knowledge only when its expected value exceeds its context cost. Prefer concise constraints and navigation pointers over comprehensive explanations of implementation details. A project that obviously uses C# does not need a note saying so; a DLL that must not be obfuscated because reflection-based serialization depends on its property names does.

## 3. Validate, decide and get approval

Build one findings table:

| Claim or gap | Where | Doc class | Content class | Evidence | Status | Verdict | Action |
|---|---|---|---|---|---|---|---|

`Doc class` is from step 1 (agent-only, human, mixed, generated). `Content class` labels the kind of fact: architecture, command, convention, constraint, workflow, trap, navigation, reference, or other. `Status` is **verified**, **assumption**, or **unknown** from step 2.

Use these verdicts: **correct**, **incorrect**, **outdated**, **contradictory**, **duplicated**, **unsupported**, **missing**. Use these actions: **keep**, **correct**, **consolidate**, **remove**, **add**, **flag**.

- A correction needs evidence from implementation, tests, build configuration, CI, an owner decision or an architectural record.
- A removal needs a justification: wrong, redundant, irrelevant, or replaced by a verified statement.
- An addition needs support from the codebase, an architectural record or the owner. Never invent it.
- When observable behavior and intended behavior disagree, add a `contradictory` / `flag` row and ask the owner; do not silently choose the code or the document.

Persistent project knowledge and procedural instructions are different things:

- "The billing API stores invoices in PostgreSQL" is project knowledge.
- "Always run the billing integration tests after modifying the API" is a procedural instruction.
- "The orchestrator must not inspect implementation files" is a workflow constraint.

Then decide where each surviving or new fact belongs:

| Content | Destination |
|---|---|
| Universal project context, architecture overview, essential commands, navigation | Root `CLAUDE.md` |
| Instructions and traps true for every file in one directory | That folder's `CLAUDE.md` |
| Technical facts, constraints and conventions for a topic or feature | `.claude/rules/<topic>.md` with `paths:` |
| Agent responsibilities and role-specific operating instructions | `.claude/agents/` — do not change operational instructions; only approved factual context |
| Reusable procedures and workflows | `.claude/skills/` — do not change; report operational problems for `/workflow-review` |
| Human documentation | Keep in place; copy only agent-facing facts into rules with the owner's OK |

By default: `CLAUDE.md` and `.claude/rules/` hold project context, technical facts, constraints and conventions; `.claude/agents/` holds agent responsibilities and role-specific operating instructions; `.claude/skills/` holds reusable procedures and workflows. Do not move procedural instructions into context files, or project facts into skills, just because they appear together.

The same fact can matter to several consumers, and they do not read the same way:

- **Planner:** architecture, layers, dependencies, constraints, conventions and the decisions that shaped the code.
- **Orchestrator:** coordination-critical project facts, stage contracts and workflow constraints. It works from plans and reports, so path-scoped rules will not reach it; put this in the root `CLAUDE.md`, the profile or the plan.
- **Implementer:** the path-scoped rules and folder `CLAUDE.md` that match the files it opens.
- **Reviewer:** the implementation rules plus architectural requirements, invariants, expected behaviour and verification instructions.
- **Explore:** enough context to investigate efficiently without loading unrelated instructions.

Placement rules:

- **Folder `CLAUDE.md` only when there is meaningful folder-wide content** — what the folder is, its layering, its test command and filter, conventions, and traps that apply to all its files. Do not create one for every folder just to satisfy a structure. Aim for at most ~4 KB where one is justified.
- **`.claude/rules/<topic>.md`:** one topic or one feature, with `paths:` naming the code the fact applies to. One feature rule can hold the library part, the app step and the tests that pin it. Keep it readable when it is the only file loaded: no "see above" that points into another rule.
- **Root `CLAUDE.md`:** universal context, essential commands, pointers and traps, plus the orchestrator-managed sections. Project detail and release-only commands move out of it.
- **An architectural fact relevant to planning and review may belong in root context** even if its implementation is concentrated in one directory. A detailed implementation constraint usually belongs in a rule.
- **Human documentation:** leave it in place. If it also carries facts agents need, copy only those facts into a rule, with the owner's OK.

Choose `paths:` globs from the references the analyser found. For each rule, check both directions: every file the fact matters for is covered, and unrelated files do not pull it in. Prefer the narrowest set. Write globs with forward slashes, as `git ls-files` prints them. A shared file that opens several rules is acceptable, but list it in the report so the owner can see the cost.

Present the findings and the mapping together as one approval package. The mapping table has these columns:

| Item | Doc class | Content class | Destination (with `paths:`) | Consumer | Evidence | Change | Original |
|---|---|---|---|---|---|---|---|

`Change` is **corrected**, **added**, **kept**, **consolidated**, **removed**, or **flagged**. `Original` says whether the source file stays, is removed after replacement, or is human/mixed and remains. Add the unresolved questions, the before/after totals, and the files whose references must be repointed.

Then ask with `AskUserQuestion`: **Apply the audit on a branch** (recommended), **Change the plan**, or **Cancel**. Nothing is written before **Apply**. If the owner wants changes, revise and ask again. Later changes that cross the approval boundary in step 4 need a new approval; editorial changes that stay inside it do not.

## 4. Prepare the branch and apply

- `git status`: require a clean tree, or ask the owner what to do with the changes. Never mix this audit with unrelated work.
- Determine the current branch and the default branch (`git symbolic-ref refs/remotes/origin/HEAD`, or the profile's `{{DEFAULT_BRANCH}}`). If the current branch is the default, create a dedicated branch from it. If there is no remote and the current branch is already the default, record `git rev-parse HEAD` and verify `git branch --show-current` equals the default before creating the branch from that commit; if either check fails, stop and ask.
- Name the branch for the work, for example `docs/context-audit-<date>`. Use a worktree if the owner is working in parallel.
- Verify the new branch is not the default branch and that its base commit matches the recorded commit. If no safe base can be established, stop and ask. Never continue on the default branch.
- Read `.claude/orchestrator/profile.md` for `{{PYTHON}}`, the gate command and the PR command.

Preserve the orchestrator-managed sections, `ADAPT` blocks, workflow logic, stage contracts, permissions, responsibilities and settings. Only project-specific factual context inside skills and agents may be corrected or completed, and only as approved in step 3. Report an apparent operational problem as a separate `/workflow-review` recommendation; never weaken an agent's responsibility here.

Write the result:

- Correct, consolidate, remove and add content according to the approved findings table.
- For a section that is already correct and only needs to move, `split_docs.py` can move it mechanically:
  ```bash
  {{PYTHON}} .claude/skills/restructure-docs/split_docs.py <config.json> --repo .          # dry run: sizes
  {{PYTHON}} .claude/skills/restructure-docs/split_docs.py <config.json> --repo . --write  # write
  ```
  It is optional, not a requirement. A section may be rewritten or dropped with the justification recorded in step 3. The script still refuses to write a mechanical move that would leave a non-empty section without a home or an explicit `drop`. Keep the config and any one-off scripts outside the repository, under `{{PLANS_DIR}}/restructure-docs/<date>/`.
- Use Edit for corrections, consolidation and new knowledge. Every material change must be traceable to an approved finding; editorial changes inside this boundary do not need another approval:

  | Change | New approval? |
  |---|---|
  | Grammar, clarity and formatting | No |
  | Rewording without changing meaning | No |
  | Correcting an approved factual error | No |
  | Adding a new fact | Yes |
  | Removing a fact not listed for removal | Yes |
  | Moving content to another destination | Yes |
  | Changing a rule's path coverage | Yes |
  | Merging or splitting rules | Yes |
- Give each fact one home. Do not copy a fact into a folder file and a rule.
- Create a folder `CLAUDE.md` only where the audit found meaningful folder-wide content.
- Update references in Claude Code-related files: `.claude/agents/`, `.claude/skills/`, every `CLAUDE.md`/`CLAUDE.local.md`, and instructions in project docs. Update references elsewhere only when a renamed or removed agent-only document makes them genuinely invalid, and only with approval. Do not rewrite unrelated human documentation or source comments.
- Check whether `.gitignore` hides `.claude/rules/`, nested `CLAUDE.md` files or other generated/ignored instruction files. Add the `!/.claude/rules/` exception when needed; any broader exception is a separate approval. `.gitignore` is the only non-documentation file this skill edits. Then check every new file:
  ```bash
  git check-ignore -v <new file>...
  ```
  A rule or `CLAUDE.md` that git ignores does not reach another machine or another worktree.

The scripts normalize path separators, so configs and globs work with `/` or `\`; prefer forward slashes because `git ls-files` prints them. On Windows, list files explicitly: PowerShell does not expand `*` or `**` for these scripts.

## 5. Verify the result

Run all of these before removing an agent-only guide:

1. **Factual validation.** Check every instruction that remains against the code, tests, configuration or a command. Confirm file paths, type names, commands, contracts and workflows. Remove or flag anything still unsupported. A sentence that survived because it was in the old document is not verified.

2. **Coverage and loading.**
   ```bash
   {{PYTHON}} .claude/skills/restructure-docs/check_rules.py --repo .
   {{PYTHON}} .claude/skills/restructure-docs/check_rules.py --repo . --shared
   ```
   The first exits non-zero on a dead glob or a rule without `paths:`. A dead glob means the rule can never load by simulated matching. `--shared` lists files that load more than one rule, which is where over-broad globs hide. Then probe files with `check_rules.py --repo . <file>`: one per project or rule boundary, one shared file, and at least one file that should match zero rules. It prints the rules and folder `CLAUDE.md` files that file would load, with their sizes. Confirm the intended rule loads, unrelated rules do not, and the zero-rule file stays empty.

   These are simulated path-matching checks, not proof of runtime loading. Confirm the model against the Claude Code version in use and its rule-loading documentation. If runtime loading differs, report it; do not claim the script proves what the runtime loaded.

3. **Consistency.** No two files contradict each other about the same behaviour. Prefer one canonical definition with short references elsewhere; deliberate duplication is allowed where the loading model requires it for different consumers. The root file stays lean: pointers, commands, universal context and traps.

4. **Knowledge preservation.** Compare old and new at the level of facts, decisions, invariants, behavioral constraints, workflows, measurements and traps, not lines.
   - For a section moved unchanged, `verify_move.py loss --strict` is a gate:
     ```bash
     {{PYTHON}} .claude/skills/restructure-docs/verify_move.py loss --strict --old <old docs> --new <new files>
     ```
   - For a rewritten section, `loss` and `facts` are review aids, not gates. A disappeared identifier, number, path, command or quoted name is a fact to restore or to justify as wrong, redundant or irrelevant:
     ```bash
     {{PYTHON}} .claude/skills/restructure-docs/verify_move.py facts --old <old docs> --new <new files>
     ```
   These checks do not prove that meaning survived. The reviewer in section 6 checks that.

5. **Readability and consumer fit.** Each rule makes sense as the only file loaded, with clear headings and no "above"/"below" references into other files. The root file serves the planner and orchestrator; folder files serve their folder; rules serve the files their `paths:` match. No file exists only to fill a structure.

6. **References and tracking.** Every reference to a removed or renamed file is repointed. Every new file is tracked by git.

## 6. Independent review, read-only

For a first audit, or more than about 15 changed files, spawn one fresh reviewer with no knowledge of your reasoning: an Opus agent. For a smaller change, work through the same checklist yourself before committing. **The reviewer is read-only.** It reports findings with exact file locations and evidence; it does not edit, move, merge or delete files. That keeps the owner's approval meaningful.

Give it the approved findings and mapping, the original documentation (from `git show <base>:<path>`), the resulting documentation, the relevant source files and tests, and the verification results. Do not give it only your summary. Require it to inspect the implementation, tests and configuration independently; it must not validate your reasoning by trusting it.

Checklist:

- **Independent verification:** inspect the relevant implementation, tests and configuration directly; check claims against them, not against the implementer's prose.
- **Factual accuracy:** every file path, type name, command, contract and workflow the docs state; distinguish observable behavior from owner decisions and architectural records.
- **Observable vs intended:** confirm that any disagreement is reported as a discrepancy instead of silently treated as correct.
- **Placement:** content that only concerns some files belongs in a rule, not a folder `CLAUDE.md`; content true for a whole folder belongs there, not in a rule. Flag a folder `CLAUDE.md` that exists without meaningful folder-wide content.
- **`paths:` coverage:** intended files are covered, unrelated files are not pulled in, and shared files do not load half the rule set without reason.
- **Consumer fit:** the planner gets architecture and constraints, the orchestrator gets coordination facts outside path-scoped rules, implementers get local rules, reviewers get invariants and verification instructions, Explore gets enough context without noise.
- **Missing knowledge:** high-value project facts are still absent from the context structure.
- **Readability in isolation:** each rule makes sense as the only file loaded.
- **Contradictions and stale claims:** no two files disagree, and an outdated decision was corrected with evidence or flagged rather than silently rewritten.
- **Knowledge preservation:** decisions, invariants, behavioral constraints, workflows, measurements and traps survived, were corrected with evidence, or were removed with a justification.

When it reports back, evaluate each finding yourself. Apply editorial corrections that stay inside the approval boundary. A finding that crosses that boundary requires the owner's approval first. Re-run the affected checks after applying anything.

Then remove the replaced agent-only guides with `git rm`. Keep human and mixed originals. Report every flagged contradiction, outdated claim or uncertainty, including those you did not change.

## 7. Gate, commit, report

Run `{{GATE_CMD}}` when it is cheap enough to justify. Documentation-only changes should not trigger expensive application-wide integration or deployment tests unless the change affects something those tests validate. If the full gate is skipped, run the documentation and integrity checks instead and say plainly why. A failure that already exists on the default branch is reported, not fixed here.

Commit the documentation on the branch. Push and open a draft PR with `{{PR_CMD}}` only when the repository has a remote and the tooling is available; otherwise leave the completed branch locally and say so. Never merge; the owner decides.

Report, in this order:

- the audit summary: how many claims were correct, incorrect, outdated, contradictory, duplicated, unsupported or missing; what was corrected, consolidated, removed and added, with evidence; every place where observable and intended behavior disagreed;
- the mapping (old section or gap → new file, with document class and sizes) and the totals before and after;
- the number of rules and folder `CLAUDE.md` files, and the dead-glob, shared-file and probe results;
- the verification: factual validation, consistency, knowledge preservation and git tracking;
- the semantic review: what the reviewer found, what was applied, what still needs the owner's decision;
- unresolved uncertainties, outdated claims and questions that need the owner, kept separate from the applied changes;
- the gate result (or why it was skipped) and the branch/PR state;
- what the owner should do next: review the diff, run `/retro` after the next feature, and review the setup every 3–6 months.

## Rules

- **Observable and intended behavior are separate.** Implementation, tests, build configuration and CI establish observable behavior; owner decisions and architectural records establish intended behavior and design constraints. Existing documentation is historical context, not automatic authority. Report disagreements instead of choosing silently.
- **Verified facts only.** A convention seen once is a hypothesis; a workaround is not an architectural pattern. Do not present an assumption as a project rule, and never invent an architectural fact, convention or requirement.
- **Knowledge preservation, not verbatim preservation.** Verified and relevant information survives. Incorrect information is corrected with evidence. Redundant information is consolidated. Irrelevant information is removed with a justification. Missing information is added only when supported. Unverifiable information is flagged, not stated as fact.
- **Prioritize value over completeness.** Add knowledge only when its expected value exceeds its context cost; prefer concise constraints and navigation pointers to exhaustive implementation detail.
- **Knowledge and procedures are different.** `CLAUDE.md` and rules carry project context and constraints; agents carry responsibilities; skills carry reusable procedures. Do not blur them.
- **Permission before work.** The warning in step 0 and the plan approval in step 3 are both required. The owner may stop at either. Material changes inside the approval boundary do not need a new gate; crossing it does.
- **Preserve human documentation.** `README.md` and human-facing docs stay; only agent-facing facts are extracted from them.
- **Never remove orchestrator functionality.** Orchestrator-managed sections, `ADAPT` blocks, workflow logic, stage contracts, permissions and responsibilities survive. Operational fixes belong to `/workflow-review`, not this skill.
- **Docs only.** No product code, tests, application configuration, settings, hooks or CI changes. Update references in Claude Code-related files; broader reference changes need approval. A settings or hook change is a separate proposal with its own OK.
- **Never on the default branch.** Always work on a dedicated branch; verify the base commit and branch identity. Open a draft PR only where the repository has a remote and the tooling for it.
- **Simulated matching is not runtime loading.** `check_rules.py` validates globs; confirm its model against the Claude Code version and documentation before claiming what loads.
- **A rule loads only when its `paths:` match.** A rule with no matching file is dead; a rule with a too-broad glob is paid for by sessions that do not need it; a rule with a too-narrow glob leaves a fact unloaded. Probe a file that should match zero rules too.
- **One canonical fact, with deliberate exceptions.** Do not copy a fact into a folder file and a rule. A critical invariant may be restated for different consumers when the loading model requires it; keep one canonical definition and short references elsewhere.
- **No folder file for structure's sake.** Create a folder `CLAUDE.md` only when it has meaningful folder-wide content.
- **Right consumer.** Put a fact where the agent that needs it will actually see it. The orchestrator does not read code, so coordination facts cannot live only in path-scoped rules.
- **One-time optimization.** `/retro` maintains the result; `/workflow-review` improves the workflow. Do not duplicate their jobs.
- **If the repository is already well structured,** do not restructure it. Audit it, and propose targeted corrections for wrong, missing, duplicated or contradictory facts.

## What done looks like

- Every existing instruction is verified, corrected with evidence, consolidated, removed with a justification, or flagged as uncertain.
- Observable behavior and intended behavior are distinguished; every disagreement is reported for the owner.
- High-value knowledge that was missing is added with support from implementation, tests, records or the owner; low-value discoverable detail is not promoted.
- Every rule has a `paths:` list, every glob hits at least one repository file, and probed files load the rules that concern them, not unrelated ones; simulated matching is not presented as proven runtime loading.
- The root `CLAUDE.md` is lean and serves the planner and orchestrator; folder `CLAUDE.md` files exist only where content is folder-wide; rules serve the files they match; agents and skills keep their operational roles.
- No two files contradict each other; one canonical fact is reused with short references, with deliberate duplication only where the loading model requires it.
- The reviewer's findings are resolved or explicitly left for the owner, and unresolved uncertainties are reported.
- The work is committed on a dedicated branch; a draft PR is open when the repository supports it.
