## Research Loop Protocol

When asked to start a research loop, follow this protocol. You are running in a **live tmux session** — the user can watch your progress, detach/reattach, and provide feedback.

### CRITICAL: Delegation Rules

**You are the ORCHESTRATOR only. You MUST delegate actual work to worker processes.**

**DO NOT recreate the research_agent package.** It already exists and is tested. Use it via PYTHONPATH or symlink. If `research_agent/` is a symlink or directory in the project, use it directly. If not, set `export PYTHONPATH="/path/to/parent/of/research_agent:$PYTHONPATH"`.

1. **For paper search**: ALWAYS call `python research_agent/literature_search.py` via Bash. Do NOT use your own WebSearch tool directly.
2. **For code implementation**: ALWAYS call `python research_agent/code_implementation.py` via Bash. Do NOT use your own Read/Edit/Write tools to modify project code directly.
3. **NEVER write or recreate** `research_agent/*.py` files. They are maintained externally.
4. **Your job**: Read state, decide what to try, call literature search / code implementation, review their output (`git diff`), run git_ops, launch experiments, analyze results, and communicate with the user.

The reason: literature search and code implementation spawn **separate Claude Code workers** as background processes. This prevents your context from getting bloated with code details and provides clean separation between orchestration and execution.

### Architecture

You (the orchestrator) run in tmux **window 0**. Worker Claude Code sessions run as **background processes** — they are independent processes that can read/edit/search without nesting issues.

```
tmux session "research"
  └── window 0: You (orchestrator) — controls the loop, reads results

Background workers (launched automatically):
  - claude -p for literature search (paper search)
  - claude -p for code implementation (code changes)
  - claude -p for idea discovery (trend digest)
```

Workers are launched automatically by the Python scripts as background processes. No API key needed — everything uses your Claude subscription.

### Operating Modes

The loop supports two modes, set by the user at startup or changed between iterations:

- **Autonomous mode**: After each iteration, analyze results and auto-decide the next experiment. Continue without waiting for user input. Stop only when the goal is reached, the metric plateaus for 3+ iterations, or you are unsure what to try.
- **Interactive mode** (default): After each iteration, present a summary and **wait for user feedback** before continuing.

The user can switch modes at any time by saying "continue autonomously" or "wait for my feedback".

### Core Functions

- **Idea Discovery** (`idea_discovery.py`): Fetches recent papers from arXiv RSS + Semantic Scholar, sends them to a Claude worker that digests trends and proposes research ideas. Use this when the user asks to explore what's new in their field or needs fresh inspiration.
- **Literature Search** (`literature_search.py`): Spawns a Claude Code worker as a background process → uses WebSearch to find papers → returns ranked JSON.
- **Code Implementation** (`code_implementation.py`): Spawns a Claude Code worker as a background process → reads code, plans edits, modifies files → returns change summary JSON.

These are called by you (the orchestrator) via Bash. They handle tmux pane creation and polling internally.

### Idea Discovery Flow

When the user asks to explore recent papers or wants fresh research ideas, use `idea_discovery.py` **before** entering the iteration loop:

1. **Fetch recent papers:**
   ```
   python research_agent/idea_discovery.py --categories cs.CV,eess.IV --days 7 \
     --state state.json --progress progress.md
   ```
   Category aliases: `medical-imaging`, `computer-vision`, `machine-learning`, `ai`, `nlp`, `robotics`.

2. **Present the ideas** to the user (read `results/ideas.json`). Each idea includes a title, hypothesis, approach, expected impact, and difficulty.

3. **Wait for user feedback** — the user picks an idea (or modifies one).

4. **Transition to the iteration loop** — use the chosen idea as the basis for literature search (`--auto` or explicit topic) and code implementation (`--instruction`).

### progress.md

`progress.md` is the shared dashboard between you and the user. It has two sections separated by a sentinel line:

- **Above the sentinel** — the user's section. They write the initial goal here, and can edit it anytime to change direction, add constraints, or leave notes for you. **Read this at the start of every iteration** — the user may have updated it.
- **Below the sentinel** — your tracking section. Auto-updated by `state.py` after `init`, `set-baseline`, `add-iteration`, and `update-progress`. Never edit this manually.

**User creates:**
```markdown
# Research Goal

Improve heart segmentation 3D Dice above 0.92 using adapter architecture changes.

## Constraints
- Keep parameter count under 1M
- Must converge within 200 epochs
```

The user can edit their section anytime — for example adding "Focus on nullspace bias next" or "Stop after iteration 5". You must check for such changes at the start of each iteration.

**Agent updates everything below** `<!-- AGENT PROGRESS BELOW -->` automatically via `state.py`.

### Git Tracking

Every iteration is tracked as a **git branch** with structured commits. This gives full traceability — `git log` shows every hypothesis and result, `git diff` between iterations shows exactly what changed.

**Branch structure:**
```
main                          ← always has the best-performing code
├── iter/1-spd-rank-increase  ← branch per iteration
├── iter/2-tokenwise-film     ← each has 2 commits: code + results
└── iter/3-bias-scale-tuning
```

**Each iteration creates 2 commits:**
1. **Code commit** (before experiment) — records hypothesis, change, papers
2. **Results commit** (after experiment) — records metrics, delta vs baseline

**Best iteration merges to main**, so `main` always reflects the top configuration.

### Setup (first time only)

1. Read the user's `progress.md` to understand the goal.
2. Initialize state from it:
   ```
   python -m research_agent.state init --progress progress.md --metric "<primary_metric>"
   ```
3. Identify baseline: read existing results, record in state:
   ```
   python -m research_agent.state set-baseline --checkpoint "<path>" --metrics '{"metric": value}'
   ```
   (This auto-updates `progress.md`.)

### Each Iteration

1. **Read state and progress** — recover full context after compression:
   ```
   python -m research_agent.state read
   cat progress.md
   ```
   Always read `progress.md` too — the user may have edited the goal, added constraints, or left notes for you above the sentinel line.

2. **Decide what to try** — the change can come from different sources:
   - **User instruction** — the user told you exactly what to try (skip literature search, go to code implementation with `--instruction`).
   - **Previous results** — analysis of the last iteration suggests an obvious next step (skip literature search).
   - **New technique needed** — call literature search first.
   - **Explore recent work** — if the user asks to see what's new, or after 3+ plateaued iterations, run idea discovery first.

3. **(Optional) Literature search:**
   ```
   python research_agent/literature_search.py "orthogonal adapter fine-tuning" \
     results/search_iter3.json --state state.json
   ```
   Or auto-generate the topic from the last iteration:
   ```
   python research_agent/literature_search.py --auto results/search_iter3.json --state state.json
   ```
   - Spawns a Claude Code worker as a background process.
   - Worker uses WebSearch to find papers, returns ranked JSON.
   - Auto-deduplicates against papers already used in previous iterations.
   - Script polls for completion and returns results.
   - Skip when the user gives a specific instruction or the next step is obvious.

4. **Create branch** (BEFORE implementing changes):
   ```
   python -m research_agent.git_ops branch-start --iteration 3 --change "enable tokenwise film"
   ```

5. **Register the iteration** — create a state entry so `progress.md` shows it as active:
   ```
   python -m research_agent.state start-iteration \
     --hypothesis "Token-wise FiLM enables per-token adaptation" \
     --change "enable cond_scale_tokenwise"
   ```
   This creates the iteration in `coding` status. The user can see it in the Active Experiments section of `progress.md`.

6. **Code implementation — implement the change:**
   ```
   # From papers:
   python research_agent/code_implementation.py --papers results/search_iter3.json \
     --project-dir . --state state.json \
     --files models/sam/modeling/common.py

   # Or from direct instruction:
   python research_agent/code_implementation.py --instruction "increase spd_rank to 8" \
     --project-dir . --state state.json
   ```
   - Spawns a Claude Code worker as a background process.
   - Worker reads code, plans edits, modifies files directly.
   - Returns JSON summary: `{hypothesis, change_summary, files_modified, papers_used}`.

7. **Review changes** — read what code implementation modified, verify correctness:
   ```
   git diff
   ```

8. **Commit code** (before experiment):
   ```
   python -m research_agent.git_ops commit-code --iteration 3 \
     --hypothesis "..." --change "..." --papers "..." \
     --checkpoint "checkpoints/exp_..."
   python -m research_agent.git_ops push
   ```

9. **Launch iteration** — mark as running and start the experiment:
   ```
   python -m research_agent.state launch-iteration --id 3 --checkpoint "checkpoints/exp3"
   bash research_agent/run_and_wait.sh <script> <checkpoint_dir>
   ```
   The iteration moves to `running` status. `progress.md` now shows it as "training" in Active Experiments.

10. **Poll** — check completion every ~10 minutes:
    ```
    test -f <checkpoint_dir>/.done && cat <checkpoint_dir>/.done || echo RUNNING
    ```

11. **Analyze** — read results, compare with baseline and previous best.

12. **Complete (or fail) the iteration:**

    On success:
    ```
    python -m research_agent.state complete-iteration --id 3 \
      --metric-name <name> --metric-value <value> \
      --feedback "..."
    ```

    On failure (OOM, NaN loss, etc.):
    ```
    python -m research_agent.state fail-iteration --id 3 --feedback "OOM error"
    ```

    Both auto-update `progress.md`. The user can `cat progress.md` at any time to see the full research history.

    > **Shortcut:** For simple iterations without lifecycle tracking, `add-iteration` still works and atomically creates + completes an iteration in one step.

13. **Commit results:**
    ```
    python -m research_agent.git_ops commit-results --iteration 3 --state state.json
    python -m research_agent.git_ops push
    ```

14. **If new best → merge to main** and push:
    ```
    python -m research_agent.git_ops merge-best --state state.json
    python -m research_agent.git_ops push
    ```

15. **Summarize** — present results and proposed next steps to user.

16. **Offer literature exploration** — at the end of every iteration, fetch today's arXiv titles (free, no Claude worker) and present them:

    ```
    python research_agent/idea_discovery.py --categories medical-imaging --days 1 --fetch-only
    ```

    Then show the user the paper titles from `results/recent_papers.json` and ask:

    > Here are today's arXiv papers in your field (N papers). Any of these look relevant?
    > I can run a full idea digest on them if you'd like (uses Claude worker), or we can continue to the next iteration.

    **Three paths:**
    - **User picks a paper** → use it directly as inspiration for the next iteration (literature search or code implementation with `--instruction`).
    - **User wants full digest** → run idea discovery WITHOUT `--fetch-only` to spawn the Claude worker and generate structured ideas.
    - **User declines** → proceed directly to the next iteration.

17. **Next iteration decision:**
    - **Interactive mode:** Wait for user feedback before continuing.
    - **Autonomous mode:** Auto-decide the next step based on results:
      - **Improved?** → Build on it (vary the same knob, combine with another).
      - **Regressed?** → Revert to best config, try a different direction.
      - **Plateaued (3+ iters)?** → Call literature search for fresh ideas, or stop and ask the user.
      - **Goal reached?** → Stop and present final summary.
      - **Unsure?** → Stop and ask the user for direction.

### Concurrent Iterations

You can overlap iterations — start coding iter N+1 while iter N trains. This is especially useful when experiments take hours.

**Pattern:**
```
Iter 3: start → code → commit → launch-iteration → [training...]
                                                      ↑ while this runs:
Iter 4: start → code → commit → launch-iteration → [training...]
                                      ↑ Iter 3 completes: complete-iteration --id 3
```

**Rules for concurrent iterations:**
- Each iteration still gets its own git branch (`branch-start` switches branches, so commit iter N's code before starting iter N+1's branch).
- Each iteration gets a unique checkpoint directory — never share checkpoints.
- `progress.md` shows all active experiments in the Active Experiments section.
- Complete or fail iterations as they finish, in any order.
- Best tracking updates correctly regardless of completion order.

### Autonomous Decision Guidelines

When running autonomously, use these heuristics to decide what to try next:

1. **Read the full iteration history** from state.json — look for trends, not just the last result.
2. **If the last change helped:** Try a variant (e.g., helped with rank 4 → try rank 8) or combine it with the second-best change.
3. **If the last change hurt or was neutral:** Revert to the best config and try something orthogonal (different component, different technique).
4. **After 3+ iterations without improvement:** Call literature search with `--auto` to search for new ideas. If still stuck, stop and ask the user.
5. **Log your reasoning** in the `--feedback` field so the user can review your thought process.

### Git Commands Reference

All commands run via `python -m research_agent.git_ops <command>`:

| Command | When | What it does |
|---------|------|-------------|
| `branch-start --iteration N --change "..."` | Before code implementation | Creates `iter/N-slug` from main |
| `commit-code --iteration N --hypothesis "..." --change "..."` | After code implementation, before experiment | Commits code with structured message |
| `commit-results --iteration N --state state.json` | After experiment results | Commits with metrics + delta vs baseline |
| `merge-best --state state.json` | When new best found | Merges best branch into main |
| `push` | After commit or merge | Pushes current branch to remote |
| `push-all` | Periodically | Pushes main + all iter branches |
| `log` | Anytime | Shows all iteration commits |

### Rules

- **NEVER implement code changes yourself** — ALWAYS use `python research_agent/code_implementation.py` via Bash. This spawns a worker as a background process.
- **NEVER search for papers yourself** — ALWAYS use `python research_agent/literature_search.py` via Bash. This spawns a worker as a background process.
- **ONE principal change per iteration** — isolate variables for clean comparison.
- **NEVER overwrite previous checkpoints** — each iteration gets a unique checkpoint directory.
- **ALWAYS create branch + commit before running experiments** — code changes must be in git before any long-running job starts.
- **Re-read state.json** at the start of every iteration to recover context.
- **Primary metric drives decisions**; always report secondary metrics too.
- **Save experiment scripts** — each iteration's script should be reproducible.
- **Cite papers** — when a technique comes from literature, note the reference.
- **Update `progress.md`** via `state.py` after every iteration — this is the user's live dashboard. Never edit the user's goal section above the sentinel, but always keep the tracking section below it current.
- **Push after every commit** — keep remote in sync so nothing is lost.
- **Present clear summaries** — the user is watching in tmux, make status updates readable.
- **Review code implementation's changes** — always `git diff` after code implementation before committing.
