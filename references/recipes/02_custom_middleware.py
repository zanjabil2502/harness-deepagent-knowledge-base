"""02 - Custom middleware: explicit planning + permission-gated writes.

Mendemokan: menambah `TodoListMiddleware` (dari `langchain.agents.middleware`,
**bukan** bagian stack default `create_deep_agent`) lewat parameter
`middleware=[...]`, dan memasang `FilesystemPermission` dengan
`mode="interrupt"` untuk menahan tiap `write_file` di luar `/scratch/` demi
persetujuan manusia — tanpa menyentuh `interrupt_on` secara manual, karena
rule `mode="interrupt"` otomatis membangkitkan entrinya sendiri lewat
`_build_interrupt_on_from_permissions`.

Arketipe yang terbantu: General Task Agent (03) — planning eksplisit adalah
axis pembeda utamanya (lihat `references/archetypes/03-general-task-agent.md`
section "Bangun ini pakai deepagents": "TodoListMiddleware ... harus
ditambahkan eksplisit").

Konsep yang diilustrasikan: `## 5. State & resume` (tidak ada todo bawaan,
harus ditambah manual) dan `## 6. Safety gate` (permission `mode="interrupt"`
membangkitkan `interrupt_on` otomatis, digabung dengan entri eksplisit) di
`references/systems/deepagents.md`.
"""

import os
import sys

from langchain.agents.middleware import TodoListMiddleware
from langchain_anthropic import ChatAnthropic

from deepagents import FilesystemPermission, create_deep_agent


def build_agent():
    """Bangun deep agent dengan TodoListMiddleware eksplisit + gate permission."""
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
    print(f"Node graph: {sorted(graph.nodes.keys())}")
    print("Middleware eksplisit: TodoListMiddleware (planning, tool write_todos)")
    print("Permission gate: write ke /scratch/** diizinkan, write lain interrupt")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ANTHROPIC_API_KEY tidak diset — invokasi live dilewati. "
            "Konstruksi agent (termasuk permission rule dan TodoListMiddleware) "
            "berhasil tanpa exception."
        )
        return 0

    print("ANTHROPIC_API_KEY ditemukan — menjalankan satu giliran nyata...")
    result = agent.invoke({"messages": [{"role": "user", "content": "Balas dengan satu kata: 'ok'."}]})
    print("Respons model:", result["messages"][-1].content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
