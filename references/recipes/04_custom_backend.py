"""04 - Custom backend: CompositeBackend campur ephemeral + durable per-user.

Mendemokan: `CompositeBackend(default=StateBackend(), routes={"/memories/":
StoreBackend(namespace=...)})` — file di luar `/memories/` tetap ephemeral
(hidup di state LangGraph, hilang saat thread berakhir), sementara file di
`/memories/` ditulis lewat `StoreBackend` yang di-scope per-user lewat
`namespace` factory (`lambda rt: (user_id, "memories")`). Ini pola hybrid
resmi yang dicontohkan di docstring `FilesystemMiddleware` dan dokumentasi
`deepagents`, bukan konstruksi kami sendiri.

Arketipe yang terbantu: In-App Copilot (05) dan General Task Agent (03) —
keduanya butuh sebagian file bertahan lintas sesi (memori/artefak) sementara
sebagian lain boleh dibuang begitu sesi selesai.

Konsep yang diilustrasikan: `## Backend filesystem` di
`references/systems/deepagents.md` — hanya `StoreBackend`/`CompositeBackend`
(yang merutekan ke situ) punya *hook* scoping eksplisit (`namespace`) untuk
isolasi multi-user; `StateBackend` polos tidak.
"""

import os
import sys

from langchain_anthropic import ChatAnthropic
from langgraph.store.memory import InMemoryStore

from deepagents import create_deep_agent
# CATATAN artefak middleware: CompositeBackend menetapkan artifacts_root (default
# "/"), dan middleware bawaan menulis ke <root>/conversation_history/,
# .../media/, serta <root>/large_tool_results/ (summarization.py:598-603).
# Route di bawah hanya menutupi /memories/, jadi ringkasan percakapan jatuh ke
# default=StateBackend() -- ephemeral, tidak persist. Untuk membuatnya durable,
# tambahkan "/conversation_history/" (dan "/large_tool_results/") ke routes.
# Lihat references/deepagents/middleware.md #artifacts_root.
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend


def build_agent():
    """Bangun deep agent dengan backend hybrid: ephemeral default + durable /memories/."""
    model = ChatAnthropic(model_name="claude-sonnet-4-6")
    user_id = "demo-user-001"  # ponytail: dihardcode untuk recipe; di aplikasi nyata ambil dari auth context
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
    print(f"Node graph: {sorted(graph.nodes.keys())}")
    print("Backend: CompositeBackend — default StateBackend (ephemeral),")
    print("         route /memories/** -> StoreBackend (durable, per-user namespace)")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "Konstruksi terverifikasi — CompositeBackend+StoreBackend terpasang "
            "tanpa exception. Live call bersifat opsional: set "
            "ANTHROPIC_API_KEY kalau ingin melihat satu giliran nyata."
        )
        return 0

    print("ANTHROPIC_API_KEY ada — menjalankan satu giliran nyata (opsional)...")
    result = agent.invoke({"messages": [{"role": "user", "content": "Balas dengan satu kata: 'ok'."}]})
    print("Respons model:", result["messages"][-1].content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
