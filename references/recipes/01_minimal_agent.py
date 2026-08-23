"""01 - Minimal deep agent: default middleware stack, no customization.

Mendemokan: pemanggilan `create_deep_agent(model, tools=[])` paling minimal —
tanpa `backend`, `subagents`, `middleware`, `permissions`, atau `interrupt_on`
eksplisit. Ini menunjukkan stack bawaan yang otomatis terpasang: tool
filesystem (`ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`),
subagent `general-purpose` default via tool `task`, kompaksi otomatis
(`SummarizationMiddleware`), dan `PatchToolCallsMiddleware`.

Arketipe yang terbantu: baseline untuk semua arketipe — ini adalah titik awal
sebelum backend/middleware/gate disesuaikan per arketipe (lihat
`references/archetypes/*.md` section "Bangun ini pakai deepagents").

Konsep yang diilustrasikan: `## 2. Context` dan `## 3. Tool surface` di
`references/systems/deepagents.md` — backend default `StateBackend`
(ephemeral, thread-scoped) dan tool surface sedikit-tapi-luas yang selalu ada
tanpa konfigurasi tambahan.
"""

import os
import sys

from langchain_anthropic import ChatAnthropic

from deepagents import create_deep_agent


def build_agent():
    """Bangun deep agent paling minimal dengan model, tanpa kustomisasi apa pun."""
    model = ChatAnthropic(model_name="claude-sonnet-4-6")
    return create_deep_agent(model=model, tools=[])


def main() -> int:
    agent = build_agent()
    graph = agent.get_graph()
    print("=== 01_minimal_agent ===")
    print(f"Node graph: {sorted(graph.nodes.keys())}")
    print("Backend: StateBackend (default, ephemeral, thread-scoped)")
    print("Subagent default: general-purpose (auto-ditambahkan)")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "Konstruksi terverifikasi — nama dan signature API yang dipakai valid. "
            "Live call bersifat opsional: set ANTHROPIC_API_KEY kalau ingin "
            "melihat satu giliran nyata."
        )
        return 0

    print("ANTHROPIC_API_KEY ada — menjalankan satu giliran nyata (opsional)...")
    result = agent.invoke({"messages": [{"role": "user", "content": "Balas dengan satu kata: 'ok'."}]})
    print("Respons model:", result["messages"][-1].content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
