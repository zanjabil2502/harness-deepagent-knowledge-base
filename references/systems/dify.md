# Dify

> Label tiap klaim: [code] / [docs] / [inferred]

Tier **T2**. `langgenius/dify`, platform Python (Flask/`api/`) + TS
(`web/`) untuk membangun aplikasi LLM lewat **workflow visual (DAG)** dan/atau
**agent app**. Dipilih sebagai eksemplar **platform workflow** sesuai
kandidat T2 spec §10.

## Arketipe

Hibrida struktural yang berbeda dari sistem lain di grid ini: Dify sendiri
adalah **platform** yang memproduksi dua jenis aplikasi berbeda arketipe —
"Agent App" (`api/core/app/apps/agent_app/`, mendekati **In-App Copilot
(05)**: horizon per-percakapan, tool terbatas) dan "Workflow App"
(`api/core/app/apps/workflow/`, mendekati **Workflow Agent (06)**: DAG
node-based, bisa dipicu `trigger_schedule`/`trigger_webhook`/`trigger_plugin`
tanpa human-in-the-loop). `[code]` — listing `api/core/app/apps/*`
(`agent_app`, `agent_chat`, `workflow`, `advanced_chat`, `chat`,
`completion`, `pipeline`), `api/core/workflow/nodes/{trigger_schedule,
trigger_webhook,trigger_plugin}/`.

## 1. Loop shape

Dua runner agent berbeda, **keduanya** loop-until-done dengan batas iterasi
keras dari konfigurasi user, bukan sekadar jaring pengaman jauh:

- **`FunctionCallAgentRunner`** — tool-calling native provider. Loop:
  `iteration_step = 1; max_iteration_steps = min(app_config.agent.max_iteration,
  99) + 1; while function_call_state and iteration_step <=
  max_iteration_steps: ...`. Kalau iterasi mencapai batas **dan** masih ada
  `tool_calls` tertunda, harness melempar `AgentMaxIterationError` — bukan
  berhenti diam-diam. `[code]` — `api/core/agent/fc_agent_runner.py` baris
  46, 101, 119-148, 302-303, 403.
- **`CotAgentRunner`** (ABC, subclass untuk chat/completion) — pola
  ReAct berbasis teks (Thought/Action/Observation di-parse dari respons,
  lewat `ActionDict`/`scratchpad`), dipakai untuk model **tanpa** dukungan
  tool-calling native. Loop dan batas iterasi sama persis strukturnya
  dengan `FunctionCallAgentRunner` (`max_iteration_steps = min(...,99)+1`,
  `AgentMaxIterationError` di iterasi terakhir kalau `scratchpad.action`
  masih ada). `[code]` — `api/core/agent/cot_agent_runner.py` baris 33, 40,
  49, 79-80, 106-191, 266.

Batas maksimum absolut **99 iterasi** (`min(app_config.agent.max_iteration,
99)`) dikunci di kode — user bisa set lebih rendah lewat config app, tidak
bisa lebih tinggi. `[code]` — kedua runner, baris yang sama persis
(`min(app_config.agent.max_iteration, 99) + 1`).

Siapa yang memutuskan berhenti (kasus normal): model, dengan tidak lagi
menghasilkan tool call/action baru — `function_call_state` menjadi falsy.
Siapa yang memutuskan berhenti (kasus darurat): harness, lewat
`AgentMaxIterationError` — beda dari `deepagents` (limit sangat tinggi,
murni jaring pengaman) dan lebih dekat ke filosofi OpenHands
(`max_iteration_per_run=500` juga bisa memicu status `ERROR`).

## 2. Context

Tidak diverifikasi detail mekanisme compaction di task ini —
`api/core/memory/` ada sebagai direktori terpisah dari `api/core/agent/`
(memori percakapan lintas-turn untuk chat app), tapi isinya tidak dibaca.
`[code]` (listing) / tidak ada klaim mekanisme tanpa verifikasi lebih jauh.

## 3. Tool surface

**Paradigma berbeda dari agent-loop biasa**: tool surface Dify sebagian
besar bukan "daftar tool untuk satu model runtime", melainkan **katalog tipe
node dalam DAG visual** yang dirakit user di UI, tiap tipe node adalah unit
eksekusi berbeda: `agent`/`agent_v2` (node yang membungkus
`FunctionCallAgentRunner`/`CotAgentRunner`), `datasource`,
`knowledge_index`, `knowledge_retrieval`, `human_input` (lihat sumbu 6),
`trigger_plugin`/`trigger_schedule`/`trigger_webhook`. `[code]` — listing
`api/core/workflow/nodes/*` (9 subdirektori bertipe khusus; tipe node
lain seperti `llm`/`code`/`if-else`/`iteration` diduga terdaftar di modul
`NodeType` yang tidak ditemukan langsung lewat grep di task ini — lihat
catatan kejujuran).

Di dalam satu node `agent`, tool surface lebih konvensional: tool provider
terkatalog lewat `core/tools/` — `builtin_tool` (bawaan, mis.
`providers/time/`, `providers/audio/`), `plugin_tool` (ekosistem plugin
pihak ketiga), `mcp_tool` (server MCP eksternal), dan
**`workflow_as_tool`** (lihat sumbu 4). `[code]` — listing
`api/core/tools/{builtin_tool,plugin_tool,mcp_tool,workflow_as_tool}/`.

## 4. Delegation

**Bukan subagent spawn** — mekanisme komposisi utamanya adalah **workflow
lain sebagai tool**: `WorkflowTool` (`core/tools/workflow_as_tool/tool.py`,
subclass `Tool`) membungkus satu app workflow yang sudah dipublikasikan
sebagai tool yang bisa dipanggil dari agent/workflow lain — lengkap dengan
propagasi trace context lintas-panggilan
(`ParentTraceContext`/`extract_parent_trace_context_from_args`,
`extract_trace_session_id_from_args`) supaya observability tetap terhubung
lintas workflow-sebagai-tool. `[code]` —
`api/core/tools/workflow_as_tool/tool.py` baris 1-50.

Ini pola komposisi berbeda dari `task`-tool `deepagents`/OpenHands: bukan
"panggil agent lain dengan prompt", tapi "panggil pipeline DAG lain dengan
input terstruktur (schema tool parameter)" — hasil kembali sebagai
`ToolInvokeMessage` terstruktur, bukan ringkasan prosa transkrip subagent.
`[code]` — `api/core/tools/workflow_as_tool/tool.py` import
`ToolInvokeMessage`.

## 5. State & resume

Tidak diverifikasi detail skema DB (task ini tidak membaca migrasi/model
SQLAlchemy Dify). Yang dikonfirmasi: `models.workflow.Workflow` sebagai
entitas persisten yang dirujuk `WorkflowTool` (`workflow_app_id` di
constructor) — workflow adalah objek tersimpan dengan identitas stabil,
bukan didefinisikan ulang tiap panggilan. `[code]` — import
`models.workflow.Workflow`, parameter `workflow_app_id` di
`WorkflowTool.__init__` (`api/core/tools/workflow_as_tool/tool.py`).

## 6. Safety gate

Dua mekanisme gate berbeda level:

- **`human_input` node** — node DAG generik untuk jeda-tunggu-manusia,
  dengan submodul `pause_reason.py` (alasan pause terstruktur),
  `session_binding.py` (mengikat sesi pause ke identitas tertentu),
  `boundary.py`. Ini gate di level **desain workflow** (siapa pun yang
  merakit DAG bisa menaruh node ini di titik mana pun), bukan gate
  otomatis per-tool-berisiko seperti `interrupt_on` `deepagents` atau
  `ConfirmationPolicy` OpenHands. `[code]` — listing
  `api/core/workflow/nodes/human_input/*.py` (8 file).
- **Moderation input/output** — `core/moderation/base.py`: kelas abstrak
  `Moderation(Extensible, ABC)`, hasil `ModerationInputsResult`/
  `ModerationOutputsResult` dengan field `flagged: bool` dan
  `action: ModerationAction` (`DIRECT_OUTPUT` — balas respons preset tanpa
  lanjut ke model, atau `OVERRIDDEN` — konten diganti). Dipasang di dua
  titik terpisah: `input_moderation.py` (sebelum LLM/agent jalan) dan
  `output_moderation.py` (sebelum hasil dikirim ke user) — persis titik 1
  dan 4 dari enam titik penegakan guardrail §8.4 spec desain. Implementasi
  konkret: `keywords/` (deterministik), `openai_moderation/` (model-based,
  provider eksternal) — pola bertingkat murah-dulu yang sama dengan
  argumen §8.4. `[code]` — `api/core/moderation/base.py` baris 1-30;
  listing `api/core/moderation/{keywords,openai_moderation,api}/`.

## 7. Capability routing & policy

**Konfigurasi statis per-app + katalog node visual — bukan classifier,
bukan judgment model runtime untuk memilih arsitektur.** Pemilihan strategi
loop (`FunctionCallAgentRunner` vs `CotAgentRunner`) dan tipe node dalam DAG
diputuskan **saat desain app** (oleh pembuat app di UI/config, berdasar
apakah model target mendukung tool-calling native), bukan oleh model itu
sendiri saat runtime memilih di antara mode. `[code]` — keberadaan dua
kelas runner terpisah dengan tanda tangan hampir identik menunjukkan
pemilihan terjadi di lapisan konfigurasi app (`app_config.agent`), bukan
dispatch dinamis dalam satu loop.

Di dalam satu node `agent`, pemilihan tool tetap **judgment model** standar
(model memilih tool dari daftar yang di-expose node itu) — tidak ada
classifier tambahan yang ditemukan. Provider tool sendiri
(`builtin_tool`/`plugin_tool`/`mcp_tool`/`workflow_as_tool`) adalah
**registry deklaratif**: tool mana yang tersedia untuk satu node ditentukan
konfigurasi node (dipilih user di UI), bukan otomatis. `[code]` — struktur
`core/tools/tool_manager.py`, `core/tools/__base/tool_provider.py` (nama
file dikonfirmasi, isi tidak dibaca detail).

## Sumber

Repo `langgenius/dify` dikloning shallow (`git clone --depth 1`) 2026-08-23
dan dibaca langsung sebagai file:

- `api/core/agent/fc_agent_runner.py` — baris 46, 101, 119-148, 302-303,
  403 (loop, `max_iteration_steps`, `AgentMaxIterationError`)
- `api/core/agent/cot_agent_runner.py` — baris 33-49, 79-80, 106-191, 266
  (loop, `ActionDict`, `scratchpad`)
- `api/core/moderation/base.py` — baris 1-30 (utuh untuk bagian dikutip:
  `ModerationAction`, `ModerationInputsResult`, `ModerationOutputsResult`,
  kelas `Moderation`)
- `api/core/tools/workflow_as_tool/tool.py` — baris 1-50 (import, kelas
  `WorkflowTool`, constructor `workflow_app_id`)
- Listing direktori (nama file/folder via `find`/`ls`, isi tidak dibaca
  penuh): `api/core/app/apps/*` (7 tipe app), `api/core/workflow/nodes/*`
  (9 subdirektori bertipe), `api/core/workflow/nodes/human_input/*.py` (8
  file), `api/core/tools/{builtin_tool,plugin_tool,mcp_tool,
  workflow_as_tool}/`, `api/core/moderation/{keywords,openai_moderation,
  api}/`, `api/core/memory/`

Catatan kejujuran: pencarian `class NodeType` lewat `grep -rln` di
`api/core/workflow/` tidak menemukan definisi enum tipe-node lengkap
(kemungkinan didefinisikan di modul luar `nodes/`, mis. paket bersama
`core/workflow/enums.py` yang tidak ditemukan/dibaca) — daftar tipe node di
sumbu 3 dibatasi pada subdirektori yang benar-benar terlihat lewat listing,
**bukan** daftar node lengkap Dify (tipe umum seperti `llm`, `code`,
`if-else`, `iteration`, `http-request` yang dikenal luas dari dokumentasi
publik Dify **tidak** diverifikasi ulang di source pada task ini — tidak
diklaim ada/tidak ada). `api/core/memory/`, skema DB workflow, dan detail
`tool_manager.py`/`tool_provider.py` **tidak** dibaca isinya — hanya
keberadaan filenya yang dikutip.
