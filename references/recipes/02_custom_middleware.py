"""02 - Custom middleware: explicit planning + permission-gated writes.

Demonstrates: adding `TodoListMiddleware` (from
`langchain.agents.middleware`, **not** part of `create_deep_agent`'s default
stack) through the `middleware=[...]` parameter, and installing a
`FilesystemPermission` with `mode="interrupt"` to hold every `write_file`
outside `/scratch/` for human approval — without touching `interrupt_on`
manually, because a `mode="interrupt"` rule generates its own entries
automatically through `_build_interrupt_on_from_permissions`.

Archetypes served: the General Task Agent (03) — explicit planning is its
primary distinguishing axis (see
`references/archetypes/03-general-task-agent.md`, the "Building this with
deepagents" section: "TodoListMiddleware ... must be added explicitly").

Concepts illustrated: `## 5. State & resume` (no built-in todos; they must be
added manually) and `## 6. Safety gate` (a `mode="interrupt"` permission
generating `interrupt_on` automatically, merged with explicit entries) in
`references/systems/deepagents.md`.
"""

import sys

from langchain.agents.middleware import TodoListMiddleware
from langchain_anthropic import ChatAnthropic

from deepagents import FilesystemPermission, create_deep_agent


def build_agent():
    """Build a deep agent with an explicit TodoListMiddleware + a permission gate."""
    model = ChatAnthropic(model_name="claude-sonnet-4-6")
    permissions = [
        FilesystemPermission(operations=["write"], paths=["/scratch/**"], mode="allow"),
        FilesystemPermission(operations=["write"], paths=["/**"], mode="interrupt"),
    ]
    return create_deep_agent(
        model=model,
        tools=[],
        middleware=[TodoListMiddleware()],
        permissions=permissions,
    )


def main() -> int:
    agent = build_agent()
    graph = agent.get_graph()
    print("=== 02_custom_middleware ===")
    print(f"Graph nodes: {sorted(graph.nodes.keys())}")
    print("Explicit middleware: TodoListMiddleware (planning, the write_todos tool)")
    print("Permission gate: writes to /scratch/** allowed, other writes interrupt")

    print(
        "Construction verified -- the API names and signatures used are valid. "
        "This recipe deliberately never calls the model: it needs no "
        "credentials at all and touches no network."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
