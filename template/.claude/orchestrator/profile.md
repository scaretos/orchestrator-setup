# Orchestrator profile

The project-specific values `/orchestrator-init` filled into the skills and agents. Kept so a re-run (after an upgrade of the setup) can apply them again, and so `/workflow-review` knows the commands. Edit a value here and re-run `/orchestrator-init` to apply it everywhere.

- **Setup version:** <filled by /orchestrator-init>
- **Installed:** <date>

| key | value | used in |
|---|---|---|
| PROJECT_NAME | | descriptions of every skill and agent |
| PROJECT_SUMMARY | | `Explore` |
| SHELL | | plan self-check, plan reviewer: the shell every command must run in |
| EXTRA_TOOLS | | agent tool lists (`, PowerShell` on Windows, else empty) |
| BUILD_CMD | | stage implementer: quiet build of one project or package |
| TEST_CMD | | implementer, reviewer, plan template: one filtered test run, output cut to the last lines; `<project>` and `<filter>` stay placeholders for the plan |
| TEST_FAIL_HINT | | how a failed test run shows in that cut output |
| GATE_CMD | | final review, plan template, `/restructure-docs`: the whole verification |
| GATE_LOG | | where the gate writes its full output |
| WORKTREE_PREP | | `/execute-plan`: commands that make a fresh worktree buildable (restore, first build, index) |
| PLANS_DIR | | `/write-plan`, `/execute-plan`, `/restructure-docs` (its `audit.md`): where plans live, outside the repo |
| DEFAULT_BRANCH | | plan base, PR target, `/restructure-docs` branch base |
| PR_CMD | | draft PR command |
| PYTHON | | `/workflow-review`, `/restructure-docs`: the Python 3 command |
| BUILD_OUTPUT_DIRS | | `Explore`, settings deny list |
| EXTERNAL_SYSTEMS | | `/write-plan` step 4: systems whose behaviour must be measured, not assumed |
| UI_CHECK | | `/write-plan` *UI check*: how to see a UI change without a person |
| LAYERS | | plan template *Architecture*: the project's layers and what each may do |
| LSP_SETUP | | *Reading rules* in `CLAUDE.md`: per main language the LSP plugin, its server binary and how to install it |
| MACHINE_TRAPS | | implementer, reviewer *This machine*: environment traps |
| LAYOUT_ROWS | | `Explore` *Where things are* |

## Switches

Read by the skills each time they run: edit a value here and it applies to the next plan or execution, without re-running `/orchestrator-init`.

- **Parallel stages:** on
  - `on`: `/write-plan` may group stages that provably do not touch each other's work (its step 7), and `/execute-plan` runs each group at the same time, one worktree per member.
  - `off`: `/write-plan` skips step 7 and writes no groups; the plan reviewer treats any group as a Must fix; `/execute-plan` runs the members of a group already written one after another, in the order listed, in the feature worktree.
  - Off for one run only: `/write-plan --sequential <feature>`, or `/execute-plan <plan> --sequential`.
