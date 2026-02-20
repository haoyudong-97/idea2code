## Research Loop Protocol

When asked to start a research loop, follow this protocol.

### progress.md

The user creates `progress.md` to define the research goal. The agent auto-updates it with tracking data below the sentinel line. **Never edit the user's goal section above the sentinel.**

**User creates:**
```markdown
# Research Goal

Improve heart segmentation 3D Dice above 0.92 using adapter architecture changes.

## Constraints
- Keep parameter count under 1M
- Must converge within 200 epochs
```

**Agent updates everything below** `<!-- AGENT PROGRESS BELOW -->` automatically via `state.py`.

### Setup (first time only)

1. Read the user's `progress.md` to understand the goal.
2. Initialize state from it:
   ```
   python -m research_agent.state init --progress progress.md --metric "<primary_metric>"
   ```
   Or with an explicit goal:
   ```
   python -m research_agent.state init --goal "<goal>" --metric "<primary_metric>"
   ```
3. Identify baseline: read existing results, record in state:
   ```
   python -m research_agent.state set-baseline --checkpoint "<path>" --metrics '{"metric": value}'
   ```
   (This auto-updates `progress.md`.)

### Each Iteration

1. **Read state** — recover full context after compression:
   ```
   python -m research_agent.state read
   ```
2. **Search literature** — use the Claude search agent to find relevant papers:
   - The search agent calls the Anthropic API with web search enabled. It reads project context (progress.md, state.json), runs multiple targeted searches, evaluates relevance, and writes structured JSON results.
   - The topic must be grounded in the project. Relate it to the current architecture, the specific problem you're solving, or the technique you plan to try.
   - **Never use generic topics** like "deep learning" or "image segmentation" — always specify the method, component, or technique relevant to this iteration.
   ```
   python research_agent/search_papers.py \
     "orthogonal adapter Gram-preserving fine-tuning for ViT" \
     results/search_iter3.json \
     --progress progress.md --state state.json
   ```
   - The agent writes a JSON array of papers, each with `relevance` score (1-5), `relevance_reason`, and `key_idea` explaining what we can apply.
   - Review results before forming your hypothesis. Focus on papers with relevance >= 4.
3. **Form hypothesis** — based on papers + previous results, state what you expect and why.
4. **Implement** — make ONE principal change. Create a new experiment script if needed. Never modify previous experiment scripts.
5. **Execute** — launch in background:
   ```
   bash research_agent/run_and_wait.sh <script> <checkpoint_dir>
   ```
6. **Poll** — check completion every ~10 minutes:
   ```
   test -f <checkpoint_dir>/.done && cat <checkpoint_dir>/.done || echo RUNNING
   ```
7. **Analyze** — read results, compare with baseline and previous best.
8. **Update state** — record the iteration (auto-updates `progress.md`):
   ```
   python -m research_agent.state add-iteration \
     --hypothesis "..." --change "..." --checkpoint "..." \
     --metric-name <name> --metric-value <value> \
     --feedback "..."
   ```
9. **Update progress** — optionally set a status note between iterations:
   ```
   python -m research_agent.state update-progress --status "Trying token-wise FiLM next"
   ```
10. **Summarize** — present results and proposed next steps to user.
11. **Get feedback** — wait for user response before next iteration.

### Rules

- **ONE principal change per iteration** — isolate variables for clean comparison.
- **NEVER overwrite previous checkpoints** — each iteration gets a unique checkpoint directory.
- **Re-read state.json** at the start of every iteration to recover context.
- **Primary metric drives decisions**; always report secondary metrics too.
- **Save experiment scripts** — each iteration's script should be reproducible.
- **Cite papers** — when a technique comes from literature, note the reference.
- **Never edit the user's goal section** in `progress.md` — only the agent-managed section below the sentinel is auto-updated.
