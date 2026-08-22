# Delta 04 — Research/Analyst

Basis: [`../_base.md`](../_base.md). File ini **hanya** selisihnya. Rasional
lengkap: [`../../archetypes/04-research-agent.md`](../../archetypes/04-research-agent.md)
§Bangun ini pakai deepagents.

## Ganti

- **Tool surface**: `_base` tidak memasang `tools=` (cuma tool filesystem
  bawaan). Di sini, tool surface dipersempit ke `tools=[web_search_tool,
  think_tool]` **plus** `permissions=[FilesystemPermission(
  operations=["write"], paths=["/**"], mode="deny")]` — `operations` cuma
  menerima `"read"`/`"write"` (klasifikasi kategori, bukan nama tool
  literal; `write_file`/`edit_file`/`delete` masuk kategori `"write"`).
  `[code]` sumber `deepagents/middleware/filesystem.py`
  (`FilesystemOperation = Literal["read", "write"]`,
  `_DEFAULT_FS_TOOL_OPS`), dibaca langsung dari
  `references/recipes/.venv`. `execute` **tidak perlu** ditutup lewat
  `permissions` sama sekali — backend `_base` (`StoreBackend`) tidak
  mengimplementasikan `SandboxBackendProtocol`, jadi tool `execute` tidak
  pernah terdaftar untuk arketipe ini (beda dari delta 01/02/07 yang
  mengganti backend ke `LocalShellBackend`/sandbox). `FilesystemMiddleware`
  sendiri tidak bisa dikeluarkan dari stack (`../../systems/deepagents.md`
  §7: middleware inti tidak bisa dikecualikan lewat `excluded_middleware`),
  jadi kemampuan tulis file ditutup lewat `permissions`, bukan dihapus —
  blast radius arketipe ini read-only terhadap dunia luar (`## Posisi di 6
  sumbu` archetype 04).
- **Delegation**: `subagents=[{"name": "research-agent", ...,
  "tools": [web_search_tool, think_tool]}]`, dipanggil lewat tool `task`
  bawaan `SubAgentMiddleware` — `_base` tidak memasang subagent. `[code]`
  sumber `examples/deep_research/research_agent.ipynb`.
- **Provenance/output**: `response_format=<skema daftar klaim+sitasi>` pada
  `create_deep_agent(...)` — `_base` tidak memasang `response_format`.
  `[code]` parameter ada di signature `create_deep_agent`, sumber `graph.py`.

## Tambah

- **Budget/loop limit**: `max_concurrent_research_units`,
  `max_researcher_iterations` sebagai konstanta di kode pemanggil subagent
  (level orchestrator aplikasi, bukan parameter bawaan
  `create_deep_agent`). `[code]` sumber sama dengan delegation di atas.
- **Guardrail titik 4 (Output) tambahan**: validasi post-hoc yang
  mencocokkan tiap sitasi di `response_format` terhadap hasil tool call
  `web_search` nyata di transkrip. `[ours]` archetype 04: vanilla
  `response_format` cuma memvalidasi bentuk skema, bukan bahwa isinya
  benar-benar berasal dari tool call nyata — celah itu yang membuat sitasi
  halusinasi (jebakan #1 archetype 04) bisa lolos kalau tidak ditambal.
  Titik pemasangan: `after_model` hook tambahan di `middleware=[...]`,
  mengikuti pola titik 4 `../../concepts/guardrails.md`.

## Buang

- **`StoreBackend` sebagai jalur file durable utama** — tetap ada
  (persistence-schema.md tetap menyimpan laporan akhir sebagai artefak),
  tapi arketipe ini tidak menulis file kerja lewat `write_file`/`edit_file`
  sama sekali (ditutup lewat `permissions` di atas) — jadi backend `_base`
  dipakai murni untuk baca (kalau ada), bukan sebagai target tulis aktif.
