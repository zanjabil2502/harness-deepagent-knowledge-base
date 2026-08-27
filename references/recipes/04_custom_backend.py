"""04 - Custom backend: a CompositeBackend mixing ephemeral + per-user durable.

Demonstrates: `CompositeBackend(default=StateBackend(), routes={"/memories/":
StoreBackend(namespace=...)})` - files outside `/memories/` stay ephemeral
(living in LangGraph state, gone when the thread ends), while files under
`/memories/` are written through a `StoreBackend` scoped per user by a
`namespace` factory (`lambda rt: (user_id, "memories")`). This is the official
hybrid pattern shown in `FilesystemMiddleware`'s docstring and the
`deepagents` documentation, not a construction of our own.

Archetypes served: the In-App Copilot (05) and the General Task Agent (03) -
both need some files to survive across sessions (memory/artifacts) while
others may be discarded once the session ends.

Concepts illustrated: `## Filesystem backend` in
`references/systems/deepagents.md` - only `StoreBackend`/`CompositeBackend`
(routing into one) has an explicit scoping *hook* (`namespace`) for
multi-user isolation; a plain `StateBackend` doesn't.
"""

import sys

from langchain_anthropic import ChatAnthropic
from langgraph.store.memory import InMemoryStore

from deepagents import create_deep_agent
# A NOTE on middleware artifacts: CompositeBackend sets artifacts_root
# (defaulting to "/"), and the built-in middleware writes into
# <root>/conversation_history/, .../media/, and <root>/large_tool_results/
# (summarization.py:598-603). The route below only covers /memories/, so
# conversation summaries fall to default=StateBackend() -- ephemeral, not
# persisted. To make them durable, add "/conversation_history/" (and
# "/large_tool_results/") to routes. See
# references/deepagents/middleware.md #artifacts_root.
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend


def build_agent():
    """Build a deep agent with a hybrid backend: ephemeral by default + durable /memories/."""
    model = ChatAnthropic(model_name="claude-sonnet-4-6")
    user_id = "demo-user-001"  # ponytail: hardcoded for the recipe; a real app takes it from the auth context
    memories_backend = StoreBackend(
        namespace=lambda _runtime: (user_id, "memories"),
        store=InMemoryStore(),
    )
    backend = CompositeBackend(
        default=StateBackend(),
        routes={"/memories/": memories_backend},
    )
    return create_deep_agent(model=model, tools=[], backend=backend)


def main() -> int:
    agent = build_agent()
    graph = agent.get_graph()
    print("=== 04_custom_backend ===")
    print(f"Graph nodes: {sorted(graph.nodes.keys())}")
    print("Backend: CompositeBackend -- default StateBackend (ephemeral),")
    print("         route /memories/** -> StoreBackend (durable, a per-user namespace)")

    print(
        "Construction verified -- the API names and signatures used are valid. "
        "This recipe deliberately never calls the model: it needs no "
        "credentials at all and touches no network."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
