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
> 2. **Stop by time or by iterations?**
>    - **By time:** "run for 12 hours" — I'll keep launching iterations until the time is up
>    - **By iterations:** "run 5 iterations" — I'll stop after exactly N iterations
> 3. **Any constraints?** (e.g., "don't change the data loader", "only try attention-based methods")

Store the answers as: `NUM_GPUS`, `STOP_MODE` ("time" or "iters"), `LIMIT` (hours or iteration count), `CONSTRAINTS`.

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

Note: `GOAL`, `BASELINE`, `BEST`, `PRIMARY_METRIC`, and how many iterations already exist. The loop continues from where previous iterations left off — if 3 iterations already ran, the loop starts at iteration 4.

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

Every idea you formulate must serve the user's `DIRECTION`. This is the high-level goal — all iterations in this loop are different approaches to achieve it. Do not drift into unrelated experiments.

Based on the current research state:

- **First iteration:** Use `DIRECTION` directly. This is exploratory — search for papers relevant to the goal.
- **After a successful iteration:** Build on what worked. Try a variant, combine with another technique, or push the same direction further.
- **After a failed iteration:** Try a different approach to the same goal. Analyze what went wrong and pivot.
- **After a plateau (3+ iterations with <1% improvement):** Search for fresh papers with a broader query. Try a fundamentally different approach — but still toward the same `DIRECTION`.

Always respect `CONSTRAINTS` from Phase 1.

Formulate ideas for the next batch. If `NUM_GPUS > 1`, formulate multiple ideas (up to `NUM_GPUS`), each exploring a different angle toward `DIRECTION`.

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

Always wait for running experiments to finish — never kill a running experiment.

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
- **Limit reached?**
  - If `STOP_MODE` is "iters" and iterations launched by this loop >= `LIMIT` → stop, go to Phase 4.
  - If `STOP_MODE` is "time" and wall-clock hours >= `LIMIT` → do NOT launch new iterations, but wait for any running experiments to finish and collect their results. Then go to Phase 4.
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
- When the limit is reached (time or iterations), stop launching new iterations but always wait for running experiments to finish and collect their results.
- With multiple GPUs, launch `NUM_GPUS` different iterations simultaneously. Wait for the full batch to finish before starting the next batch.
- Always present the final report, even if stopped early.
