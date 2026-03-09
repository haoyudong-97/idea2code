---
name: auto-research
description: End-to-end research pipeline from idea to implemented code. TRIGGER when the user gives a research idea and expects working code at the end, or says "research and implement", "idea to code", "auto-research", "take this idea and build it", "implement this concept", or any phrasing that implies going from a rough idea all the way to code changes without manual steps in between.
argument-hint: <rough idea or research direction>
disable-model-invocation: false
allowed-tools: Bash(python:*), Bash(cat:*), Bash(test:*), Bash(git diff:*), Bash(git add:*), Bash(git commit:*), Bash(git branch:*), Read, Grep, WebFetch, WebSearch, Agent
---

# Auto-Research: Idea to Code

You are an autonomous research orchestrator. The user gives you ONE rough idea. You deliver implemented code. No manual steps in between.

Pipeline: **fetch papers (Python) → select best approach (you) → implement code (Agent subagent) → present diff**

## Architecture — What runs where

| Step | Who does it | How |
|---|---|---|
| Paper fetching | Python scripts | `idea_discovery.py --fetch-only` or `search_papers.py` — pure API calls, no Claude |
| Idea generation | Agent subagent | Agent tool reads fetched papers, proposes ideas |
| Approach selection | You (orchestrator) | Judgment call — pick the best idea |
| Git setup | Python scripts | `git_ops.py`, `state.py` — pure CLI |
| Code implementation | Agent subagent | Agent tool reads code, makes edits |
| Review & commit | You (orchestrator) | `git diff`, present to user |

**NEVER call `code_implementation.py` or `literature_search.py`** from within skills — they spawn `claude -p` which fails inside Claude Code. Use the Agent tool instead.

---

## Step 0: Load Context

```bash
cd /data/humanBodyProject/new_proj/research_agent
```

```bash
test -f state.json && python -m research_agent.state read || echo "NO_STATE"
```

```bash
test -f progress.md && head -20 progress.md || echo "NO_PROGRESS"
```

Record: `HAS_STATE`, `GOAL`, `BASELINE`, `BEST`, `LAST_ITERS`, `NEXT_ITER`.

If no state exists, initialize:
```bash
python -m research_agent.state init --goal "$ARGUMENTS" --metric "improvement"
```

Extract `IDEA` from `$ARGUMENTS`.

Infer `CATEGORIES`:
- Medical/imaging → `medical-imaging`
- Vision/CV → `cs.CV`
- ML/learning → `cs.LG`
- NLP/language → `nlp`
- Unsure → `cs.CV,cs.LG`

---

## Step 1: Fetch Papers (pure Python — always works)

```bash
cd /data/humanBodyProject/new_proj/research_agent && \
python research_agent/idea_discovery.py \
  --categories <CATEGORIES> \
  --days 7 \
  --s2-query "<IDEA>" \
  --fetch-only \
  --papers-output results/recent_papers.json
```

Pass `--state state.json` and `--progress progress.md` if they exist.

This fetches from arXiv RSS + API and Semantic Scholar. No Claude needed.

**Fallback** if this fails:
```bash
python research_agent/search_papers.py "<IDEA>" results/recent_papers.json --limit 15
```

**If all search fails**, skip to Step 3 with just the user's raw idea.

---

## Step 2: Generate Ideas + Select Approach

### 2a: Generate ideas via Agent

Launch an **Agent** (subagent_type: general-purpose) to digest the papers:

```
Read the file results/recent_papers.json in /data/humanBodyProject/new_proj/research_agent.
Also read state.json if it exists for project context.

The user's research idea is: <IDEA>

From these papers:
1. Identify the 3-5 most relevant trends/techniques.
2. Propose 3-5 concrete research ideas aligned with the user's idea.

For each idea include: title, hypothesis, approach (specific code changes), expected_impact, difficulty (low/medium/high), relevant_papers.

Write output to results/ideas.json as JSON:
{
  "trend_digest": ["Trend 1: ...", ...],
  "ideas": [{"id": 1, "title": "...", "hypothesis": "...", "approach": "...", "expected_impact": "...", "difficulty": "low", "relevant_papers": ["..."]}]
}

This is a research-only task. Do NOT modify any project code. Only read files and write results/ideas.json.
```

### 2b: Select the best approach (YOUR judgment)

Read `results/ideas.json`. Select ONE idea based on:
1. **Relevance** to `IDEA`
2. **Feasibility** — prefer low/medium difficulty
3. **Novelty** — skip what overlaps with `LAST_ITERS`
4. **Concreteness** — clear `approach` field

Formulate:
- `HYPOTHESIS`
- `CHANGE_DESC` (short, for git)
- `INSTRUCTION` (detailed, for the implementation Agent)
- `PAPERS_USED`

Tell the user (2-3 lines): which approach and why.

**If no ideas.json** (Agent or fetch failed): formulate an instruction directly from the user's raw `IDEA`.

---

## Step 3: Git Setup + Register Iteration

```bash
cd /data/humanBodyProject/new_proj/research_agent && \
python -m research_agent.git_ops branch-start \
  --iteration <NEXT_ITER> \
  --change "<CHANGE_DESC>"
```

```bash
python -m research_agent.state start-iteration \
  --hypothesis "<HYPOTHESIS>" \
  --change "<CHANGE_DESC>"
```

---

## Step 4: Implement Code via Agent

Launch an **Agent** (subagent_type: general-purpose) to implement the change:

```
You are implementing a code change in the project.
Working directory: /data/humanBodyProject/new_proj/research_agent

## Instruction
<INSTRUCTION — detailed, specific implementation plan>

## Project Context
- Goal: <GOAL>
- Primary metric: <METRIC>
- Baseline: <BASELINE_METRICS>
- Current best (iter <N>): <BEST_METRICS>
- Last change: <LAST_CHANGE> -> <LAST_RESULT>

## Papers
<PAPER_TITLES_AND_KEY_IDEAS>

## Key files to examine
<FOCUS_FILES or "explore the codebase to find relevant files">

## Rules
1. Read relevant code files FIRST to understand current implementation.
2. Implement ONE focused change based on the instruction.
3. Make minimal, surgical edits — don't rewrite entire files.
4. Verify changes are syntactically correct.
5. After implementing, write a summary to results/impl_summary.json:
{
  "hypothesis": "What you expect this change to achieve",
  "change_summary": "Short description of what was changed",
  "files_modified": ["path/to/file1.py"],
  "papers_used": ["Paper Title"]
}
```

---

## Step 5: Review and Present

1. Read `results/impl_summary.json`.
2. Show the diff:
   ```bash
   git diff
   ```
3. Present to the user:
   - **Selected approach**: which idea/paper and why
   - **Hypothesis**: expected improvement
   - **Changes**: files modified + summary
   - **Diff**: actual code changes

4. Commit:
   ```bash
   python -m research_agent.git_ops commit-code \
     --iteration <NEXT_ITER> \
     --hypothesis "<HYPOTHESIS>" \
     --change "<CHANGE_DESC>" \
     --papers "<PAPER1>" "<PAPER2>"
   ```

---

## Step 6: Offer Next Steps

- **Run experiment** — launch training
- **Iterate** — give another idea
- **Modify** — launch another Agent with refinement
- **Reject** — `git checkout -- .`

---

## Fallback Chain

| Level | Paper fetch | Idea generation | Implementation |
|---|---|---|---|
| Full | `idea_discovery.py --fetch-only` | Agent subagent | Agent subagent |
| Partial | `search_papers.py` | Agent subagent | Agent subagent |
| Minimal | WebSearch | Orchestrator synthesizes | Agent subagent |
| Direct | None | User's raw idea | Agent subagent |

Implementation always goes through the Agent tool. Only the quality of paper context degrades.

---

## Rules

- NEVER implement code yourself. ALWAYS use the Agent tool.
- NEVER call `code_implementation.py` or `literature_search.py` — they are archived.
- Paper fetching uses pure Python scripts (`idea_discovery.py --fetch-only`, `search_papers.py`) — always safe.
- ONE change per invocation.
- Run steps sequentially.
- Keep the user informed with brief status updates.
