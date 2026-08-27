"""03 - Subagents: delegating through the `task` tool to a narrow research subagent.

Demonstrates: `subagents=[SubAgent, ...]` on `create_deep_agent` - a
declarative subagent with `tools` narrower than the main agent's (only
`web_search_stub`, with no broad filesystem access), invoked through the
`task` tool `SubAgentMiddleware` builds automatically. The `ToolMessage`
content returning to the main agent is the subagent's last non-empty
`AIMessage` text, or its `structured_response` serialised to JSON when that
field is set - not the subagent's final `messages` state copied raw, and not
its whole working transcript.

Archetypes served: Research/Analyst (04) - the research subagent pattern with
a narrow search tool, exactly as referenced by
`references/archetypes/04-research-agent.md`'s "Building this with
deepagents" section (`examples/deep_research/research_agent.ipynb`).

Concepts illustrated: `## 4. Delegation` in
`references/systems/deepagents.md` - the `SubAgent` spec (a dict), the
automatic addition of the `general-purpose` subagent alongside a custom one,
and how a delegation's result returns as the `task` tool's `ToolMessage`.
"""

import sys

from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool

from deepagents import SubAgent, create_deep_agent


@tool
def web_search_stub(query: str) -> str:
    """Search the web for `query` (a stub -- it makes no real network call)."""
    return f"[stub] no real results for: {query}"


def build_agent():
    """Build a deep agent with one narrow-tooled research subagent."""
    model = ChatAnthropic(model_name="claude-sonnet-4-6")
    research_subagent: SubAgent = {
        "name": "research-agent",
        "description": "Searches and summarises information from the web for research sub-questions.",
        "system_prompt": "You are a research subagent. Use web_search_stub, then summarise your findings briefly.",
        "tools": [web_search_stub],
    }
    return create_deep_agent(
        model=model,
        tools=[],
        subagents=[research_subagent],
    )


def main() -> int:
    agent = build_agent()
    graph = agent.get_graph()
    print("=== 03_subagents ===")
    print(f"Graph nodes: {sorted(graph.nodes.keys())}")
    print("Registered subagent: research-agent (narrow tool: web_search_stub)")
    print("The default general-purpose subagent is still added automatically")

    print(
        "Construction verified -- the API names and signatures used are valid. "
        "This recipe deliberately never calls the model: it needs no "
        "credentials at all and touches no network."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
