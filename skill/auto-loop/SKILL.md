---
name: auto-loop
description: Run multiple research iterations automatically. Launches an idea, waits for the experiment, checks results, decides next direction, repeats.
when_to_use: When the user says "run automatically", "auto loop", "keep iterating", "run N iterations", "overnight run", "hands-free", or wants the agent to run multiple idea-iter cycles without manual intervention.
argument-hint: <research direction>
arguments: direction
disable-model-invocation: false
version: "1.0.0"
effort: high
allowed-tools: Bash(python -m research_agent:*), Bash(test:*), Bash(git diff:*), Bash(git add:*), Bash(git commit:*), Bash(git branch:*), Bash(git checkout:*), Bash(sleep:*), Read, Grep, WebFetch(domain:arxiv.org), WebFetch(domain:semanticscholar.org), WebSearch, Agent, Skill
---

# Auto-Loop: Hands-Free Research Iterations

You are running a fully autonomous research loop. The user gives you a research direction — you run multiple iterations of idea → code → experiment → results → next idea, stopping when the goal is reached or the iteration budget is exhausted.

```
/auto-loop improve segmentation accuracy
/auto-loop try different attention mechanisms
/auto-loop explore data augmentation strategies
```

Your FIRST action must be to set up the Python tools:

```bash
export PYTHONPATH="$HOME/.claude/skills/auto-loop:$PYTHONPATH"
```

---

## Phase 1: Ask Setup Questions

Before starting, ask the user these questions. **Wait for answers before proceeding.**

> **Research direction:** $direction
>
> Before I start the autonomous loop, I need a few details:
>
> 1. **How many GPUs can I use?** (e.g., 1, 2, 4 — each GPU runs a different iteration simultaneously)
> 2. **How many hours should I run?** (e.g., 6, 12, 24 — I'll stop after this, even mid-iteration)
> 3. **Max iterations?** (e.g., 5, 10, 20 — or "until goal reached")
> 4. **Any constraints?** (e.g., "don't change the data loader", "only try attention-based methods")

Store the answers as: `NUM_GPUS`, `MAX_HOURS`, `MAX_ITERS`, `CONSTRAINTS`.

---

## Phase 2: Load State

```bash
cd "$(git rev-parse --show-toplevel)"
test -f state.json && python -m research_agent.state read || echo "NO_STATE"
```

If no state exists:
```bash
python -m research_agent.state init --goal "$direction" --metric "improvement"
```

Note: `GOAL`, `BASELINE`, `BEST`, `COMPLETED_ITERS`, `PRIMARY_METRIC`.

Check GPU availability:
```bash
python -m research_agent.deploy preflight
```

Confirm the available GPUs match what the user requested. If fewer GPUs are available, tell the user and adjust `NUM_GPUS` accordingly.

Record the start time.

---

## Phase 3: Iteration Loop

Repeat the following for up to `MAX_ITERS` iterations (or until `MAX_HOURS` exceeded):

### 3a: Decide what to try next

Based on the current research state:

- **First iteration:** Use the user's `DIRECTION` as the idea. This is exploratory — search for papers.
- **After a successful iteration:** Build on what worked. Try a variant, combine with another technique, or push the approach further.
- **After a failed iteration:** Try something different. Analyze what went wrong and pivot.
- **After a plateau (3+ iterations with <1% improvement):** Search for fresh papers with a broader query. Try a fundamentally different approach.

Always respect `CONSTRAINTS` from Phase 1.

Formulate ideas for the next batch. If `NUM_GPUS > 1`, you can formulate multiple ideas to run in parallel (up to `NUM_GPUS` at a time).

### 3b: Launch iterations

Formulate `NUM_GPUS` different ideas (or fewer if near `MAX_ITERS`). Each idea should explore a different angle — do not run the same idea twice.

Launch them one at a time. Each idea-iter creates a separate branch:

```
skill: "idea-iter"
args: "--auto <IDEA_1>"
```

**Wait for idea-iter to finish its code changes and launch.** Then start the next:

```
skill: "idea-iter"
args: "--auto <IDEA_2>"
```

Repeat until `NUM_GPUS` experiments are running. Each runs on a different GPU automatically (deploy.py auto-selects the GPU with most free memory).

### 3c: Wait for experiments to finish

Poll for completion every 5 minutes:

```bash
python -m research_agent.state read
```

Check if any iteration's status is still `"running"`. If yes, wait:

```bash
sleep 300
```

Repeat until ALL running iterations in this batch change to `"completed"` or `"failed"`.

Check wall-clock time — if `MAX_HOURS` exceeded, stop the loop.

### 3d: Collect results

For each iteration that just finished:

```bash
python -m research_agent.deploy status --output-dir <CHECKPOINT>
```

If completed successfully, extract metrics and record:
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

Commit results for each iteration:
```bash
git checkout iter/<ID>-*
python -m research_agent.git_ops commit-results --iteration <ID> --state state.json
python -m research_agent.git_ops push
```

If any iteration is the new best, merge to main:
```bash
python -m research_agent.git_ops merge-best --state state.json
python -m research_agent.git_ops push
git checkout main
```

### 3e: Evaluate and decide

After recording all results, check:

- **Goal reached?** If the primary metric meets or exceeds the goal → stop the loop, go to Phase 4.
- **Budget exhausted?** If iteration count or wall-clock hours exceeded → stop, go to Phase 4.
- **Otherwise** → loop back to 3a with updated state. Use learnings from this batch to formulate the next batch.

---

## Phase 4: Final Report

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
- Stop if wall-clock time exceeds `MAX_HOURS` even mid-iteration.
- With multiple GPUs, launch `NUM_GPUS` different iterations simultaneously. Wait for the full batch to finish before starting the next batch.
- Always present the final report, even if stopped early.
