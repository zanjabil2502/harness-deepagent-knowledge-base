# `deepagents`

> Label tiap klaim: [code] / [docs] / [inferred]

Tier **T1** — bedah dalam. Semua klaim `[code]` dibaca langsung dari paket
`deepagents==0.7.8` terinstal (`uv sync` dari `references/recipes/pyproject.toml`,
diverifikasi lewat `deepagents.__version__` dan direktori
`deepagents-0.7.8.dist-info`), plus `langchain==1.3.16` dan `langgraph==1.2.11`
yang menjadi fondasinya. Detail lengkap sumber ada di `## Sumber`.

## Arketipe

`deepagents` **bukan** satu arketipe — ia SDK harness yang dipakai untuk
membangun archetype apa pun di grid ini; instansiasinya (backend + middleware +
`interrupt_on`/`permissions` yang dipasang) yang menentukan archetype akhir.
Dokumentasi resmi menggambarkannya sebagai lapisan tengah dari tiga: `[docs]`

```
Deep Agents  -> harness beropini: middleware, backend, profile, subagent
LangChain    -> abstraksi agent: model + tools + middleware
LangGraph    -> runtime eksekusi: state, checkpoint, streaming, interrupt
```

(`openwiki/architecture/overview.md`, langchain-ai/deepagents, dikutip lewat
Context7 `/langchain-ai/deepagents`). Default stack-nya (filesystem sebagai
memori, `task` tool + subagent general-purpose otomatis, tanpa todo eksplisit)
paling dekat dengan **General Task Agent (03)**, tapi tiap axis di bawah bisa
digeser lewat parameter `create_deep_agent(...)` untuk membentuk archetype lain
(mis. `Workspace Agent` lewat `LocalShellBackend`, `Generative Builder` lewat
backend sandbox). `[code]` — `deepagents/graph.py`.

## 1. Loop shape

`create_deep_agent(...)` adalah pembangun graph tipis di atas
`langchain.agents.create_agent(...)`: seluruh middleware dirakit jadi satu
`list[AgentMiddleware]`, lalu diteruskan ke `create_agent()` yang mengembalikan
`CompiledStateGraph` LangGraph. `[code]` — `deepagents/graph.py` baris 922-934.

`create_agent()` sendiri didokumentasikan sebagai "creates an agent graph that
calls tools in a loop until a stopping condition is met" — loop ReAct standar
(model node ⇄ tool node) yang berhenti ketika `AIMessage` terakhir tidak berisi
`tool_calls`, bukan diputuskan oleh `deepagents`. `[code]` —
`langchain/agents/factory.py` baris 859-860 (docstring `create_agent`).

`deepagents` menaikkan `recursion_limit` LangGraph dari default 25 menjadi
**9999** lewat `.with_config({"recursion_limit": 9_999, ...})` yang dipasang di
setiap agent yang dibangun `create_deep_agent` — bukan mekanisme "kapan
berhenti" tapi jaring pengaman supaya task deep-agent yang panjang tidak
kepotong `GraphRecursionError` pada limit default LangGraph yang jauh lebih
kecil. `[code]` — `deepagents/graph.py` baris 935-944.

## 2. Context

Tiga mekanisme berjalan **default**, tanpa perlu dikonfigurasi eksplisit:

- **`SummarizationMiddleware`** (via `create_summarization_middleware(model,
  backend)`) selalu ada di stack utama maupun tiap subagent. Threshold
  trigger/keep/`truncate_args_settings` dihitung otomatis dari profil model
  (`compute_summarization_defaults`, berbasis `max_input_tokens`). Saat token
  terlampaui, pesan lama dikompaksi jadi ringkasan; ini *middleware milik
  deepagents* yang membungkus `langchain.agents.middleware.SummarizationMiddleware`
  untuk menambah kesadaran backend/file. `[code]` —
  `deepagents/middleware/summarization.py`.
- **`FilesystemMiddleware`** meng-*evict* hasil tool yang besar ke backend
  filesystem begitu melewati `tool_token_limit_before_evict` (default 20000
  token) atau `human_message_token_limit_before_evict` (default 50000) —
  hasil asli ditulis ke path, lalu pesan digantikan preview head/tail +
  rujukan path (`TOO_LARGE_TOOL_MSG`). Ini pola *filesystem-as-memory*: bukan
  dibuang, tapi dipindah ke penyimpanan yang bisa dibaca ulang lewat
  `read_file`. `[code]` — `deepagents/middleware/filesystem.py` baris
  1556-1630, `deepagents/middleware/_message_eviction.py`.
- **`DeepAgentState.messages`** memakai reducer LangGraph
  `DeltaChannel(_messages_delta_reducer, snapshot_frequency=50)`, yang
  menurunkan pertumbuhan ukuran checkpoint dari O(N²) ke O(N) — signifikan
  untuk sesi panjang bertumpuk-tumpuk pesan. `[code]` — `deepagents/graph.py`
  baris 70-73.

Mekanisme opsional:

- **`SummarizationToolMiddleware`** (via `create_summarization_tool_middleware`)
  menambah tool `compact_conversation` untuk kompaksi manual dipicu model/user,
  memakai mesin ringkas yang sama dengan `SummarizationMiddleware` tapi tidak
  pernah kompaksi otomatis sendiri. `[code]` —
  `deepagents/middleware/summarization.py`.
- **`memory=["./AGENTS.md", ...]`** pada `create_deep_agent` memicu
  `MemoryMiddleware`, yang memuat isi file `AGENTS.md` ke system prompt saat
  startup (bukan filesystem-as-memory dinamis, tapi context statis yang
  disuntik sekali di awal sesi). `[code]` — `deepagents/middleware/memory.py`.
- **`AnthropicPromptCachingMiddleware`** selalu ditambahkan tanpa syarat
  (no-op untuk model non-Anthropic) via `append_prompt_caching_middleware`;
  `BedrockPromptCachingMiddleware`/`FireworksPromptCachingMiddleware` ikut
  ditambahkan otomatis kalau `langchain-aws`/`langchain-fireworks` terpasang.
  Ini trade-off compaction vs prompt-cache eksplisit:
  `AnthropicPromptCachingMiddleware` ditambahkan ke stack **sebelum**
  `MemoryMiddleware` (`deepagents/graph.py` baris 860 vs baris 861-870,
  bukan urutan sebaliknya) — update memory tidak merusak prefix cache
  bukan karena urutan middleware itu, tapi karena `MemoryMiddleware`
  sendiri menandai blok terakhir system message dengan `cache_control`
  lewat parameter `add_cache_control=True` (di-set `True` untuk instance
  di stack utama), diterapkan hanya kalau model target `ChatAnthropic`.
  `[code]` — `deepagents/middleware/_prompt_caching.py`,
  `deepagents/middleware/memory.py` baris 193, 342-374,
  `deepagents/graph.py` baris 856-870.
- **`PatchToolCallsMiddleware`** selalu ada di stack utama maupun subagent —
  menambal `ToolMessage` sintetis untuk tool call yang dangling/dibatalkan di
  riwayat pesan (mis. akibat interrupt atau ringkasan), menjaga riwayat pesan
  tetap valid untuk model berikutnya. `[code]` —
  `deepagents/middleware/patch_tool_calls.py`.

## 3. Tool surface

Sedikit tool luas, bukan banyak tool sempit — by design. Tool bawaan `execute`
tetap satu nama meski implementasinya berubah total tergantung backend, `[code]`
per docstring `create_deep_agent`:

- `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep` — dari
  `FilesystemMiddleware`, selalu ada.
- `execute` — hanya muncul jika `backend` yang dipasang mengimplementasi
  `SandboxBackendProtocol`; untuk backend non-sandbox, `FilesystemMiddleware`
  memfilternya keluar sama sekali (bukan tool yang mengembalikan error, tool
  itu tidak diekspos ke model). `[code]` — `deepagents/backends/protocol.py`
  baris 840-939, dikonfirmasi oleh `THREAT_MODEL.md` (langchain-ai/deepagents):
  *"the execute tool is filtered out by FilesystemMiddleware when the backend
  does not implement SandboxBackendProtocol"*.
- `task` — dari `SubAgentMiddleware`, hanya muncul jika ada subagent inline
  (default: subagent `general-purpose` selalu ditambahkan kecuali dimatikan
  lewat profil).
- `tools=[...]` pada `create_deep_agent` bersifat **aditif** — selalu
  digabung dengan tool bawaan di atas, tidak pernah menggantikannya. Untuk
  mencabut tool bawaan, satu-satunya jalur resmi adalah
  `HarnessProfile.excluded_tools` (lewat `_ToolExclusionMiddleware`, dijalankan
  paling akhir di stack supaya tool yang disuntik middleware lain pun ikut
  tersaring). `[code]` — `deepagents/graph.py` baris 331-339, 787-788,
  `deepagents/middleware/_tool_exclusion.py`.
- `FsToolName = Literal["ls", "read_file", "write_file", "edit_file",
  "delete", "glob", "grep", "execute"]` — enumerasi resmi nama tool
  filesystem/eksekusi (`delete` ada di literal tapi hanya terpasang jika
  backend mendukungnya). `[code]` — `deepagents/middleware/filesystem.py`
  baris 1345.

## 4. Delegation

Tiga jalur delegasi, tidak flat:

- **`SubAgent`** (dict deklaratif: `name`, `description`, `system_prompt`,
  opsional `tools`/`model`/`middleware`/`interrupt_on`/`skills`/
  `permissions`/`response_format`) — dipanggil lewat tool `task` yang
  dibangun `SubAgentMiddleware`. Subagent otomatis mendapat stack middleware
  dasarnya sendiri (`FilesystemMiddleware` + `SummarizationMiddleware` +
  `PatchToolCallsMiddleware`, lalu `custom middleware` milik spec) sebelum
  custom `middleware` di spec-nya dijalankan. `[code]` —
  `deepagents/graph.py` baris 645-743, `deepagents/middleware/subagents.py`.
- **`CompiledSubAgent`** — runnable yang sudah dikompilasi sendiri oleh
  caller, dipakai apa adanya; tidak mewarisi `state_schema` dari
  `create_deep_agent`. `[code]` — `deepagents/middleware/subagents.py`.
- **`AsyncSubAgent`** — subagent remote/background via LangGraph SDK ke
  server Agent Protocol (LangGraph Platform/LangSmith Deployment terkelola
  atau self-hosted). Dirutekan ke `AsyncSubAgentMiddleware`, bukan
  `SubAgentMiddleware`, dan mengekspos lima tool berbeda:
  `start_async_task`, `check_async_task`, `update_async_task`,
  `cancel_async_task`, `list_async_tasks` — berjalan non-blocking, agent
  utama bisa lanjut bekerja sambil subagent async berjalan. `[code]` —
  `deepagents/middleware/async_subagents.py`.

Subagent `general-purpose` otomatis ditambahkan kecuali caller sudah
menyediakan subagent bernama sama, atau profil harness men-set
`general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)`.
`[code]` — `deepagents/graph.py` baris 745-814.

**Hasil kembali ke pemanggil**: isi `ToolMessage` dari tool `task` **bukan**
seluruh `messages` state akhir subagent. `_return_command_with_state_update`
memilih salah satu dari dua: kalau `structured_response` hasil subagent tidak
`None`, nilainya diserialkan ke JSON (`model_dump_json()` untuk Pydantic,
`json.dumps(dataclasses.asdict(...))` untuk dataclass, `json.dumps(...)`
selain itu) dan itulah isi `ToolMessage`-nya; kalau `None`, kode berjalan
mundur dari pesan terakhir dan memakai teks `AIMessage` **non-kosong**
pertama yang ditemukan (walk-back ini ada karena Anthropic kadang menutup
dengan `AIMessage` `end_turn` kosong). Hasilnya tetap seperti yang
diharapkan — ringkasan bersih, bukan transkrip kerja subagent — tapi
mekanismenya seleksi satu pesan, bukan penyalinan state pesan.

Di luar `messages`, key state lain yang dikembalikan subagent **memang**
di-merge ke state agent utama, kecuali `_EXCLUDED_STATE_KEYS`
(`messages`, `todos`, `structured_response`) dan field privat. State privat
subagent (field bertanda `PrivateStateAttr` di middleware manapun,
dikumpulkan lewat `private_state_field_names`) tidak bocor kembali ke state
agent utama — filter yang sama juga dipakai saat mengirim state parent
**ke** subagent. `[code]` —
`deepagents/middleware/subagents.py` baris 251-268 (`_EXCLUDED_STATE_KEYS`),
474-512 (`_return_command_with_state_update`), 529-540
(`_validate_and_prepare_state`); `deepagents/graph.py` baris 943-947.

## 5. State & resume

`checkpointer` dan `store` di `create_deep_agent` diteruskan **apa adanya**
ke `langchain.agents.create_agent(...)` — `deepagents` tidak pernah
membangun checkpointer/store sendiri, aplikasi pemanggil yang menyuntikkannya.
`[code]` — `deepagents/graph.py` baris 546-553, 922-931 (parameter
`checkpointer`, `store` diteruskan langsung).

Peta lapisan state konkret:

| Lapis | Mekanisme deepagents |
|---|---|
| Transcript per-thread | `DeepAgentState.messages` (`DeltaChannel`, resumable via `checkpointer` yang disuntik aplikasi) |
| File ephemeral | `StateBackend` (default) — hidup di state LangGraph, checkpoint otomatis per step, tidak lintas thread |
| File durable lintas-thread | `StoreBackend(namespace=...)` di atas `store` yang disuntik aplikasi |
| Task subagent async | `AsyncSubAgentState.tasks` (dict `task_id -> AsyncTask`, status di-cache lalu dicek ulang ke server) |
| Iterasi self-eval | `RubricState` (private: status, iteration count, riwayat evaluasi) — hanya aktif kalau caller mengirim `rubric` di state invoke |

Tidak ada mekanisme todo/scratchpad bawaan di stack default — `DeepAgentState`
hanya menambah reducer pesan, tanpa field `todos`. `TodoListMiddleware`
(sumbernya `langchain.agents.middleware`, bukan `deepagents`) harus
ditambahkan eksplisit lewat `middleware=[TodoListMiddleware()]`; ia tidak
masuk daftar base-stack manapun di `create_deep_agent`. `[code]` —
`deepagents/graph.py` baris 361-402 (daftar lengkap base stack tidak
menyebut `TodoListMiddleware`), `langchain/agents/middleware/todo.py`.

## 6. Safety gate

Dua jalur gate independen, bisa dipakai bersamaan:

1. **`interrupt_on={"tool_name": True | InterruptOnConfig}`** — mem-instal
   `HumanInTheLoopMiddleware` (dari `langchain.agents.middleware`) hanya jika
   hasil merge (`_merge_fs_interrupt_on`) tidak kosong; kalau kosong,
   middleware itu tidak dipasang sama sekali (tanpa overhead). `[code]` —
   `deepagents/graph.py` baris 871-876. `InterruptOnConfig` mendukung
   `allowed_decisions` (subset dari `"approve"/"edit"/"reject"/"respond"`)
   per tool. `[code]` — `langchain/agents/middleware/human_in_the_loop.py`.
2. **`permissions=[FilesystemPermission(operations=[...], paths=[...],
   mode="allow"|"deny"|"interrupt")]`** — aturan dievaluasi berurutan, match
   pertama menang, default `allow` kalau tak ada yang match. `mode="deny"`
   membuat tool mengembalikan pesan permission-denied (tanpa jeda);
   `mode="interrupt"` **otomatis** membangkitkan entri `interrupt_on` lewat
   `_build_interrupt_on_from_permissions`, lalu digabung dengan `interrupt_on`
   eksplisit (entri user menang per nama tool bila bentrok). Rule
   `"interrupt"` butuh versi `langchain` yang mendukung predikat `when` pada
   `InterruptOnConfig`. `[code]` — `deepagents/middleware/filesystem.py`
   baris 384-419, `deepagents/middleware/_fs_interrupt.py`.

Subagent (`SubAgent`) mewarisi `interrupt_on`/`permissions` milik agen utama
secara default; menyatakan field itu sendiri di spec-nya **menggantikan**
total, bukan menggabung. `CompiledSubAgent`/`AsyncSubAgent` tidak mewarisi
apa pun — HITL untuk keduanya harus dikonfigurasi di dalam
runnable/server-nya sendiri. `[code]` — docstring parameter `interrupt_on`,
`permissions` di `deepagents/graph.py`.

**Sandbox**: `execute` hanya jalan lewat backend yang mengimplementasi
`SandboxBackendProtocol`. Menurut `THREAT_MODEL.md` (langchain-ai/deepagents,
dikutip via WebFetch): `LocalShellBackend` *"is not the default; it must be
explicitly provided by the user"*, dan menjalankan command lewat
`subprocess.run(shell=True)` tanpa validasi isi command selain cek non-kosong
— *"passes the LLM-generated command string directly to subprocess.run
(shell=True)...Zero validation on command content"*. Penting: `virtual_mode`
pada `FilesystemBackend`/`LocalShellBackend` **hanya** membatasi operasi file
(`read_file`/`write_file`/dst) ke `root_dir`; `execute()` **tidak** ikut
dibatasi — *"Even when virtual_mode=True restricts file operation paths to
root_dir, the execute() method runs shell commands without path
restrictions."* `[code]`/`[docs]` (kutipan langsung dari THREAT_MODEL.md).
Backend sandbox pihak ketiga (mis. `LangSmithSandbox`, atau backend custom
lain yang mengimplementasikan `SandboxBackendProtocol`) tidak otomatis aman —
"sandbox" di sini adalah kontrak interface, bukan jaminan isolasi OS-level;
tanggung jawab isolasi ada di implementasi backend. `[code]` —
`deepagents/backends/local_shell.py`, `deepagents/backends/langsmith.py`.

## 7. Capability routing & policy

Dua mekanisme deklaratif berdampingan, **bukan** classifier, dan keduanya
bukan "prosa sebagai aturan":

- **`HarnessProfile` / `ProviderProfile`** (`deepagents.profiles`, ditandai
  beta) — dataclass yang dipilih otomatis berdasar **model/provider** saat
  konstruksi (`_harness_profile_for_model`), bukan berdasar intent tugas.
  Mengatur `materialize_extra_middleware()`, `excluded_middleware`,
  `excluded_tools`, `tool_description_overrides`, `base_system_prompt` +
  `system_prompt_suffix`, dan `general_purpose_subagent`. Caller bisa
  mendaftar profil sendiri lewat `register_harness_profile`/
  `register_provider_profile`. Middleware inti (`FilesystemMiddleware`,
  `SubAgentMiddleware`) tidak bisa dikeluarkan lewat mekanisme ini —
  `excluded_middleware` yang menyentuh keduanya memicu `ValueError` saat
  konstruksi. `[code]` — `deepagents/profiles/harness/harness_profiles.py`,
  `deepagents/graph.py` baris 238-266, 605-611.
- **`SkillsMiddleware`** (`skills=["/skills/user/", ...]`) — mengimplementasi
  pola Agent Skills Anthropic dengan *progressive disclosure*: metadata
  (`name`/`description` dari frontmatter YAML `SKILL.md`) dimuat ke system
  prompt di awal, isi lengkap skill baru dimuat saat model memilihnya. Ini
  **prosa + judgment model** murni — tidak ada classifier kode yang
  menentukan skill mana dipanggil, keputusan sepenuhnya di tangan model
  berdasar deskripsi yang terlihat. Sumber dimuat berurutan, sumber
  belakangan menang untuk skill bernama sama (layering
  base→user→project→team). `[code]` — `deepagents/middleware/skills.py`.

Tidak ada classifier intent bawaan di `deepagents` untuk memilih skill/mode:
routing skill = judgment model atas metadata; routing profil = deterministik
berdasar spec model/provider, diputuskan sekali per konstruksi agent, bukan
per giliran. `[inferred]` — disimpulkan dari tidak ditemukannya modul
classifier di source yang dibaca (lihat daftar file lengkap di `## Sumber`).

## API permukaan

| Entrypoint | Tipe | Fungsi |
|---|---|---|
| `create_deep_agent(model, tools=None, *, system_prompt=None, middleware=(), subagents=None, skills=None, memory=None, permissions=None, backend=None, interrupt_on=None, response_format=None, state_schema=None, context_schema=None, checkpointer=None, store=None, debug=False, name=None, cache=None)` | fungsi | Entrypoint utama; merakit middleware lalu mendelegasikan ke `langchain.agents.create_agent` |
| `DeepAgentState` | `TypedDict` (`AgentState`) | State graph dasar; `messages` pakai `DeltaChannel` reducer |
| `SubAgent` | `TypedDict` | Spec subagent deklaratif sinkron |
| `CompiledSubAgent` | `TypedDict` | Wrapper subagent yang sudah dikompilasi (`runnable`) |
| `AsyncSubAgent` | `TypedDict` | Spec subagent remote/background (Agent Protocol) |
| `FilesystemMiddleware`, `FilesystemPermission`, `FsToolName` | kelas/tipe | Tool filesystem + `execute` + aturan izin |
| `SubAgentMiddleware`, `AsyncSubAgentMiddleware` | kelas | Tool `task` (sinkron) dan tool background (async) |
| `MemoryMiddleware` | kelas | Muat `AGENTS.md` ke system prompt |
| `RubricMiddleware` | kelas | Iterasi self-eval terhadap rubric (opsional, tidak default) |
| `HarnessProfile`, `HarnessProfileConfig`, `register_harness_profile` | kelas/fungsi | Profil perilaku per model/provider |
| `ProviderProfile`, `register_provider_profile` | kelas/fungsi | Hook inisialisasi model per provider |
| `GeneralPurposeSubagentProfile` | kelas | Kontrol on/off subagent `general-purpose` default |

`[code]` — `deepagents/__init__.py` (daftar `__all__` lengkap), `deepagents/graph.py`.

## Middleware bawaan

| Middleware | Titik penegakan | Kapan dipakai |
|---|---|---|
| `FilesystemMiddleware` | Selalu, main + tiap subagent | Wajib — sumber tool `ls/read_file/write_file/edit_file/glob/grep(/execute)`, penegak `permissions`, eviction tool result besar |
| `SubAgentMiddleware` | Main agent (jika ada subagent inline) | Wajib jika ada `SubAgent`/`CompiledSubAgent` — sumber tool `task` |
| `create_summarization_middleware` (→ `SummarizationMiddleware`) | Selalu, main + tiap subagent | Kompaksi otomatis saat token lampaui threshold berbasis profil model |
| `PatchToolCallsMiddleware` | Selalu, main + tiap subagent | Tambal `ToolMessage` dangling di riwayat pesan |
| `AsyncSubAgentMiddleware` | Main agent, hanya jika ada `AsyncSubAgent` | Tool background start/check/update/cancel/list |
| `SkillsMiddleware` | Main + subagent yang deklarasikan `skills=` | Muat progressive-disclosure skill ke system prompt |
| `MemoryMiddleware` | Main agent, hanya jika `memory=[...]` diisi | Suntik isi `AGENTS.md` ke system prompt |
| `AnthropicPromptCachingMiddleware` (+Bedrock/Fireworks kondisional) | Selalu, tail stack | Cache prompt provider-spesifik, no-op di provider lain |
| `HumanInTheLoopMiddleware` (langchain) | Main/subagent, hanya jika `interrupt_on` gabungan tidak kosong | Jeda approval manusia sebelum tool tereksekusi |
| `_ToolExclusionMiddleware` (privat) | Tail stack, hanya jika profil punya `excluded_tools` | Menyaring nama tool hasil middleware manapun sebelum dikirim ke model |
| `RubricMiddleware` | Tidak di stack default — pasang manual via `middleware=[...]` | Iterasi ulang jawaban terhadap rubric sampai lolos atau `max_iterations` |
| `TodoListMiddleware` (langchain, **bukan** milik `deepagents`) | Tidak di stack default — pasang manual | Planning eksplisit (tool `write_todos`) untuk task multi-langkah |

`[code]` — `deepagents/graph.py` baris 361-402 (urutan resmi base+tail stack
di docstring parameter `middleware`), tiap file middleware terkait.

## Backend filesystem

| Backend | Sifat | Implikasi multi-user |
|---|---|---|
| `StateBackend` (default) | Ephemeral, tersimpan di state LangGraph, checkpoint otomatis per step | Isolasi = isolasi thread di level checkpointer; tidak ada scope per-user bawaan |
| `FilesystemBackend(root_dir, virtual_mode=True, max_file_size_mb=10)` | Baca/tulis langsung ke disk lokal; `virtual_mode` mengurung operasi file ke `root_dir` | Berbagi filesystem host — isolasi antar user adalah tanggung jawab pemanggil (proses/container terpisah per user), bukan backend |
| `LocalShellBackend` (extends `FilesystemBackend` + `SandboxBackendProtocol`) | Sama seperti `FilesystemBackend` + `execute` lewat `subprocess.run(shell=True)` tanpa validasi command; `virtual_mode` **tidak** membatasi `execute()` | Eksekusi shell tak terisolasi di host — dilabeli eksplisit "not the default" di `THREAT_MODEL.md`; tidak layak multi-user tanpa sandbox tambahan |
| `StoreBackend(namespace: NamespaceFactory, store=None)` | Persisten lintas-thread lewat `BaseStore` LangGraph | `namespace` adalah *hook* scoping resmi — mis. `lambda rt: (rt.server_info.user.identity,)` untuk isolasi per-user `[docs]` |
| `CompositeBackend(default, routes={prefix: backend}, artifacts_root="/")` | Merutekan path ke backend berbeda per prefix (mis. `/memories/` → `StoreBackend`, sisanya → `StateBackend`) | Pola hybrid: gabung ephemeral cepat + durable ter-scope, cocok untuk memisahkan area publik/per-user dalam satu agent |
| `ContextHubBackend(identifier, client=None)` | Persisten di LangSmith Hub agent repo, mutasi diserialkan lewat `_MutationQueue` bertimer/lock | Satu `identifier` = satu repo bersama; scoping per-user harus lewat `identifier`/prefix path sendiri |
| `LangSmithSandbox(sandbox)` | Implementasi `SandboxBackendProtocol` via sandbox terkelola LangSmith | Isolasi eksekusi mengikuti jaminan sandbox LangSmith, bukan proses host |

Hanya `StoreBackend`, `CompositeBackend` (yang merutekan ke `StoreBackend`),
dan `ContextHubBackend` yang punya *hook* scoping eksplisit (`namespace`/
`identifier`). `StateBackend`, `FilesystemBackend`, dan `LocalShellBackend`
tidak — isolasi multi-user untuk ketiganya harus dibangun di luar backend
(proses/container terpisah per user). `[code]` + `[docs]` (kutipan
`THREAT_MODEL.md` dan contoh `namespace=lambda rt: ...` dari
`docs.langchain.com/oss/python/deepagents/backends`, dikutip via Context7).

## Sumber

**Versi yang dibaca**: `deepagents==0.7.8` (dikonfirmasi lewat
`deepagents.__version__` setelah `uv sync`, dan nama direktori
`deepagents-0.7.8.dist-info`), diinstal bersama `langchain==1.3.16`,
`langchain-anthropic==1.6.1`, `langgraph==1.2.11`, `langgraph-checkpoint==4.2.0`,
`langgraph-prebuilt==1.1.0` — semua dari PyPI, 2026-08-23, lewat
`references/recipes/pyproject.toml`.

File `[code]` yang dibaca langsung dari
`references/recipes/.venv/lib/python3.13/site-packages/`:

- `deepagents/__init__.py`, `deepagents/_version.py`, `deepagents/graph.py` (utuh)
- `deepagents/_models.py`, `deepagents/_excluded_middleware.py` (sebagian, untuk perilaku `_harness_profile_for_model` dan validasi `excluded_middleware`)
- `deepagents/backends/__init__.py`, `protocol.py`, `state.py` (utuh), `filesystem.py`, `store.py`, `local_shell.py`, `composite.py`, `context_hub.py`, `langsmith.py` (docstring modul + kelas + signature `__init__`/`execute`)
- `deepagents/middleware/__init__.py`, `permissions.py` (utuh), `_fs_interrupt.py` (sebagian), `_tool_exclusion.py` (utuh), `_prompt_caching.py` (utuh), `_message_eviction.py`, `_overflow_clip.py` (sebagian, header modul + helper kunci), `filesystem.py` (kelas `FilesystemPermission`, `FilesystemMiddleware`, konstanta `FsToolName`), `subagents.py`, `async_subagents.py`, `summarization.py`, `memory.py`, `skills.py`, `patch_tool_calls.py`, `rubric.py` (docstring modul + kelas + signature `__init__`)
- `deepagents/profiles/harness/harness_profiles.py` (sebagian, header modul + validasi scaffolding)
- `langchain/agents/factory.py` (signature + docstring `create_agent`)
- `langchain/agents/middleware/human_in_the_loop.py`, `langchain/agents/middleware/todo.py` (header + tipe kunci)

Sumber `[docs]` (dikutip via Context7 MCP, library id `/langchain-ai/deepagents`
dan `/websites/langchain_oss_python_deepagents`):

- `openwiki/architecture/overview.md` (langchain-ai/deepagents) — diagram
  layering Deep Agents/LangChain/LangGraph
- `libs/deepagents/deepagents/graph.py` (potongan yang sama seperti di atas,
  dikonfirmasi identik lewat Context7 dan pembacaan source langsung)
- `docs.langchain.com/oss/python/deepagents/human-in-the-loop` — contoh
  override `interrupt_on` per subagent
- `docs.langchain.com/oss/python/deepagents/permissions` — contoh
  penggantian total `permissions` di subagent
- `docs.langchain.com/oss/python/deepagents/backends` — contoh
  `CompositeBackend` + `StoreBackend(namespace=lambda rt: ...)`
- `libs/deepagents/THREAT_MODEL.md` (langchain-ai/deepagents) — dikutip
  lewat WebFetch langsung ke
  `raw.githubusercontent.com/langchain-ai/deepagents/main/libs/deepagents/THREAT_MODEL.md`,
  untuk klaim `LocalShellBackend` non-default, `execute()` tak terbatas
  `virtual_mode`, dan HITL sebagai mitigasi opt-in bukan default
- Struktur direktori `libs/` repo `langchain-ai/deepagents` (berisi `acp`,
  `cli`, `code`, `deepagents`, `evals`, `partners` (termasuk `daytona`),
  `talon`) — dikutip via WebFetch ke
  `github.com/langchain-ai/deepagents/tree/main/libs`, untuk mengonfirmasi
  paket `libs/cli` dan `libs/partners/daytona` yang dirujuk archetype 01/02/07
  benar ada, meski API persisnya (`agent.json`, `DaytonaSandbox(...)`) **tidak**
  diverifikasi di task ini karena keduanya paket terpisah dari `deepagents`
  core yang diinstal (lihat `## Bangun ini pakai deepagents` di file
  archetype terkait untuk detail yang belum diverifikasi ulang).

Catatan kejujuran: paket `deepagents-cli`/`langchain_daytona` **tidak**
terinstal di lingkungan ini (dicek lewat `uv run pip list`), sehingga klaim
API persis milik dua paket itu di file archetype tetap berlabel seperti yang
sudah mereka pakai (`[code]` mengutip repo, bukan `[code]` dari instalasi
lokal) — bukan diverifikasi ulang oleh file ini.
