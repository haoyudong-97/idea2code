# Research Agent

> Once people said "Talk is cheap. Show me the code." But now in the era of vibe coding, I think the reverse might be true: your ability to create a new idea is far more important than being able to implement it.
>
> With this idea in mind, this project is created to accelerate the idea-to-real-code step.

A project-agnostic autonomous research loop for Claude Code. Give one idea, get a results summary.

```
/auto-research <your idea here>
```

That's it. The agent fetches papers, selects an approach, implements code, runs the experiment, and presents you with a full results summary.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Pipeline Steps (Detail)](#pipeline-steps-detail)
- [Installation](#installation)
- [Skills (Slash Commands)](#skills-slash-commands)
- [Architecture](#architecture)
- [Components](#components)
- [State & Progress Tracking](#state--progress-tracking)
- [Git Workflow](#git-workflow)
- [CLI Reference](#cli-reference)
- [Customization](#customization)

---

## Quick Start

```bash
# In Claude Code, just type:
/auto-research improve segmentation accuracy using attention-based boundary refinement
```

The full pipeline runs automatically:

1. **Load context** — reads `state.json` and `progress.md` for goal, baseline, iteration history
2. **Fetch papers** — searches arXiv RSS + API and Semantic Scholar for relevant papers
3. **Generate ideas** — Agent subagent digests papers and proposes 3-5 research ideas
4. **Select approach** — picks the best idea based on relevance, feasibility, and novelty
5. **Git setup** — creates iteration branch, registers iteration in state (`coding` status)
6. **Implement code** — Agent subagent reads codebase and makes surgical edits
7. **Review + commit code** — shows diff, commits code changes, pushes
8. **Run experiment** — launches training via `run_and_wait.sh`, polls for completion
9. **Analyze results** — extracts metrics, compares to baseline and previous best
10. **Record results** — `complete-iteration` (or `fail-iteration`), updates `progress.md`
11. **Commit results + merge** — commits results, merges to main if new best, pushes
12. **Present summary** — hypothesis, changes, metrics, verdict, suggestion for next iteration

---

## Pipeline Steps (Detail)

Here's exactly what `/auto-research <idea>` does under the hood:

### Step 0: Load Context

Reads `state.json` (goal, baseline, best result, iteration history) and `progress.md` (user's goal and constraints). If no state exists, initializes one from the idea.

```bash
python -m research_agent.state read    # recover full context
head -30 progress.md                   # check user's notes
```

### Step 1: Fetch Papers

Calls arXiv RSS + API and Semantic Scholar to find relevant papers. Pure Python — no Claude needed, always works.

```bash
python research_agent/idea_discovery.py \
  --categories <inferred> --days 7 --s2-query "<idea>" \
  --fetch-only --papers-output results/recent_papers.json
```

Fallback: `search_papers.py "<idea>" results/recent_papers.json --limit 15`

### Step 2: Generate Ideas + Select Approach

**2a.** An Agent subagent reads the fetched papers and proposes 3-5 concrete research ideas with hypothesis, approach, expected impact, and difficulty. Output: `results/ideas.json`.

**2b.** The orchestrator selects ONE idea based on relevance, feasibility, novelty (vs previous iterations), and concreteness. Tells the user which approach and why.

### Step 3: Git Setup + Register Iteration

Creates a dedicated branch and registers the iteration in state:

```bash
python -m research_agent.git_ops branch-start --iteration <N> --change "<description>"
python -m research_agent.state start-iteration --hypothesis "..." --change "..."
```

State moves to `coding` status. Shows in `progress.md` Active Experiments.

### Step 4: Implement Code

An Agent subagent receives a detailed prompt with the instruction, project context, papers, and key files. It reads the codebase, makes surgical edits, and writes a summary to `results/impl_summary.json`.

### Step 5: Review + Commit Code

Shows `git diff` and briefly explains what changed. Then commits and pushes:

```bash
python -m research_agent.git_ops commit-code --iteration <N> \
  --hypothesis "..." --change "..." --papers "..."
python -m research_agent.git_ops push
```

### Step 6: Discover Experiment Script

Finds the training script to run by checking (in order):
1. `progress.md` — look for script path or "How to run" section
2. `state.json` — checkpoint path patterns from previous iterations
3. File search — `train*.sh`, `train*.py`, `scripts/` directory
4. Ask the user if not found

### Step 7: Run Experiment

Marks iteration as running and launches the experiment in background:

```bash
python -m research_agent.state launch-iteration --id <N> --checkpoint "checkpoints/iter_<N>"
bash research_agent/run_and_wait.sh <script> checkpoints/iter_<N>
```

Polls `checkpoints/iter_<N>/.done` for completion. State moves to `running` status.

### Step 8: Analyze Results

Reads the exit code from `.done` and extracts metrics from checkpoint dir / training log.

- **Success:** extracts primary metric value + secondary metrics
- **Failure:** reads `training.log` tail for error diagnosis

### Step 9: Record Results

Updates state and `progress.md`:

```bash
# On success:
python -m research_agent.state complete-iteration --id <N> \
  --metric-name <metric> --metric-value <value> --feedback "..."

# On failure:
python -m research_agent.state fail-iteration --id <N> --feedback "<error>"
```

### Step 10: Commit Results + Merge

```bash
python -m research_agent.git_ops commit-results --iteration <N> --state state.json
python -m research_agent.git_ops push
```

If this iteration is the new best:
```bash
python -m research_agent.git_ops merge-best --state state.json
python -m research_agent.git_ops push
```

### Step 11: Present Results Summary

```
## Results: Iteration <N>

Idea: <title>
Hypothesis: <what we expected>
Papers: <cited papers>

Changes: <description>
  Files modified: model.py, config.py

Results:
  test_3d_dice: 0.918 (baseline: 0.905, delta: +0.013)

Verdict: NEW BEST

Suggestion: Try combining this with token-wise adaptation
```

---

## Installation

### Step 1: Copy the package into your project

```bash
cp -r research_agent/ /path/to/your/project/
```

Or use PYTHONPATH:
```bash
export PYTHONPATH="/path/to/parent/of/research_agent:$PYTHONPATH"
```

### Step 2: Install the skills (slash commands)

Copy the `.claude/skills/` directory into your project:

```bash
cp -r .claude/skills/ /path/to/your/project/.claude/skills/
```

This adds four slash commands: `/auto-research`, `/find-papers`, `/implement`, `/combine-findings`.

### Step 3: Append the protocol to your CLAUDE.md

```bash
cat research_agent/protocol.md >> /path/to/your/project/CLAUDE.md
```

### Step 4: Create progress.md (optional, for research loops)

```bash
cat > progress.md << 'EOF'
# Research Goal

Improve heart segmentation 3D Dice above 0.92 using adapter architecture changes.

## Constraints
- Keep parameter count under 1M
- Must converge within 200 epochs
EOF
```

### Step 5: Start using

```bash
cd /path/to/your/project
claude
# Then type: /auto-research <your idea>
```

---

## Skills (Slash Commands)

### `/auto-research <idea>` — Full Research Cycle

The main command. Takes a rough idea and delivers a results summary.

```
/auto-research use boundary-aware loss to improve segmentation edges
/auto-research try token-wise FiLM conditioning for adapter layers
/auto-research explore attention gating for skip connections
```

**Full pipeline:**

| Step | What happens | How |
|------|-------------|-----|
| 0. Load context | Read `state.json` + `progress.md` | `python -m research_agent.state read` |
| 1. Fetch papers | Search arXiv + Semantic Scholar | `idea_discovery.py --fetch-only` (pure Python) |
| 2a. Generate ideas | Digest papers, propose ideas | Agent subagent → `results/ideas.json` |
| 2b. Select approach | Pick best idea | Orchestrator judgment |
| 3. Git setup | Create branch, register iteration | `git_ops branch-start` + `state start-iteration` |
| 4. Implement code | Read code, make edits | Agent subagent → `results/impl_summary.json` |
| 5. Review + commit | `git diff`, commit, push | `git_ops commit-code` + `git_ops push` |
| 6. Discover script | Find experiment/training script | Check progress.md, state, or ask user |
| 7. Run experiment | Launch training, poll | `state launch-iteration` + `run_and_wait.sh` |
| 8. Analyze results | Extract metrics from output | Read checkpoint dir / training log |
| 9. Record results | Update state + progress.md | `state complete-iteration` or `fail-iteration` |
| 10. Commit + merge | Commit results, merge if best | `git_ops commit-results` + `merge-best` |
| 11. Present summary | Show metrics, verdict, next steps | Orchestrator output |

**Fallback chain:** If paper fetching fails, degrades gracefully (idea_discovery → search_papers → WebSearch → raw idea). Implementation always uses the Agent tool.

### `/find-papers <topic>` — Search Literature

Search for papers and generate research ideas.

```
/find-papers medical image segmentation transformers
/find-papers attention mechanisms --days 7
/find-papers PEFT adapters --categories machine-learning --fetch-only
```

**Steps:** fetch papers (pure Python) → present to user → generate ideas (Agent subagent) → offer to implement

### `/implement <instruction>` — Full Implementation Cycle

Implement a specific code change and run the experiment.

```
/implement increase spd_rank from 4 to 8
/implement add dropout after the adapter layer
/implement apply idea 3 from the last paper search
```

**Steps:** parse instruction → git branch → implement (Agent subagent) → commit → run experiment → analyze → record results → present summary

### `/combine-findings <input>` — Integrate New Input

Combine a paper, idea, or literature search with current research state.

```
/combine-findings https://arxiv.org/abs/2401.12345
/combine-findings try orthogonal regularization on adapter weights
/combine-findings find related literature
```

**Input types:**
- **Paper URL** — fetches paper, extracts key ideas, proposes hypothesis
- **Rough idea** — formulates hypothesis combining idea with current state
- **"find related literature"** — searches for papers, user picks, then implements

---

## Architecture

The research agent uses a clean separation between **pure Python** (API calls, state, git) and **Agent subagents** (reasoning, code implementation):

```
Claude Code Session
├── Orchestrator (you / skill instructions)
│   ├── Reads state, selects approaches, manages git
│   └── Presents results, asks for user feedback
│
├── Pure Python Scripts (always safe, no Claude needed)
│   ├── idea_discovery.py --fetch-only  → arXiv RSS + API + Semantic Scholar
│   ├── search_papers.py               → fallback paper search
│   ├── state.py                       → JSON state + progress.md updates
│   └── git_ops.py                     → branch/commit/merge per iteration
│
└── Agent Subagents (Claude Code's native mechanism)
    ├── Idea Generation  → digests papers, proposes research ideas
    └── Code Implementation → reads code, makes surgical edits
```

**Why Agent subagents?** Claude Code's Agent tool spawns isolated subagents with full tool access (Read/Edit/Write/Bash/Grep/Glob). This avoids the nesting issues of `claude -p` while keeping implementation work separate from orchestration.

**Fallback chain:** If paper fetching fails, the pipeline degrades gracefully — from full paper context down to using just the raw idea. Implementation always goes through the Agent tool.

---

## Components

| File | Purpose |
|------|---------|
| `idea_discovery.py` | Paper fetching (arXiv RSS + API, Semantic Scholar) + Claude worker for idea generation |
| `search_papers.py` | Fallback paper search via Semantic Scholar + arXiv APIs (no Claude needed) |
| `state.py` | Persistent JSON state + auto-updates `progress.md` |
| `git_ops.py` | Branch per iteration, structured commits, merge best to main |
| `run_and_wait.sh` | Experiment runner with `.done` completion marker |
| `protocol.md` | Research loop protocol (append to your project's CLAUDE.md) |
| `archive/` | Deprecated scripts (`code_implementation.py`, `literature_search.py`) — kept for reference only |

## Project Structure

```
your_project/
├── CLAUDE.md                    # Protocol instructions (appended from protocol.md)
├── .claude/skills/              # Slash command definitions
│   ├── auto-research/SKILL.md
│   ├── find-papers/SKILL.md
│   ├── implement/SKILL.md
│   └── combine-findings/SKILL.md
├── progress.md                  # Your goal + auto-updated tracking dashboard
├── state.json                   # Machine-readable state (created at runtime)
└── research_agent/
    ├── idea_discovery.py        # Paper fetching + idea generation
    ├── search_papers.py         # Fallback paper search
    ├── state.py                 # State management + progress.md auto-updates
    ├── git_ops.py               # Git branching, commits, merges per iteration
    ├── run_and_wait.sh          # Experiment runner
    ├── protocol.md              # Source protocol
    └── archive/                 # Deprecated (kept for reference)
        ├── code_implementation.py
        └── literature_search.py
```

---

## State & Progress Tracking

### progress.md

The human-readable dashboard with two sections:

1. **Your goal** (top) — you write this. The agent never touches it.
2. **Agent tracking** (bottom) — auto-generated below `<!-- AGENT PROGRESS BELOW -->`. Updated after every action.

### state.json

Machine-readable state with goal, baseline, best result, and full iteration history. Persists across context compression and session restarts.

### Iteration Lifecycle

| Command | From | To | When |
|---------|------|----|------|
| `start-iteration` | *(new)* | `coding` | After branch creation, before coding |
| `launch-iteration` | `coding` | `running` | After commit, before experiment |
| `complete-iteration` | `running` | `completed` | After experiment succeeds |
| `fail-iteration` | `coding`/`running` | `failed` | On error (OOM, NaN, abandoned) |
| `add-iteration` | *(new)* | `completed` | Shortcut: one-step create + complete |

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

## CLI Reference

### state.py

```bash
python -m research_agent.state init --progress progress.md --metric test_3d_dice
python -m research_agent.state read
python -m research_agent.state set-baseline --checkpoint "..." --metrics '{"test_3d_dice": 0.905}'
python -m research_agent.state start-iteration --hypothesis "..." --change "..."
python -m research_agent.state launch-iteration --id 3 --checkpoint "checkpoints/exp3"
python -m research_agent.state complete-iteration --id 3 --metric-name test_3d_dice --metric-value 0.912
python -m research_agent.state fail-iteration --id 3 --feedback "OOM error"
```

### git_ops.py

```bash
python -m research_agent.git_ops branch-start --iteration 3 --change "enable tokenwise film"
python -m research_agent.git_ops commit-code --iteration 3 --hypothesis "..." --change "..."
python -m research_agent.git_ops commit-results --iteration 3 --state state.json
python -m research_agent.git_ops merge-best --state state.json
python -m research_agent.git_ops push
python -m research_agent.git_ops log
```

### idea_discovery.py

```bash
# Fetch papers only (pure Python, always safe)
python research_agent/idea_discovery.py --categories cs.CV,eess.IV --days 3 --fetch-only

# With Semantic Scholar search
python research_agent/idea_discovery.py --categories cs.CV --days 3 \
  --s2-query "medical image segmentation" --fetch-only

# Category aliases: medical-imaging, computer-vision, machine-learning, ai, nlp, robotics
```

### search_papers.py

```bash
python research_agent/search_papers.py "query" --limit 10 --year-min 2023
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

---

## Rules (for Claude)

1. **ONE change per iteration** — isolate variables
2. **NEVER overwrite checkpoints** — unique directory per iteration
3. **Create branch + commit BEFORE experiments** — code must be in git first
4. **Re-read state.json** every iteration — recover context after compression
5. **Review changes** — always `git diff` before committing
6. **Push after every commit** — keep remote in sync
7. **Never edit the user's goal** in `progress.md`
8. **Cite papers** when techniques come from literature
9. **NEVER call archived scripts** (`code_implementation.py`, `literature_search.py`) — use Agent tool instead
10. **Final output is always a results summary** — not just a diff
