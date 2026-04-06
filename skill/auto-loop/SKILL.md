---
name: auto-loop
description: Run multiple research iterations automatically. Launches an idea, waits for the experiment, checks results, decides next direction, repeats.
when_to_use: When the user says "run automatically", "auto loop", "keep iterating", "run N iterations", "overnight run", "hands-free", or wants the agent to run multiple idea-iter cycles without manual intervention.
argument-hint: <research direction> [--iterations N] [--max-hours H]
arguments: direction
disable-model-invocation: false
version: "1.0.0"
effort: high
allowed-tools: Bash(python -m research_agent:*), Bash(test:*), Bash(git diff:*), Bash(git add:*), Bash(git commit:*), Bash(git branch:*), Bash(git checkout:*), Bash(sleep:*), Read, Grep, WebFetch(domain:arxiv.org), WebFetch(domain:semanticscholar.org), WebSearch, Agent, Skill
---

# Auto-Loop: Hands-Free Research Iterations

You are running a fully autonomous research loop. The user gives you a research direction — you run multiple iterations of idea → code → experiment → results → next idea, stopping when the goal is reached or the iteration budget is exhausted.

```
/auto-loop improve segmentation accuracy --iterations 5
/auto-loop try different attention mechanisms --max-hours 12
/auto-loop explore data augmentation strategies
```

Your FIRST action must be to set up the Python tools:

```bash
export PYTHONPATH="$HOME/.claude/skills/auto-loop:$PYTHONPATH"
```

---

## Phase 1: Parse Arguments & Load State

Extract from `$direction`:
- `DIRECTION` — the research direction (everything except flags)
- `--iterations N` — max iterations to run (default: 5)
- `--max-hours H` — max wall-clock hours (default: 24)

```bash
cd "$(git rev-parse --show-toplevel)"
test -f state.json && python -m research_agent.state read || echo "NO_STATE"
```

If no state exists:
```bash
python -m research_agent.state init --goal "$direction" --metric "improvement"
```

Note: `GOAL`, `BASELINE`, `BEST`, `COMPLETED_ITERS`, `PRIMARY_METRIC`.

Record the start time.

---

## Phase 2: Iteration Loop

Repeat the following for up to N iterations (or until max hours exceeded):

### 2a: Decide what to try next

Based on the current research state:

- **First iteration:** Use the user's `DIRECTION` as the idea. This is exploratory — search for papers.
- **After a successful iteration:** Build on what worked. Try a variant, combine with another technique, or push the approach further.
- **After a failed iteration:** Try something different. Analyze what went wrong and pivot.
- **After a plateau (3+ iterations with <1% improvement):** Search for fresh papers with a broader query. Try a fundamentally different approach.

Formulate `NEXT_IDEA` — a specific, concrete idea for the next iteration.

### 2b: Run idea-iter

Invoke the `Skill` tool:
```
skill: "idea-iter"
args: "--auto <NEXT_IDEA>"
```

The `--auto` flag skips user confirmation so the loop runs unattended.

**Wait for idea-iter to complete.** It will implement code, commit, and launch the experiment.

### 2c: Wait for experiment to finish

Poll for completion every 5 minutes:

```bash
python -m research_agent.state read
```

Check if the latest iteration's status is still `"running"`. If yes, wait:

```bash
sleep 300
```

Repeat until status changes to `"completed"` or `"failed"`.

Also check wall-clock time — if `--max-hours` exceeded, stop the loop.

### 2d: Collect results

```bash
python -m research_agent.state read
```

Read the latest iteration's metrics and feedback. If the experiment used a checkpoint directory, check for results:

```bash
python -m research_agent.deploy status --output-dir <CHECKPOINT>
```

If the experiment completed successfully, record metrics:
```bash
python -m research_agent.state complete-iteration --id <ITER_ID> \
  --metric-name <PRIMARY_METRIC> --metric-value <VALUE> \
  --feedback "<what we learned — insights for the next iteration>"
```

If failed:
```bash
python -m research_agent.state fail-iteration --id <ITER_ID> \
  --feedback "<what went wrong>"
```

### 2e: Evaluate and decide

After recording results, check:

- **Goal reached?** If the primary metric meets or exceeds the goal → stop the loop, go to Phase 3.
- **Budget exhausted?** If iteration count or wall-clock hours exceeded → stop, go to Phase 3.
- **Otherwise** → loop back to 2a with updated state.

---

## Phase 3: Final Report

After the loop ends, generate a full report:

```bash
python -m research_agent.state report
```

Present to the user:

```
## Auto-Loop Complete

**Direction:** <DIRECTION>
**Iterations run:** <N>
**Best result:** <PRIMARY_METRIC>: <BEST_VALUE> (iter <BEST_ITER>)
**Baseline:** <BASELINE_VALUE>
**Total improvement:** <DELTA>

### Iteration Summary
| # | Idea | Result | Delta | Learnings |
|---|------|--------|-------|-----------|
| 1 | ...  | ...    | ...   | ...       |

### What worked
- <patterns from successful iterations>

### What didn't work
- <patterns from failed/regressed iterations>

### Suggested next steps
- <based on the trajectory of results>
```

If the best iteration hasn't been merged to main yet:
```bash
python -m research_agent.git_ops merge-best --state state.json
python -m research_agent.git_ops push
```

---

## Rules

- Always use `--auto` when invoking `/idea-iter` so the loop runs unattended.
- Each iteration must be a different idea — do not repeat the same change.
- Use learnings from previous iterations to inform the next one.
- Commit and push after every iteration (idea-iter handles this).
- If an iteration fails, do not retry the same thing — pivot.
- Poll with `sleep 300` (5 min) between checks. Do not poll more frequently.
- Stop if wall-clock time exceeds `--max-hours` even mid-iteration.
- Always present the final report, even if stopped early.
