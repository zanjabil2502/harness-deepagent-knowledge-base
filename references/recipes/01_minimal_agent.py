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

    print(
        "Konstruksi terverifikasi — nama dan signature API yang dipakai valid. "
        "Recipe ini sengaja tidak memanggil model: tidak butuh kredensial "
        "apa pun, dan tidak menyentuh jaringan."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
