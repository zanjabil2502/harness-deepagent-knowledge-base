"""03 - Subagents: delegasi lewat tool `task` ke subagent riset sempit.

Mendemokan: `subagents=[SubAgent, ...]` pada `create_deep_agent` — sebuah
subagent deklaratif dengan `tools` yang lebih sempit dari agent utama
(hanya `web_search_stub`, tanpa akses filesystem luas), dipanggil lewat tool
`task` yang dibangun otomatis oleh `SubAgentMiddleware`. Isi `ToolMessage`
yang kembali ke agent utama adalah teks `AIMessage` non-kosong terakhir dari
subagent, atau `structured_response` yang di-serialize ke JSON kalau field
itu diisi — bukan `messages` state akhir subagent disalin mentah, dan bukan
seluruh transkrip kerjanya.

Arketipe yang terbantu: Research/Analyst (04) — pola subagent riset dengan
tool pencarian sempit persis seperti yang dirujuk
`references/archetypes/04-research-agent.md` section "Bangun ini pakai
deepagents" (`examples/deep_research/research_agent.ipynb`).

Konsep yang diilustrasikan: `## 4. Delegation` di
`references/systems/deepagents.md` — spec `SubAgent` (dict), auto-tambahnya
subagent `general-purpose` di samping subagent kustom, dan bagaimana hasil
delegasi kembali sebagai `ToolMessage` tool `task`.
"""

import os
import sys

from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool

from deepagents import SubAgent, create_deep_agent


@tool
def web_search_stub(query: str) -> str:
    """Cari informasi di web untuk `query` (stub — tidak memanggil jaringan nyata)."""
    return f"[stub] tidak ada hasil nyata untuk: {query}"


def build_agent():
    """Bangun deep agent dengan satu subagent riset bertool sempit."""
    model = ChatAnthropic(model_name="claude-sonnet-4-6")
    research_subagent: SubAgent = {
        "name": "research-agent",
        "description": "Mencari dan meringkas informasi dari web untuk sub-pertanyaan riset.",
        "system_prompt": "Kamu adalah subagent riset. Gunakan web_search_stub, lalu ringkas temuan secara singkat.",
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
    print(f"Node graph: {sorted(graph.nodes.keys())}")
    print("Subagent terdaftar: research-agent (tool sempit: web_search_stub)")
    print("Subagent default general-purpose tetap ditambahkan otomatis")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ANTHROPIC_API_KEY tidak diset — invokasi live dilewati. "
            "Konstruksi agent dengan spec SubAgent berhasil tanpa exception."
        )
        return 0

    print("ANTHROPIC_API_KEY ditemukan — menjalankan satu giliran nyata...")
    result = agent.invoke({"messages": [{"role": "user", "content": "Balas dengan satu kata: 'ok'."}]})
    print("Respons model:", result["messages"][-1].content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
