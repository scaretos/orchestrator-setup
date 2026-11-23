<!--
Sections /orchestrator-init merges into the project's root CLAUDE.md. The agents refer to them by name
(*Reading rules*, *New tests*, *The gate*, *Conventions*), so keep these headings. Adapt the wording to the
project; keep each rule's reason, which is what lets a model apply it to a case the rule did not name.
-->

## Where the context lives

Context loads by itself as you work; do not go looking for a guide.

- **Per folder:** a folder's `CLAUDE.md` holds what is true for every file in it (its test command, its traps). It loads when you read or edit a file there.
- **Per topic:** `.claude/rules/*.md`, each with `paths:` frontmatter, loads when you read or edit a file its `paths:` match. To know a topic before touching its code (planning, a review), open the rule file directly.
- **Workflows:** `/write-plan` + `/execute-plan` (staged agent builds), `/retro` (what a finished piece of work taught), `/workflow-review` (how the workflow itself performed).
- A rule or `CLAUDE.md` statement that turned out wrong or incomplete is fixed in the same piece of work.

## Planning work

- At most 3 stages and nothing external to measure: plan and build in one session, run the gate, done. Agents cost more than they save on work that small: each starts cold and reads its share again.
- Larger work: `/write-plan <feature>`, read the plan, then `/execute-plan <plan path>` in a new session.

## The gate

`{{GATE_CMD}}` is the verification command. Run it once when a piece of work is done, not after each change. On failure read the last lines of `{{GATE_LOG}}` rather than re-running the suite. While iterating, run only the tests of the code you touch, with a filter.

Run verification in the foreground. No background jobs, no polling loops: every look at a log is a turn that re-reads the whole context.

When the gate is green at the end of a piece of work, invoke the `retro` skill before the final report or PR, in the main session only.

## New tests

A test written from the same understanding as the code shares its blind spots. Add a new test only when it checks against something independent of your code, or guards something that must not change:

- **An external system or a real input:** behaviour that must equal a real system's gets a test against that system; a form found in real data is rebuilt as a fixture.
- **An owner decision:** one test per rule the owner decided, with inputs and expected result taken from the decision, written before the code.
- **A promise to the user:** what the docs say a feature does; security and privacy rules.
- **A fixed bug:** one test that fails without the fix.
- **An existing contract test:** add the new item to the lists those tests enforce.
- **A table of cases** (a parser, formats): one table-driven test, not a method per case.

No new tests for plumbing, getters and setters, each error branch, a second path to something already pinned, or code checked against its own output. Existing tests stay; change one only when the behaviour it pins changes on purpose.

## Reading rules

- Locate before you read: Grep (scoped to a folder, never the repository root, which can hold full worktree copies under `.claude/worktrees/`), or LSP `documentSymbol` for a file's members.
- Every use of a known symbol before a rename, removal or signature change: LSP `findReferences` where available; otherwise Grep every naming variant.
- Files you will edit: read whole, early, once. Large files: read only the ranges you edit.
- Files you need one fact from: read only the range the search hit points at.
- Never re-read a range already in your context; trust your own edits.
- Never read build output ({{BUILD_OUTPUT_DIRS}}).

## Conventions

- **Comments:** only where the code does not explain itself; say why, never what.
- **Temporary files:** never commit probes, scratch files or plans.
