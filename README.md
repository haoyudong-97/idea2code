# Research Agent

> Once people said "Talk is cheap. Show me the code." But now in the era of vibe coding, I think the reverse might be true: your ability to create a new idea is far more important than being able to implement it.
>
> With this idea in mind, this project is created to accelerate the idea-to-real-code step.

A project-agnostic autonomous research loop for Claude Code. The **orchestrator** Claude Code session runs in tmux and controls **worker** Claude Code sessions (paper search, code implementation, idea discovery) that run as background processes. No API key needed — uses your Claude subscription.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Components](#components)
- [Requirements](#requirements)
- [Activation (Step-by-Step)](#activation-step-by-step)
- [Iteration Protocol](#iteration-protocol)
- [CLI Reference](#cli-reference)
- [Monitoring Progress](#monitoring-progress)
- [How progress.md Works](#how-progressmd-works)
- [Git Workflow](#git-workflow)
- [State File Schema](#state-file-schema)
- [Customization](#customization)

---

## Overview

You define a research goal. Claude Code autonomously searches literature, implements changes, runs experiments, and tracks everything via git. After each iteration, it presents results and **waits for your feedback** (or auto-continues in autonomous mode). You stay in control; the agent does the grunt work.

## Architecture

```
tmux session "research"
┌─────────────────────────────────────────────────────────┐
│  window 0: Claude Code (ORCHESTRATOR)                    │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ Controls the loop:                                  │ │
│  │  1. Read state.json (recover context)               │ │
│  │  2. Literature search → papers (background worker)  │ │
│  │  3. Code implementation → code change (bg worker)   │ │
│  │  4. Review changes, git branch + commit             │ │
│  │  5. Launch experiment (background)                  │ │
│  │  6. Poll for completion                             │ │
│  │  7. Analyze, record, commit results                 │ │
│  │  8. Merge best to main                              │ │
│  │  9. Summarize to user                               │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  User: watches, provides feedback, Ctrl-b d to detach    │
└─────────────────────────────────────────────────────────┘

Background workers (launched automatically by the Python scripts):
  - claude -p for literature search (paper search)
  - claude -p for code implementation (code changes)
  - claude -p for idea discovery (trend digest)
```

**Key insight:** Workers run as background processes (not in separate tmux windows), so only one tmux window is needed. The Python scripts handle process launching, prompt piping, and output polling automatically.

## Components

| File | Purpose |
|------|---------|
| `idea_discovery.py` | **Idea Discovery**: Fetches recent arXiv/S2 papers, digests trends, proposes research ideas |
| `literature_search.py` | **Literature Search**: Paper search — spawns `claude -p` background worker, uses WebSearch |
| `code_implementation.py` | **Code Implementation**: Spawns `claude -p` background worker, edits project files |
| `search_papers.py` | Fallback paper search via Semantic Scholar + arXiv APIs (no Claude needed) |
| `state.py` | Persistent JSON state + auto-updates `progress.md` |
| `git_ops.py` | Branch per iteration, structured commits, merge best to main |
| `run_and_wait.sh` | Experiment runner with `.done` completion marker |
| `protocol.md` | Research loop protocol (append to your project's CLAUDE.md) |

## Requirements

- **Python 3.10+**
- **Claude Code CLI** (`claude`) with an active subscription
- **tmux** (for orchestrator session; workers run as background processes)
- **git** (for iteration tracking)

No API key needed. Workers use `claude -p` (pipe mode) which authenticates via your Claude subscription.

## Project Structure

```
your_project/
├── CLAUDE.md                    # Protocol instructions for Claude (appended from protocol.md)
├── progress.md                  # Your goal + auto-updated tracking dashboard
├── state.json                   # Machine-readable state (created at runtime)
└── research_agent/
    ├── idea_discovery.py        # Fetch recent papers, digest trends, propose ideas
    ├── literature_search.py     # Paper search via Claude background worker
    ├── code_implementation.py   # Code changes via Claude background worker
    ├── search_papers.py         # Fallback paper search (Semantic Scholar + arXiv APIs)
    ├── state.py                 # State management + progress.md auto-updates
    ├── git_ops.py               # Git branching, commits, merges per iteration
    ├── run_and_wait.sh          # Experiment runner with completion markers
    └── protocol.md              # Source protocol (append to your CLAUDE.md)
```

---

## Activation (Step-by-Step)

### Step 1: Make the package importable

```bash
# Option A: Copy into your project
cp -r research_agent/ /path/to/your/project/

# Option B: PYTHONPATH (add to .bashrc for persistence)
export PYTHONPATH="/path/to/parent/of/research_agent:$PYTHONPATH"
```

### Step 2: Append the protocol to your project's CLAUDE.md

```bash
cd /path/to/your/project
cat research_agent/protocol.md >> CLAUDE.md
```

Edit the appended section to customize metric names, experiment scripts, and file paths.

### Step 3: Create `progress.md` in your project directory

Write your research goal — the agent will automatically append a tracking section below it as it runs (see [How progress.md works](#how-progressmd-works)).

```bash
cat > progress.md << 'EOF'
# Research Goal

Improve heart segmentation 3D Dice above 0.92 using adapter architecture changes.

## Constraints
- Keep parameter count under 1M
- Must converge within 200 epochs
EOF
```

### Step 4: Start tmux and launch Claude Code

```bash
tmux new -s research
cd /path/to/your/project
conda activate your_env
claude
```

### Step 5: Tell Claude to start the loop

```
# Interactive mode (default):
Start the research loop from progress.md

# Autonomous mode:
Start the research loop from progress.md, run autonomously
```

### Step 6: Provide feedback or monitor

**Interactive mode** — Claude presents a summary after each iteration. You can:
- Steer: "Focus on token-wise adaptation next"
- Approve: "Looks good, continue"
- Reject: "Revert this, try increasing spd_rank instead"
- Go autonomous: "Continue autonomously"

**Autonomous mode** — Claude continues without waiting. Interrupt anytime:
- Type to give new instructions
- "Wait for my feedback from now on" to switch to interactive

### tmux Controls

| Action | Command |
|--------|---------|
| Detach (leave running) | `Ctrl-b d` |
| Reattach | `tmux attach -t research` |
| List sessions | `tmux ls` |
| List windows | `Ctrl-b w` (window list) |

---

## Iteration Protocol

| Step | Action | Tool |
|------|--------|------|
| 1 | Read state (recover context) | `python -m research_agent.state read` |
| 2 | *(Optional)* Literature search — find papers | `python research_agent/literature_search.py ...` |
| 3 | Create git branch | `python -m research_agent.git_ops branch-start ...` |
| 4 | **Register iteration** | `python -m research_agent.state start-iteration ...` |
| 5 | Code implementation — implement change | `python research_agent/code_implementation.py ...` |
| 6 | Review changes | `git diff` |
| 7 | Commit code + push | `python -m research_agent.git_ops commit-code ...` + `push` |
| 8 | **Launch iteration** + experiment | `python -m research_agent.state launch-iteration ...` then `run_and_wait.sh` |
| 9 | Poll for completion | `test -f <dir>/.done && cat <dir>/.done \|\| echo RUNNING` |
| 10 | Analyze results | Read eval logs, compare to baseline/best |
| 11 | **Complete or fail iteration** | `python -m research_agent.state complete-iteration ...` or `fail-iteration` |
| 12 | Commit results + push | `python -m research_agent.git_ops commit-results ...` + `push` |
| 13 | Merge if best | `python -m research_agent.git_ops merge-best ...` + `push` |
| 14 | Summarize to user | Present results and proposed next steps |
| 15 | **Show today's arXiv** | `idea_discovery.py --fetch-only` (free), ask user if any look relevant |
| 16 | Next iteration | Wait for feedback OR auto-decide |

Steps 4, 8, and 11 are the lifecycle transitions (`coding` → `running` → `completed`/`failed`). Each transition updates `progress.md` so the user can see what's happening during long experiments.

> **Shortcut:** For simple iterations, `add-iteration` still works as a single command that creates + completes atomically.

**Concurrent iterations:** You can start coding iter N+1 while iter N trains. See `protocol.md` for details.

**When to search papers (literature search):**
- Exploring a new technique
- Previous iterations plateaued, need fresh ideas
- User asks about literature

**When to skip search:**
- User gave a specific instruction
- Next step is obvious from previous results

---

## CLI Reference

### idea_discovery.py — Trend Digest & Research Ideas

```bash
# Fetch recent papers and generate research ideas
python research_agent/idea_discovery.py --categories cs.CV,eess.IV --days 3

# With project context
python research_agent/idea_discovery.py --categories cs.CV --days 7 \
  --state state.json --progress progress.md

# Use aliases: medical-imaging, computer-vision, machine-learning, ai, nlp, robotics
python research_agent/idea_discovery.py --categories medical-imaging --days 3

# Also pull from Semantic Scholar
python research_agent/idea_discovery.py --categories cs.CV --days 3 \
  --s2-query "medical image segmentation"

# Just fetch papers, skip idea generation
python research_agent/idea_discovery.py --categories cs.CV --days 3 --fetch-only
```

**How it works:** Fetches papers from arXiv RSS + API (and optionally Semantic Scholar), sends them to a Claude background worker which digests trends and proposes 3-5 research ideas aligned with your goal.

**Output:** `results/ideas.json` with trend digest + ranked research ideas. `results/recent_papers.json` with all fetched papers.

### literature_search.py — Paper Search (background worker)

```bash
# Search with explicit topic
python research_agent/literature_search.py "orthogonal adapter fine-tuning" results/search.json

# With project context (auto-deduplicates)
python research_agent/literature_search.py "PEFT medical segmentation" results/search.json --state state.json

# Auto-generate topic from last iteration
python research_agent/literature_search.py --auto results/search.json --state state.json

# Custom timeout (default: 300s)
python research_agent/literature_search.py "topic" results/search.json --timeout 600
```

**How it works:** Writes a prompt file, launches `claude -p` as a background process, polls for output, parses JSON array of papers.

### code_implementation.py — Code Implementation (background worker)

```bash
# From paper results
python research_agent/code_implementation.py --papers results/search.json --project-dir .

# From direct instruction
python research_agent/code_implementation.py --instruction "increase spd_rank to 8" --project-dir .

# With context and file focus
python research_agent/code_implementation.py --papers results/search.json --project-dir . \
  --state state.json --files models/sam/modeling/common.py cfg.py

# Custom timeout (default: 600s)
python research_agent/code_implementation.py --instruction "..." --project-dir . --timeout 900
```

**How it works:** Writes a prompt file, launches `claude -p` as a background process (from the project directory), polls for output, parses change summary JSON.

**Output:** JSON to stdout: `{hypothesis, change_summary, files_modified, papers_used}`

### search_papers.py — Fallback Search (no Claude needed)

```bash
python research_agent/search_papers.py "query" --limit 10 --year-min 2023
```

Uses Semantic Scholar + arXiv APIs directly. No relevance scoring.

### state.py — State Management

```bash
# Initialize session
python -m research_agent.state init --progress progress.md --metric test_3d_dice

# Read state
python -m research_agent.state read
python -m research_agent.state read --field best

# Set baseline
python -m research_agent.state set-baseline --checkpoint "..." --metrics '{"test_3d_dice": 0.905}'

# Iteration lifecycle (recommended)
python -m research_agent.state start-iteration \
  --hypothesis "Token-wise FiLM" --change "enable cond_scale_tokenwise"

python -m research_agent.state launch-iteration --id 3 --checkpoint "checkpoints/exp3"

python -m research_agent.state complete-iteration --id 3 \
  --metric-name test_3d_dice --metric-value 0.912 \
  --feedback "good improvement"

python -m research_agent.state fail-iteration --id 3 --feedback "OOM error"

# Backward-compatible shortcut (creates + completes atomically)
python -m research_agent.state add-iteration \
  --hypothesis "..." --change "..." --checkpoint "..." \
  --metric-name test_3d_dice --metric-value 0.912 \
  --feedback "..."

# Report
python -m research_agent.state report
```

**Lifecycle transitions:**

| Command | From | To | When |
|---------|------|----|------|
| `start-iteration` | *(new)* | `coding` | After branch creation, before coding |
| `launch-iteration` | `coding` | `running` | After commit, before experiment |
| `complete-iteration` | `running` | `completed` | After experiment succeeds |
| `fail-iteration` | `coding`/`running` | `failed` | On error (OOM, NaN, abandoned) |
| `add-iteration` | *(new)* | `completed` | Shortcut: one-step create + complete |

### git_ops.py — Git Workflow

```bash
python -m research_agent.git_ops branch-start --iteration 3 --change "enable tokenwise film"
python -m research_agent.git_ops commit-code --iteration 3 --hypothesis "..." --change "..."
python -m research_agent.git_ops commit-results --iteration 3 --state state.json
python -m research_agent.git_ops merge-best --state state.json
python -m research_agent.git_ops push
python -m research_agent.git_ops log
```

### run_and_wait.sh — Experiment Runner

```bash
bash research_agent/run_and_wait.sh scripts/my_exp.sh checkpoints/my_exp/
# Poll: test -f checkpoints/my_exp/.done && cat checkpoints/my_exp/.done || echo RUNNING
```

---

## Monitoring Progress

```bash
# Human-readable status
cat progress.md

# Machine-readable state
python -m research_agent.state read

# Best result only
python -m research_agent.state read --field best

# Git iteration history
python -m research_agent.git_ops log

# Check experiment status
test -f checkpoints/my_exp/.done && cat checkpoints/my_exp/.done || echo RUNNING
```

---

## How progress.md Works

`progress.md` is the human-readable record of your research loop. It has two sections:

1. **Your goal** (top) — you write this once at setup. The agent never touches it.
2. **Agent tracking** (bottom) — auto-generated below a sentinel line. Updated after every significant action.

### Auto-update triggers

The tracking section is rewritten automatically whenever `state.py` is called with:

| Command | When it runs |
|---------|-------------|
| `state init` | Loop starts — creates the sentinel and initial status table |
| `state set-baseline` | Baseline recorded — adds baseline metrics |
| `state start-iteration` | Iteration created — appears in Active Experiments |
| `state launch-iteration` | Experiment launched — shows as "training" in Active Experiments |
| `state complete-iteration` | Iteration done — moves to Iteration Log with metrics |
| `state fail-iteration` | Iteration failed — marked as FAILED in Iteration Log |
| `state add-iteration` | Iteration completed (shortcut) — appends to the iteration log |
| `state update-progress` | Manual refresh — e.g., to set a "current direction" note |

### What gets tracked

Below the sentinel (`<!-- AGENT PROGRESS BELOW -->`), the agent writes:

- **Status table** — primary metric, baseline value, current best (with iteration number), iteration counts by status, start time
- **Active Experiments** — iterations currently in `coding` or `running` status, with time since creation
- **Current direction** — optional note on what the agent is trying next
- **Baseline** — checkpoint path and all baseline metrics
- **Iteration log** — table with every iteration: change summary, metric value (or status label), delta vs baseline, feedback
- **Recent iterations (detail)** — last 3 iterations expanded with hypothesis, papers cited, checkpoint path, and full metrics

### Example

After 3 completed iterations and 2 active experiments, `progress.md` looks like:

```markdown
# Research Goal

Improve heart segmentation 3D Dice above 0.92.

<!-- AGENT PROGRESS BELOW — auto-updated, do not edit below this line -->

## Status

| | |
|---|---|
| **Primary metric** | `test_3d_dice` |
| **Baseline** | 0.905 |
| **Best** | 0.918 (iter 3) |
| **Iterations** | 3 completed, 2 active |
| **Started** | 2026-02-20 10:00:00 |

> **Current direction:** Combining token-wise FiLM with increased bias scale

## Active Experiments

- **Iter 4** [coding] (0.3h ago) — enable grouped nullspace bias
- **Iter 5** [training] (2.1h ago) — increase spd_rank to 8 (`checkpoints/exp5`)

## Baseline
- Checkpoint: `checkpoints/baseline`
- test_3d_dice: **0.905**

## Iteration Log

| # | Change | test_3d_dice | vs baseline | Feedback |
|---|--------|---|------------|----------|
| 1 | spd_rank 4->8 | 0.908 | +0.0030 | marginal gain |
| 2 | enable tokenwise FiLM | 0.912 | +0.0070 | promising |
| 3 | bias_max_scale 0.05->0.1 | 0.918 | +0.0130 | new best |
| 4 | enable grouped nullspace bias | coding... | coding... |  |
| 5 | increase spd_rank to 8 | running... | running... |  |

## Recent Iterations (detail)

### Iteration 5 [running] — 2026-02-20 16:00:00
- **Hypothesis:** Higher SPD rank adds expressiveness
- **Change:** increase spd_rank to 8
- **Checkpoint:** `checkpoints/exp5`
- **Feedback:** N/A

### Iteration 4 [coding] — 2026-02-20 16:30:00
- **Hypothesis:** Grouped nullspace enables finer control
- **Change:** enable grouped nullspace bias
- **Checkpoint:** `N/A`
- **Feedback:** N/A

### Iteration 3 — 2026-02-20 14:30:00
- **Hypothesis:** Larger bias scale allows more adaptation capacity
- **Change:** bias_max_scale 0.05->0.1
- **Papers:** Nullspace Tuning 2024
- **Checkpoint:** `checkpoints/exp3`
- **Metrics:** {"test_3d_dice": 0.918, "test_3d_nsd": 0.952}
- **Feedback:** new best

*Last updated: 2026-02-20 16:35:00*
```

The user can `cat progress.md` at any time (or view it in a file browser) to see the full state of the research loop without needing to parse JSON or run commands.

---

## Git Workflow

```
main                          ← best configuration (merged after each new best)
├── iter/1-spd-rank-increase  ← 2 commits: code + results
├── iter/2-tokenwise-film
└── iter/3-film-bias-scale
```

Each iteration: `branch-start` → `commit-code` → experiment → `commit-results` → (if best) `merge-best`

---

## State File Schema

`state.json` — persists across context compression and session restarts.

```json
{
  "goal": "Improve heart segmentation 3D Dice above 0.92",
  "project_dir": "/path/to/project",
  "created_at": "2026-02-20 10:00:00",
  "primary_metric": "test_3d_dice",
  "baseline": {
    "checkpoint": "checkpoints/baseline",
    "metrics": {"test_3d_dice": 0.905, "test_3d_nsd": 0.940}
  },
  "best": {
    "iteration": 3,
    "metrics": {"test_3d_dice": 0.921},
    "experiment": "tokenwise film + bias scale"
  },
  "iterations": [
    {
      "id": 1,
      "status": "completed",
      "created_at": "2026-02-20 10:30:00",
      "timestamp": "2026-02-20 11:45:00",
      "hypothesis": "Increasing SPD rank adds expressiveness",
      "change_summary": "spd_rank 4->8",
      "papers_referenced": ["LoRA 2021"],
      "checkpoint": "checkpoints/exp1",
      "metrics": {"test_3d_dice": 0.908},
      "feedback": "marginal gain"
    },
    {
      "id": 2,
      "status": "running",
      "created_at": "2026-02-20 11:00:00",
      "timestamp": "2026-02-20 11:30:00",
      "hypothesis": "Token-wise FiLM enables per-token adaptation",
      "change_summary": "enable cond_scale_tokenwise",
      "papers_referenced": [],
      "checkpoint": "checkpoints/exp2",
      "metrics": {},
      "feedback": ""
    }
  ]
}
```

**Iteration fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Sequential iteration number |
| `status` | string | `coding` \| `running` \| `completed` \| `failed` |
| `created_at` | string | When the iteration was created (start-iteration) |
| `timestamp` | string | Last status change time |
| `hypothesis` | string | What you expected |
| `change_summary` | string | What was changed |
| `papers_referenced` | list | Cited papers |
| `checkpoint` | string | Checkpoint directory path |
| `metrics` | dict | Results (populated on complete-iteration) |
| `feedback` | string | Human/agent feedback |

**Backward compatibility:** Old iterations without `status` are treated as `completed`.
```

---

## Customization

```bash
# Different metric
python -m research_agent.state init --progress progress.md --metric val_loss

# Override file locations
export RESEARCH_STATE_FILE=my_state.json
export RESEARCH_PROGRESS_FILE=my_progress.md
```

For git tracking, configure a remote: `git remote add origin https://...`

---

## Rules (for Claude)

1. **ONE change per iteration** — isolate variables
2. **NEVER overwrite checkpoints** — unique directory per iteration
3. **Create branch + commit BEFORE experiments** — code must be in git first
4. **Re-read state.json** every iteration — recover context after compression
5. **Review code implementation's changes** — always `git diff` before committing
6. **Push after every commit** — keep remote in sync
7. **Never edit the user's goal** in `progress.md`
8. **Cite papers** when techniques come from literature
9. **Present clear summaries** — user is watching in tmux
