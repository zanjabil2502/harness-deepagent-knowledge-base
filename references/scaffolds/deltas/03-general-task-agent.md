# Delta 03 — General Task Agent

Basis: [`../_base.md`](../_base.md). File ini **hanya** selisihnya. Rasional
lengkap: [`../../archetypes/03-general-task-agent.md`](../../archetypes/03-general-task-agent.md)
§Bangun ini pakai deepagents.

## Tambah

- **Planning**: `middleware=[TodoListMiddleware()]` pada
  `create_deep_agent(...)` — `_base` tidak memasangnya (middleware ini
  **tidak** ada di stack default `create_deep_agent()` sama sekali, bukan
  cuma tidak ada di `_base`). `[code]` sumber `graph.py`, archetype 03.
- **Delegation**: `subagents=[{"name": ..., "description": ..., "model":
  ..., "system_prompt": ..., "tools": [...]}, ...]` — `_base` tidak
  memasang subagent apa pun. `[code]` sumber `middleware/subagents.py`,
  `examples/content-builder-agent/README.md`.
- **Memory lintas sesi**: `memory=["./AGENTS.md"]` pada
  `create_deep_agent(...)` — memuat `AGENTS.md` ke system prompt tiap sesi
  lewat `MemoryMiddleware`, di atas `StoreBackend` yang `_base` sudah
  pasang untuk file durable. `[code]` sumber `ARCHITECTURE.md`.
- **Loop budget & kill switch**: middleware kustom deteksi tool-call
  berulang identik N kali berturut-turut → paksa berhenti. `[ours]`
  archetype 03: `deepagents` tidak punya "no-progress detector" bawaan —
  vanilla-nya `recursion_limit` generik LangGraph (9999,
  `../../concepts/guardrails.md` peringatan titik 5), `interrupt_on` per
  tool, dan `ModelCallLimitMiddleware`/`ToolCallLimitMiddleware`
  (`langchain.agents.middleware`, bukan milik `deepagents`) — ketiganya
  cukup mencegah loop tak berhenti secara sintaksis (atau kelebihan
  budget) tapi tidak satu pun mendeteksi *pengulangan*, jadi tidak cukup
  untuk agent yang secara semantik berputar di tempat sebelum budgetnya
  habis.

## Ganti

- **Tidak ada** — backend (`StoreBackend(namespace=...)`) dari `_base`
  sudah cocok dengan kebutuhan "filesystem-as-memory" arketipe ini apa
  adanya; `memory=["./AGENTS.md"]` di atas menambah lapisan di atasnya,
  bukan menggantinya.

## Buang

- **Tidak ada** — `_base` tidak memasang apa pun yang bertentangan dengan
  arketipe ini; delta ini murni penambahan di atas baseline.
