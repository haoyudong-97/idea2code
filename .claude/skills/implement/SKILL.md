---
name: implement
description: Implement a code change in the project. TRIGGER when the user asks to implement something, make a code change, try an idea in code, apply a technique, modify the model/config, or says things like "implement X", "try X in code", "change Y to Z", "apply this paper's approach". Do NOT trigger for pure discussion or analysis — only when actual code changes are requested.
argument-hint: <instruction or description of what to implement> [--papers path] [--files file1 file2]
disable-model-invocation: false
allowed-tools: Bash(python:*), Bash(cat:*), Bash(test:*), Bash(git diff:*), Bash(git add:*), Bash(git commit:*), Bash(git branch:*), Read, Grep, Agent
---

# Implement Code Change

Delegate a code change to an **Agent subagent**. You are the orchestrator — NEVER edit project code directly.

## Step 0: Read current state

```bash
cd /data/humanBodyProject/new_proj/research_agent
```

1. If `state.json` exists:
   ```bash
   python -m research_agent.state read
   ```
2. If `progress.md` exists, read the user section for notes/constraints.

## Step 1: Parse the input

- **instruction**: the main thing to implement (required).
- **--papers PATH**: path to a papers JSON file.
- **--files FILE1 FILE2 ...**: specific files to focus on.

If the user references an idea number from `/find-papers`, read `results/ideas.json` and extract that idea's details.

## Step 2: Prepare the iteration (if state exists)

```bash
python -m research_agent.git_ops branch-start --iteration <N> --change "<CHANGE_DESC>"
python -m research_agent.state start-iteration --hypothesis "<HYPOTHESIS>" --change "<CHANGE_DESC>"
```

## Step 3: Implement via Agent tool

Launch an **Agent** subagent with a detailed prompt including:
- The instruction
- Project context (goal, baseline, best, last iteration)
- Key files to focus on
- Requirement to write summary to `results/impl_summary.json`

## Step 4: Review changes

1. Read `results/impl_summary.json`.
2. Show `git diff`.
3. Present: what changed, hypothesis, diff preview.

## Step 5: Ask the user

- **Accept** — commit via `git_ops commit-code`
- **Modify** — launch another Agent with refinement
- **Reject** — `git checkout -- .`

## Notes

- NEVER implement code yourself. ALWAYS use the Agent tool.
- NEVER call `code_implementation.py` — it is archived.
- ONE change per invocation.
