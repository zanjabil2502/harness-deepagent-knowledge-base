"""01 - Minimal deep agent: default middleware stack, no customization.

Demonstrates: the most minimal `create_deep_agent(model, tools=[])` call — no
explicit `backend`, `subagents`, `middleware`, `permissions`, or
`interrupt_on`. It shows the default stack installed automatically: the
filesystem tools (`ls`, `read_file`, `write_file`, `edit_file`, `glob`,
`grep`), the default `general-purpose` subagent through the `task` tool,
automatic compaction (`SummarizationMiddleware`), and
`PatchToolCallsMiddleware`.

Archetypes served: the baseline for all of them — this is the starting point
before the backend/middleware/gates are adjusted per archetype (see the
"Building this with deepagents" section of `references/archetypes/*.md`).

Concepts illustrated: `## 2. Context` and `## 3. Tool surface` in
`references/systems/deepagents.md` — the default `StateBackend` (ephemeral,
thread-scoped) and the few-but-broad tool surface always present with no extra
configuration.
"""

import sys

from langchain_anthropic import ChatAnthropic

from deepagents import create_deep_agent


def build_agent():
    """Build the most minimal deep agent with a model and no customization."""
    model = ChatAnthropic(model_name="claude-sonnet-4-6")
    return create_deep_agent(model=model, tools=[])


def main() -> int:
    agent = build_agent()
    graph = agent.get_graph()
    print("=== 01_minimal_agent ===")
    print(f"Graph nodes: {sorted(graph.nodes.keys())}")
    print("Backend: StateBackend (the default, ephemeral, thread-scoped)")
    print("Default subagent: general-purpose (added automatically)")

    print(
        "Construction verified -- the API names and signatures used are valid. "
        "This recipe deliberately never calls the model: it needs no "
        "credentials at all and touches no network."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
