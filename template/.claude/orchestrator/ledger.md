# Workflow ledger

What `/workflow-review` changed in this workflow, what it expected, and what the next review measured. Every review reads this before proposing anything: a rejected proposal comes back only with new evidence that answers its reason.

Units are the relative cost units of `analyze.py` (input tokens of the strongest model = 1).

## Reviews

| date | runs reviewed | total units | units per stage | main finding |
|---|---|---:|---:|---|

## Changes

<!-- One entry per adopted change:
### W1 <title> (adopted YYYY-MM-DD)
- Change: <file>: <what changed>
- Evidence: <run, agent, turn range, numbers; measured or estimated>
- Baseline: <metric> = <value>
- Expected: <metric> → <value>
- Verify: <how the next review measures it>
- Result: <filled by the next review: confirmed | no effect | regressed, with the numbers>
-->

## Rejected

<!-- One entry per rejected proposal:
### R1 <title> (rejected YYYY-MM-DD)
- Proposal: <what>
- Reason: <the owner's reason, in their words>
- Evidence at the time: <numbers>
-->

## Inherited

Measured in the project this setup comes from, not in this one. Treat them as strong priors: re-measure here before relying on one, and before proposing the opposite.

### I1 Subagents stay on the 5-minute cache
- A replay of three runs' subagent turns with a 1-hour cache: implementers −0.41M units, stage reviewers +1.04M, plan reviewers +0.40M, net +1.1M. Only 16 turns sat in the 5–60 minute window; every other cache write would have cost 2× instead of 1.25×.
- Check here with `analyze.py ttl <sessions>`.

### I2 Should fix items go to a warm implementer only
- A cold resume rewrites the implementer's whole context (130–300k tokens); reviews took 3–9 minutes. Rule in `/execute-plan` step 5: send Should fix items at once only when the review took under 4 minutes or a later stage builds on them; otherwise batch them into the final `FIX` stage.

### I3 Checks run in the stage that produces the behaviour
- A late "check everything" stage found 22 violations in earlier stages' work and needed an inserted fix stage (about a quarter of that build). Rule in `/write-plan` step 6 *Verify*.

### I4 Ask, don't park
- An owner conflict left as "to confirm" came back after the owner's first real look as a fix stage that reopened finished stages. Rule in `/write-plan` step 2.

### I5 Small work gets no agents
- At most 3 stages (about 15 files) without external measurement: one session is cheaper than an orchestrator plus agents, which each start cold. Rule in `/write-plan` *First*.
