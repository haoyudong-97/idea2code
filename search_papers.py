#!/usr/bin/env python3
"""Search for papers using a Claude agent with web search capability.

Calls the Anthropic Messages API with the server-side web_search tool.
Claude reads project context, searches for relevant papers, evaluates
relevance, and returns structured JSON results.

No dependencies beyond Python stdlib — uses urllib directly.

Usage:
    python search_papers.py "topic" output.json
    python search_papers.py "topic" output.json --progress progress.md --state state.json
    python search_papers.py "topic" output.json --model claude-sonnet-4-6 --max-searches 10

Requires:
    ANTHROPIC_API_KEY environment variable

Output:
    Writes JSON array to output.json with fields:
        title, authors, year, abstract, url, arxiv_id,
        relevance (1-5), relevance_reason, key_idea
"""

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TURNS = 5  # max agentic turns if tool_use requires continuation

SYSTEM_PROMPT = """\
You are a research paper search agent for an ML project. Your ONLY job is to \
find academic papers relevant to a specific topic within the project's context.

## Instructions

1. **Understand the project**: Read the project context provided. Understand what \
the project does, what has been tried, and what the current research direction is.

2. **Plan search queries**: Based on the topic and project context, plan 3-5 \
specific search queries. Each query should target a different angle:
   - The core technique/method mentioned in the topic
   - The technique applied to the project's domain (e.g., medical image segmentation)
   - Related or alternative approaches to the same problem
   - Key author names or paper titles if you recognize them

3. **Execute searches**: Use your web_search tool for each query. Follow up on \
particularly relevant results to read abstracts or paper pages.

4. **Evaluate relevance**: For each paper found, score its relevance (1-5):
   - 5: Directly applicable — describes the exact technique or a close variant
   - 4: Highly relevant — same problem domain and approach category
   - 3: Relevant — useful background or related technique
   - 2: Tangentially related
   - 1: Not relevant
   Only keep papers scoring 3 or above.

5. **Return results**: Your final response must contain ONLY a JSON array (no \
markdown fences, no commentary before or after). Each element:
   {
     "title": "Paper Title",
     "authors": "First Author et al.",
     "year": 2024,
     "abstract": "First 2-3 sentences of abstract...",
     "url": "https://...",
     "arxiv_id": "2401.12345 or empty string",
     "relevance": 5,
     "relevance_reason": "Why this paper matters for the project",
     "key_idea": "One sentence: the main takeaway applicable to our work"
   }

   Sort by relevance descending, then year descending.

## Rules
- Be specific: every search query must relate to the topic, not generic terms.
- Quality over quantity: 3-8 highly relevant papers beat 15 vague ones.
- No hallucinated papers: only include papers you actually found via search.
- Valid JSON only: your final message must be a parseable JSON array, nothing else.\
"""


def _build_user_message(topic: str, progress_path: str | None,
                        state_path: str | None) -> str:
    """Build the user message with topic and project context."""
    parts = [f"## Search Topic\n{topic}"]

    if progress_path and Path(progress_path).exists():
        content = Path(progress_path).read_text().strip()
        parts.append(f"\n## Project Goal (from progress.md)\n{content}")

    if state_path and Path(state_path).exists():
        try:
            state = json.loads(Path(state_path).read_text())
            # Summarize state rather than dumping raw JSON
            summary_parts = []
            if state.get("goal"):
                goal_text = state["goal"]
                # If goal is from progress.md, it might be very long; truncate
                if len(goal_text) > 200:
                    goal_text = goal_text[:200] + "..."
                summary_parts.append(f"Goal: {goal_text}")
            if state.get("primary_metric"):
                summary_parts.append(f"Primary metric: {state['primary_metric']}")
            bl = state.get("baseline")
            if bl and bl.get("metrics"):
                summary_parts.append(f"Baseline: {json.dumps(bl['metrics'])}")
            best = state.get("best")
            if best and best.get("metrics"):
                summary_parts.append(
                    f"Best so far (iter {best.get('iteration', '?')}): "
                    f"{json.dumps(best['metrics'])}"
                )
            for it in state.get("iterations", [])[-3:]:
                summary_parts.append(
                    f"Iter {it['id']}: {it.get('change_summary', '')} "
                    f"-> {json.dumps(it.get('metrics', {}))}"
                )
            if summary_parts:
                parts.append(
                    "\n## Iteration History (from state.json)\n" +
                    "\n".join(f"- {s}" for s in summary_parts)
                )
        except (json.JSONDecodeError, IOError):
            pass

    parts.append(
        "\n## Task\n"
        "Search for papers relevant to the topic above, within the context of "
        "this project. Return ONLY a JSON array of results."
    )
    return "\n".join(parts)


def _call_api(messages: list, model: str, api_key: str,
              max_searches: int) -> dict:
    """Make a single call to the Anthropic Messages API."""
    payload = {
        "model": model,
        "max_tokens": 16000,
        "system": SYSTEM_PROMPT,
        "tools": [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": max_searches,
        }],
        "messages": messages,
    }

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode())


def _extract_text(response: dict) -> str:
    """Extract all text blocks from an API response."""
    parts = []
    for block in response.get("content", []):
        if block.get("type") == "text":
            parts.append(block["text"])
    return "\n".join(parts)


def _serialize_content(content: list) -> list:
    """Serialize response content for use in messages (handle non-JSON types)."""
    serialized = []
    for block in content:
        if isinstance(block, dict):
            serialized.append(block)
        else:
            # Handle SDK-style objects by converting to dict
            serialized.append(dict(block))
    return serialized


def run_search(topic: str, progress_path: str | None, state_path: str | None,
               model: str = DEFAULT_MODEL, max_searches: int = 10) -> str:
    """Run the search agent. Returns the final text response."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    user_msg = _build_user_message(topic, progress_path, state_path)
    messages = [{"role": "user", "content": user_msg}]

    for turn in range(MAX_TURNS):
        try:
            response = _call_api(messages, model, api_key, max_searches)
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            print(f"API error ({e.code}): {body}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Request failed: {e}", file=sys.stderr)
            sys.exit(1)

        stop = response.get("stop_reason", "")

        # If end_turn, we have the final response
        if stop == "end_turn":
            return _extract_text(response)

        # If the model wants to continue (e.g., tool_use with client-side tools),
        # pass the response back and prompt continuation.
        # For server-side tools (web_search), results are already in the response
        # content, so this case is unlikely but handled for robustness.
        messages.append({
            "role": "assistant",
            "content": response.get("content", []),
        })
        messages.append({
            "role": "user",
            "content": "Continue. Remember to return ONLY a JSON array as your final response.",
        })

        print(f"  Turn {turn + 1}/{MAX_TURNS} (stop_reason={stop})", file=sys.stderr)

    # If we exhausted turns, return whatever text we have
    return _extract_text(response)


def _extract_json_array(text: str) -> list | None:
    """Try to extract a JSON array from text, handling markdown fences."""
    text = text.strip()

    # Try direct parse
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code fence
    import re
    patterns = [
        r"```json\s*\n(.*?)\n```",
        r"```\s*\n(.*?)\n```",
        r"\[.*\]",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            candidate = match.group(1) if match.lastindex else match.group(0)
            try:
                result = json.loads(candidate)
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                continue

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Search for papers using a Claude agent with web search. "
                    "Topics should be specific to the project, not generic.",
        epilog="""Examples:
  python search_papers.py "Householder orthogonal adapters for ViT fine-tuning" results.json
  python search_papers.py "nullspace bias in adapter layers" results.json --progress progress.md
  python search_papers.py "Gram matrix preservation PEFT" results.json --state state.json
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("topic",
                        help="What to search for — must be specific to the project")
    parser.add_argument("output",
                        help="Output JSON file path")
    parser.add_argument("--progress", default=None,
                        help="Path to progress.md for project context")
    parser.add_argument("--state", default=None,
                        help="Path to state.json for iteration history")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Claude model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--max-searches", type=int, default=10,
                        help="Max web searches the agent can perform (default: 10)")
    parser.add_argument("--verbose", action="store_true",
                        help="Print raw response to stderr")
    args = parser.parse_args()

    print(f"Searching: {args.topic}", file=sys.stderr)
    print(f"Model: {args.model}", file=sys.stderr)

    raw_text = run_search(
        args.topic, args.progress, args.state,
        args.model, args.max_searches,
    )

    if args.verbose:
        print(f"\n--- Raw response ---\n{raw_text}\n---", file=sys.stderr)

    # Parse JSON from response
    papers = _extract_json_array(raw_text)
    if papers is None:
        print("Warning: Could not parse JSON from agent response.", file=sys.stderr)
        print("Raw text saved to output file.", file=sys.stderr)
        Path(args.output).write_text(raw_text)
        sys.exit(1)

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(papers, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Found {len(papers)} papers -> {args.output}", file=sys.stderr)

    # Also print to stdout for piping
    json.dump(papers, sys.stdout, indent=2, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()
