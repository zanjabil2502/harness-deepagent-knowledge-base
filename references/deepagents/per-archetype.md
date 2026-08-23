# `deepagents` per arketipe — konstruksi yang benar

Untuk tiap arketipe di [`../archetypes/`](../archetypes/README.md): middleware
apa, backend apa, subagent apa, batas loop apa, handler apa. Ini menyatukan
rasional arketipe dengan API konkret; rasional lengkapnya tidak diulang di
sini.

Baca dulu [`extension-points.md`](extension-points.md) — semua konstruksi di
bawah tunduk pada aturan keras di sana. Semua penyimpangan berlabel `[ours]`
tercatat di [`conformance.md`](conformance.md).

## Ringkasan

| # | Arketipe | Backend | Subagent | Gate | Batas loop |
|---|---|---|---|---|---|
| 01 | Workspace Agent | `LocalShellBackend(root_dir=repo)` | tidak (default) | `interrupt_on` per tool tulis/`execute` | `recursion_limit` sedang + `ToolCallLimitMiddleware` |
| 02 | Generative Builder | backend sandbox (`DaytonaSandbox` dsb.) | opsional | gate hanya di tool publish/deploy | `recursion_limit` longgar |
| 03 | General Task Agent | `CompositeBackend(StateBackend, {"/memories/": StoreBackend})` | ya, beberapa | checkpoint, bukan per langkah | `ModelCallLimitMiddleware` + guard pengulangan |
| 04 | Research/Analyst | `StateBackend` atau `CompositeBackend` | ya, per sub-topik | tidak (read-only) | `ToolCallLimitMiddleware(tool_name="task")` |
| 05 | In-App Copilot | `StateBackend` | tidak | tool `undo_*`, bukan `interrupt_on` | `recursion_limit` ketat |
| 06 | Workflow Agent | `StoreBackend(namespace=...)` | opsional | `interrupt_on` async lewat dashboard | `recursion_limit` ketat + `ModelCallLimitMiddleware(exit_behavior="error")` |
| 07 | Computer-Use Agent | backend sandbox untuk sesi browser | opsional | `interrupt_on` untuk aksi ireversibel | `ToolCallLimitMiddleware` per tool aksi |

---

## 01 — Workspace Agent

**Backend**: `LocalShellBackend(root_dir="<repo>", virtual_mode=True)`.
`virtual_mode` mengurung operasi file ke `root_dir` tapi **tidak** membatasi
`execute()` — docstring backend-nya sendiri menyatakan itu. `[code]` —
`deepagents/backends/local_shell.py` baris 26-105.

**Middleware**: cukup stack default. Tambahkan `TodoListMiddleware()` hanya
kalau tugas repo-nya multi-langkah panjang; tidak wajib.

**Subagent**: tidak dipakai sebagai default (`[ours]`, lihat
[`conformance.md`](conformance.md) D-01).

**Gate**: `interrupt_on={"execute": True, "write_file": True, "edit_file": True,
"delete": True}` + `checkpointer` wajib (tanpa checkpointer interrupt tidak
bisa di-resume).

⚠️ Jangan pakai `permissions=` bersama backend ini: `FilesystemMiddleware`
**raise `NotImplementedError`** untuk `permissions` + backend
`SandboxBackendProtocol` yang path-nya tidak ter-scope ke route. `[code]` —
`deepagents/middleware/filesystem.py` baris 1691-1700. Ada dua jalan keluar
resmi:

1. `interrupt_on` per tool, atau `wrap_tool_call` allow-list command (pola
   `ShellAllowListMiddleware` maintainer).
2. **Rutekan setiap path yang di-`permissions` ke backend non-eksekusi.**
   Pengecekan `_all_paths_scoped_to_routes` lolos kalau semua pola rule
   berada di route `CompositeBackend`, bukan di backend default yang
   ber-shell. Ini persis yang dilakukan `examples/llm-wiki/helpers.py`
   (baris 548-565, 623-638): default `LangSmithSandbox`, route
   `/raw/`, `/wiki/`, `/log.md`, `/AGENTS.md` ke
   `FilesystemBackend(root_dir=workspace)`, dan `permissions` hanya menyentuh
   keempat prefix itu. `[code]` — repo `langchain-ai/deepagents`
   commit `23b83ad`.

**Batas loop**: `.with_config({"recursion_limit": 150})` — cukup untuk sesi
edit panjang, jauh di bawah default `9_999`.

```python
agent = create_deep_agent(
    model=ChatAnthropic(model_name="claude-sonnet-4-6"),
    system_prompt=WORKSPACE_PROMPT,
    backend=LocalShellBackend(root_dir=repo_path, virtual_mode=True),
    interrupt_on={"execute": True, "write_file": True, "edit_file": True, "delete": True},
    checkpointer=checkpointer,
).with_config({"recursion_limit": 150})
```

---

## 02 — Generative Builder

**Backend**: keluarga sandbox. `DaytonaSandbox(sandbox=Daytona().create(),
timeout=300)` dari paket `langchain-daytona` (keyword-only), atau
`LangSmithSandbox(sandbox)` bawaan `deepagents`. Untuk deployment lewat CLI
`deepagents`, `agent.json`:
`{"backend": {"type": "sandbox", "sandbox_config": {"scope": "thread",
"policy_ids": [...]}}}` — kunci `sandbox_config` diverifikasi di
`libs/cli/deepagents_cli/deploy/project.py` dan
`libs/cli/tests/unit_tests/deploy/test_project.py` baris 219-249. `[code]` —
repo `langchain-ai/deepagents` commit `23b83ad`.

**Middleware**: stack default. `FilesystemMiddleware` otomatis mengekspos
`execute` karena backend sandbox mengimplementasi `SandboxBackendProtocol`.

**Subagent**: opsional. Kalau ada tahap panjang yang bisa dipisah (mis.
"generate aset" vs "susun halaman"), pakai `SubAgent` dengan `tools` sempit.

**Gate**: `interrupt_on` hanya di tool publish/deploy buatan sendiri
(`interrupt_on={"publish": True}`); loop build/iterate sengaja tanpa gate
(`[ours]` D-02).

**Persistence**: tanpa `checkpointer`/`store` untuk sesi sekali pakai. Kalau
artefak harus bertahan, tambahkan route durable:
`CompositeBackend(default=sandbox_backend, routes={"/exports/": StoreBackend(namespace=...)})`
— pilihan eksplisit, bukan default.

**Batas loop**: `recursion_limit` longgar (mis. 300) karena iterasi
build-preview memang banyak; batas nyata datang dari budget token
(`ModelCallLimitMiddleware(thread_limit=...)`) bukan dari jumlah langkah.

---

## 03 — General Task Agent

**Backend**: `CompositeBackend(default=StateBackend(), routes={"/memories/":
StoreBackend(namespace=lambda rt: (user_id, "memories"))})` — kerja
sehari-hari ephemeral, memory persisten durable dan ter-scope per user.
Ini pola hybrid yang dicontohkan docstring `FilesystemMiddleware` sendiri.

**Middleware**:
- `TodoListMiddleware()` lewat `middleware=[...]` — planning eksplisit adalah
  pembeda arketipe ini, dan middleware ini **bukan** bagian stack default
  `create_deep_agent`. `[code]` — verifikasi runtime: stack default adalah
  `FilesystemMiddleware, SubAgentMiddleware, SummarizationMiddleware,
  PatchToolCallsMiddleware, AnthropicPromptCachingMiddleware`; satu-satunya
  tempat `TodoListMiddleware` muncul di `deepagents` 0.7.8 adalah profil
  `_openai_codex.py`.
- `memory=["/memories/AGENTS.md"]` untuk konteks persisten.
- `ModelCallLimitMiddleware(thread_limit=..., exit_behavior="end")`.

**Subagent**: beberapa `SubAgent` deklaratif dengan `tools` dan `model`
berbeda per subtugas — persis pola `examples/nvidia_deep_agent/src/agent.py`
(researcher + data-processor) dan `examples/content-builder-agent/`.

**Gate**: review di checkpoint, bukan per langkah. `interrupt_on` hanya untuk
aksi keluar sistem (kirim email, panggil API pihak ketiga).

**Batas loop**: `ModelCallLimitMiddleware` untuk budget, plus guard
pengulangan tool-call identik (`[ours]` D-03) — `ToolCallLimitMiddleware`
menghitung total panggilan, bukan pengulangan, jadi tidak menangkap agent
yang berputar di tempat.

---

## 04 — Research/Analyst

**Backend**: `StateBackend` cukup untuk satu sesi riset; naikkan ke
`CompositeBackend` dengan route durable kalau laporan harus bertahan.

**Middleware**: stack default. `SummarizationMiddleware` bawaan penting di
sini — hasil pencarian besar otomatis di-evict ke
`/large_tool_results/` oleh `FilesystemMiddleware` sebelum membanjiri context.

**Subagent**: satu `SubAgent` riset per sub-topik, dengan `tools` sempit
(`[web_search, think_tool]`) dan **tanpa** akses filesystem luas. Ini persis
konstruksi maintainer di `examples/deep_research/agent.py`.

```python
research_sub_agent: SubAgent = {
    "name": "research-agent",
    "description": "Delegate research to the sub-agent researcher. Only give this researcher one topic at a time.",
    "system_prompt": RESEARCHER_INSTRUCTIONS,
    "tools": [web_search, think_tool],
}
agent = create_deep_agent(
    model=model,
    tools=[web_search, think_tool],
    system_prompt=ORCHESTRATOR_INSTRUCTIONS,
    subagents=[research_sub_agent],
    response_format=ResearchReport,
)
```

**Gate**: tidak ada — arketipe ini read-only terhadap dunia luar.

**Output**: `response_format=<skema laporan>` untuk memaksa bentuk keluaran.
⚠️ `response_format` memvalidasi **bentuk**, bukan kebenaran isi; sitasi
halusinasi tetap lolos. Validasi provenance post-hoc adalah `[ours]` (D-04).

**Batas loop**: batas eksplisit di prompt orchestrator
(`max_concurrent_research_units`, `max_researcher_iterations` — pola
maintainer di `examples/deep_research/agent.py`) **plus**
`ToolCallLimitMiddleware(tool_name="task", thread_limit=N)` sebagai penegak
struktural, karena batas di prompt hanya instruksi.

---

## 05 — In-App Copilot

**Tool surface**: `tools=[...]` berisi wrapper tipis ke endpoint API produk
tuan rumah. Tool filesystem bawaan tidak relevan.

**Cara menghilangkannya** — dua jalur resmi, keduanya jauh lebih tepat
daripada `permissions`:

```python
# per agent, dengan mengganti instance FilesystemMiddleware di tempat
agent = create_deep_agent(
    model=model,
    tools=product_tools,
    middleware=[FilesystemMiddleware(backend=backend, tools=["read_file"])],
)

# atau, untuk semua stack sekaligus (main + subagent)
register_harness_profile(
    "anthropic:claude-sonnet-4-6",
    HarnessProfile(
        excluded_tools=frozenset({"write_file", "edit_file", "delete", "glob", "grep", "execute", "ls"}),
        general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
    ),
)
```

`read_file` **wajib** ada dalam `FilesystemMiddleware(tools=[...])` —
kalau tidak, `ValueError`. `FilesystemMiddleware` sendiri tidak bisa dibuang
(`excluded_middleware` menolaknya). `[code]` —
`deepagents/middleware/filesystem.py` baris 1670-1673;
`deepagents/graph.py` baris 287-314.

Arketipe ini juga satu-satunya yang wajar mematikan tool `task`:
`GeneralPurposeSubagentProfile(enabled=False)` + tanpa subagent sinkron.

**Backend**: `StateBackend` default. Sumber kebenaran ada di produk tuan
rumah, bukan di agent.

**Context**: `context_schema=` untuk state aplikasi per panggilan, bukan
`memory=` lintas sesi — horizon arketipe ini pendek.

**Gate**: tool `undo_<aksi>` dipanggil dari UI host, bukan `interrupt_on`
(`[ours]` D-05).

**Batas loop**: `recursion_limit` ketat (mis. 25) — copilot yang berpikir
lama adalah regresi UX.

---

## 06 — Workflow Agent

**Loop shape**: `create_deep_agent(...)` sebagai satu node di dalam graph
LangGraph yang lebih besar, atau di belakang worker antrian yang dipicu
event. `deepagents` menentukan "apa yang dilakukan LLM saat dipanggil",
bukan "kapan dipanggil" (`[ours]` D-06).

**Backend**: `StoreBackend(namespace=lambda rt: (tenant_id, "workflow"))` —
durable dan ter-scope; tidak ada sesi interaktif yang menjaganya.

**Idempotency**: `checkpointer` disuntikkan aplikasi + `thread_id` diturunkan
dari idempotency key event, bukan random (`[ours]` D-06b). Retry event yang
sama jatuh ke checkpoint yang sama.

**Gate**: `interrupt_on={"send_email": True}` tetap masuk akal meski tidak
ada manusia real-time — interrupt LangGraph berarti run **berhenti dan
menunggu**, approval bisa datang async lewat dashboard/Slack. Ini butuh
`checkpointer` durable, bukan `MemorySaver`.

**Error handling**: ini arketipe yang paling butuh
`ToolRetryMiddleware`/`ModelRetryMiddleware`, karena tidak ada manusia yang
mencoba ulang secara manual.

**Batas loop**: `recursion_limit` ketat +
`ModelCallLimitMiddleware(thread_limit=..., exit_behavior="error")` —
`"error"` (bukan `"end"`) supaya run yang lewat budget terlihat sebagai
kegagalan di dashboard, bukan selesai diam-diam.

**Kill switch**: tidak ada di `deepagents` (`[ours]` D-06c) — flag di
database yang dicek worker sebelum memanggil agent.

---

## 07 — Computer-Use Agent

**Tool surface**: `tools=[screenshot, click, type_text, scroll, verify_state]`
custom yang memetakan ke driver browser eksternal. `deepagents` tidak punya
tool computer-use bawaan.

**Backend**: backend sandbox untuk sesi browser, setara arketipe 02 — sesi
browser yang crash/di-abuse tidak boleh menyentuh compute lain.

**Gate**: `interrupt_on={"submit_form": True, "click": {"allowed_decisions":
["approve", "reject"]}}` untuk aksi ireversibel. Predikat
`InterruptOnConfig.when` berguna di sini: interrupt hanya kalau selector yang
diklik masuk daftar berisiko, bukan tiap klik.

**Verifikasi**: tool `verify_state` wajib dipanggil setelah tiap aksi UI,
ditegakkan lewat instruksi system prompt (`[ours]` D-07).
`deepagents` **tidak** punya middleware yang menegakkan urutan pemanggilan
tool. `PatchToolCallsMiddleware` sering dikira melakukannya — perannya hanya
menambal `ToolMessage` untuk tool call dangling/dibatalkan/rusak, bukan
menegakkan urutan. `[code]` —
`deepagents/middleware/patch_tool_calls.py` baris 14-45.

Penegakan yang lebih kuat dari prompt (tapi tetap bukan jaminan struktural):
`wrap_tool_call` yang menolak aksi UI kedua berturut-turut tanpa
`verify_state` di antaranya, mengembalikan `ToolMessage(status="error")`.
Pola yang sama dengan `ShellAllowListMiddleware` maintainer.

**Batas loop**: `ToolCallLimitMiddleware(tool_name="click", thread_limit=N,
exit_behavior="end")` — arketipe paling rapuh, paling butuh batas keras per
tool aksi.

## Sumber

**Versi yang dibaca**: `deepagents==0.7.8`, `langchain==1.3.16`, dari
`references/recipes/.venv/lib/python3.13/site-packages/`.

`[code]` paket terinstal: `deepagents/graph.py`,
`deepagents/backends/{local_shell,composite,store,state}.py`,
`deepagents/middleware/{filesystem,subagents,patch_tool_calls}.py`,
`deepagents/profiles/harness/{harness_profiles.py,_openai_codex.py}`,
`langchain/agents/middleware/{model_call_limit,tool_call_limit,tool_retry,model_retry}.py`.

`[code]` dari `git clone --depth 1 langchain-ai/deepagents` (commit
`23b83ad`, 2026-08-21):
`examples/deep_research/agent.py`,
`examples/nvidia_deep_agent/src/agent.py`,
`examples/content-builder-agent/content_writer.py`,
`examples/text-to-sql-agent/agent.py`,
`examples/async-subagent-server/{supervisor,server}.py`,
`examples/better-harness/better_harness/agent.py`,
`examples/ralph_mode/ralph_mode.py`,
`libs/cli/deepagents_cli/deploy/project.py`,
`libs/cli/tests/unit_tests/deploy/test_project.py`,
`libs/code/deepagents_code/agent.py`,
`libs/partners/daytona/langchain_daytona/sandbox.py`.

Rasional per arketipe: [`../archetypes/`](../archetypes/README.md).
Divergensi berlabel `[ours]` (D-01 … D-07): [`conformance.md`](conformance.md).
