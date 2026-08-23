# `deepagents` — lifecycle satu turn

Apa yang terjadi dari `agent.invoke({"messages": [...]})` sampai state akhir,
tahap demi tahap, dan di mana tiap tahap bisa diintervensi secara resmi.

`create_deep_agent` tidak membangun graph-nya sendiri: ia merakit stack
middleware lalu memanggil `langchain.agents.create_agent(...)`. Jadi
lifecycle-nya adalah lifecycle `create_agent`, dengan node middleware yang
dirakit `deepagents`. `[code]` — `deepagents/graph.py` baris 922-944;
`langchain/agents/factory.py` baris 1543-1830 (perakitan node dan edge).

## Diagram alur

```
                     invoke(state, config)
                              │
                              ▼
                        ┌───────────┐
                        │   START   │
                        └─────┬─────┘
                              │
      ┌───────────────────────▼────────────────────────┐
      │  before_agent  (node, sekali per RUN)          │   urutan = urutan list
      │  m[0].before_agent → m[1].before_agent → …     │   (PatchToolCalls, Skills,
      └───────────────────────┬────────────────────────┘    Memory, Rubric)
                              │
   ╔══════════════════════════▼═══════════════════════════════════════════╗
   ║  LOOP  (berulang sampai model berhenti memanggil tool)               ║
   ║                                                                      ║
   ║   ┌──────────────────────────────────────────────┐                   ║
   ║   │  before_model (node, tiap iterasi)           │  urutan list      ║
   ║   │  m[0] → m[1] → …                             │  (ModelCallLimit) ║
   ║   └──────────────────┬───────────────────────────┘                   ║
   ║                      │                                               ║
   ║   ┌──────────────────▼───────────────────────────┐                   ║
   ║   │  node "model"                                │                   ║
   ║   │                                              │                   ║
   ║   │  ModelRequest dirakit:                       │                   ║
   ║   │    model, tools=default_tools,               │                   ║
   ║   │    system_message, response_format,          │                   ║
   ║   │    messages=state["messages"], state, runtime│                   ║
   ║   │                     │                        │                   ║
   ║   │   wrap_model_call ONION (m[0] = TERLUAR):    │                   ║
   ║   │     m0( … m1( … mN( _execute_model )))       │                   ║
   ║   │        Skills/FS/Memory tambah system prompt │                   ║
   ║   │        FS saring tool tak didukung backend   │                   ║
   ║   │        Summarization kompaksi bila perlu     │                   ║
   ║   │        _ToolExclusion (terdalam) buang tool  │                   ║
   ║   │                     │                        │                   ║
   ║   │   messages = [system_message, *messages]     │                   ║
   ║   │   model_.invoke(messages)  ◄── panggilan LLM │                   ║
   ║   │                     │                        │                   ║
   ║   │   _handle_model_output → ModelResponse       │                   ║
   ║   └──────────────────┬───────────────────────────┘                   ║
   ║                      │                                               ║
   ║   ┌──────────────────▼───────────────────────────┐                   ║
   ║   │  after_model (node)  URUTAN TERBALIK         │  m[n] → … → m[0]  ║
   ║   │  HumanInTheLoopMiddleware ada DI SINI        │  ← interrupt()    ║
   ║   └──────────────────┬───────────────────────────┘                   ║
   ║                      │                                               ║
   ║          ┌───────────▼────────────┐                                  ║
   ║          │ ada tool_calls?        │                                  ║
   ║          └──┬──────────────────┬──┘                                  ║
   ║        ya   │                  │ tidak → keluar loop                 ║
   ║   ┌─────────▼──────────────────────────────────┐                     ║
   ║   │  node "tools"                              │                     ║
   ║   │   wrap_tool_call ONION (m[0] = TERLUAR)    │                     ║
   ║   │     FS: evict hasil besar ke backend       │                     ║
   ║   │     ToolRetry/ToolError bila dipasang      │                     ║
   ║   │   → ToolMessage / Command masuk state      │                     ║
   ║   └─────────┬──────────────────────────────────┘                     ║
   ║             └──────────► kembali ke before_model/model               ║
   ╚══════════════════════════╤═══════════════════════════════════════════╝
                              │
      ┌───────────────────────▼────────────────────────┐
      │  after_agent (node, sekali per RUN)            │  URUTAN TERBALIK
      │  m[n].after_agent → … → m[0].after_agent       │  (RubricMiddleware)
      └───────────────────────┬────────────────────────┘
                              │
                        ┌─────▼─────┐
                        │    END    │
                        └───────────┘
```

`[code]` — `langchain/agents/factory.py`: `model_node` baris 1468-1489,
`_execute_model_sync` baris 1441-1466, komposisi onion
`_chain_model_call_handlers` baris 263-352 (komentar eksplisit
"first in list becomes outermost layer"), wiring edge baris 1675-1830.
Urutan terbalik `after_model` terbaca dari
`graph.add_edge("model", f"{middleware_w_after_model[-1].name}.after_model")`
baris 1793 yang berantai turun ke index 0; `after_agent` sama, baris
1817-1830.

## Tahap demi tahap

### 1. `before_agent` — sekali per run

Node graph. Dijalankan berurutan sesuai urutan list middleware.
Di stack default hanya `PatchToolCallsMiddleware` yang memakainya — ia
menambal `ToolMessage` sintetis untuk tool call yang dangling/rusak di
riwayat, lalu **menulis ulang seluruh `messages`** dengan
`RemoveMessage(id=REMOVE_ALL_MESSAGES)` diikuti daftar hasil tambalannya.
Ini yang membuat resume setelah crash/cancel tidak ditolak provider.
`SkillsMiddleware`, `MemoryMiddleware`, dan `RubricMiddleware` juga memakai
hook ini (memuat index skill / isi `AGENTS.md` / rubric ke state).
`[code]` — `deepagents/middleware/patch_tool_calls.py` baris 14-45;
`skills.py` baris 928; `memory.py` baris 274; `rubric.py` baris 522.

**Titik intervensi**: `before_agent` middleware sendiri, atau decorator
`@before_agent` dari `langchain.agents.middleware`. Bisa `jump_to` END.

### 2. `before_model` — tiap iterasi loop

Node graph, urutan list. Tidak ada middleware `deepagents` yang memakainya.
Yang memakainya di `langchain`: `ModelCallLimitMiddleware` (dengan
`@hook_config(can_jump_to=["end"])` sehingga bisa memutus loop).

**Titik intervensi**: hook `before_model`, atau `@before_model`.

### 3. Perakitan prompt & pemilihan tool — di dalam node `model`

`ModelRequest` dibuat sekali dengan `system_message` hasil rakitan statis
(`USER` → `BASE` → `SUFFIX`) dan `tools=default_tools` (semua tool: caller +
middleware). Semua penyesuaian dinamis terjadi di rantai `wrap_model_call`:

- `SkillsMiddleware`, `MemoryMiddleware`, `FilesystemMiddleware` menambahkan
  fragmen ke system message lewat `request.override(system_message=...)`.
- `FilesystemMiddleware` menyaring tool yang tidak didukung backend
  (`execute` hilang kalau backend bukan `SandboxBackendProtocol`), melakukan
  scrubbing blok multimodal yang tak didukung, dan meng-evict `HumanMessage`
  raksasa ke backend.
- `SummarizationMiddleware` menghitung token dan, bila melewati threshold,
  mengganti riwayat dengan summary **hanya untuk request ini** —
  `state["messages"]` tidak dimutasi (dilacak di field privat
  `_summarization_event`).
- `_ToolExclusionMiddleware` berada paling akhir di list = **terdalam** =
  kata terakhir soal isi `request.tools`.

Baru setelah itu `messages = [request.system_message, *request.messages]` dan
`model_.invoke(messages)` dipanggil.

**Titik intervensi**: `wrap_model_call` / `awrap_model_call`, atau
`@wrap_model_call` / `@dynamic_prompt`. Handler boleh dipanggil berkali-kali
(retry), boleh tidak dipanggil sama sekali (short-circuit).
⚠️ `Command` dengan `goto`/`resume`/`graph` **tidak didukung** di
`wrap_model_call` — `factory.py` baris 247-255 raise eksplisit.

### 4. `after_model` — urutan terbalik

Node graph. Middleware **terakhir** di list dijalankan **pertama**.
`HumanInTheLoopMiddleware` hidup di sini: ia membaca `tool_calls` pada
`AIMessage` terakhir dan memanggil `interrupt()` sebelum node `tools`
sempat berjalan. Karena `HumanInTheLoopMiddleware` selalu ditaruh di ujung
stack oleh `create_deep_agent`, ia menjadi `after_model` yang **pertama**
dieksekusi — approval terjadi sebelum middleware `after_model` lain sempat
melihat hasil model.

**Titik intervensi**: `after_model` / `@after_model`, `interrupt_on`,
`permissions(mode="interrupt")`.

### 5. Eksekusi tool

Node `tools`. Rantai `wrap_tool_call` juga onion (pertama = terluar).
`FilesystemMiddleware.wrap_tool_call` memanggil handler lebih dulu lalu
memeriksa ukuran hasil; hasil di atas `tool_token_limit_before_evict`
ditulis ke backend dan diganti preview + referensi file.
⚠️ Exception dari tool (termasuk `ToolException`) **sengaja diloloskan**
oleh `FilesystemMiddleware` — kalau butuh ditangkap, pasang
`ToolErrorMiddleware`/`ToolRetryMiddleware`.
`[code]` — `deepagents/middleware/filesystem.py` baris 3471-3520.

**Titik intervensi**: `wrap_tool_call` / `awrap_tool_call`, atau
`@wrap_tool_call`.

### 6. Penulisan state

State ditulis lewat return value node — `dict` update atau `Command(update=...)`
— dan di-reduce oleh channel LangGraph. Untuk `messages`, `DeepAgentState`
memakai `DeltaChannel(_messages_delta_reducer, snapshot_frequency=50)`
sehingga checkpoint tumbuh O(N), bukan O(N²).
Middleware yang perlu menulis state dari dalam `wrap_model_call` memakai
`ExtendedModelResponse(model_response=..., command=...)` — bukan mutasi
langsung.

**Titik intervensi**: `state_schema` middleware (cara yang disarankan),
`create_deep_agent(state_schema=...)` (cara global), `PrivateStateAttr`
untuk field yang tidak boleh menyeberang ke/dari subagent.

### 7. Kondisi berhenti

Loop berhenti ketika `AIMessage` terakhir tidak punya `tool_calls`
(`_make_model_to_tools_edge` mengarahkan ke `exit_node`). Selain itu:

- `recursion_limit` LangGraph — default `9_999` dari
  `.with_config(...)` di `create_deep_agent`; **override lewat**
  `.with_config({"recursion_limit": N})` atau
  `invoke(..., config={"recursion_limit": N})`.
- `ModelCallLimitMiddleware` / `ToolCallLimitMiddleware` — `jump_to end`
  atau raise, tergantung `exit_behavior`.
- Tool dengan `return_direct=True` — langsung ke `exit_node`.
- `interrupt()` dari HITL — run berhenti dan menunggu `Command(resume=...)`.

### 8. `after_agent` — urutan terbalik, sekali per run

`RubricMiddleware` memakainya untuk menilai transkrip terhadap rubric dan,
bila gagal, memaksa iterasi ulang.

## Subagent: lifecycle bersarang

Tool `task` menjalankan graph subagent **penuh** (lifecycle 1-8 di atas)
di dalam satu tool call agent induk. State yang dikirim ke subagent adalah
state induk minus `_EXCLUDED_STATE_KEYS` (`messages`, `todos`,
`structured_response`) dan minus field `PrivateStateAttr`, dengan
`messages` diganti satu `HumanMessage` berisi `description`.

Yang kembali: satu `ToolMessage` berisi `structured_response` ter-JSON
(kalau ada) atau teks `AIMessage` non-kosong terakhir, **plus** merge key
state non-excluded lainnya ke state induk.
`[code]` — `deepagents/middleware/subagents.py` baris 251-268, 474-512,
529-540.

## Sumber

**Versi yang dibaca**: `deepagents==0.7.8`, `langchain==1.3.16`, dari
`references/recipes/.venv/lib/python3.13/site-packages/`.

File `[code]`:

- `langchain/agents/factory.py` — `create_agent`, `model_node`,
  `_execute_model_sync`, `_chain_model_call_handlers`,
  `_chain_tool_call_wrappers`, `_add_middleware_edge`, wiring START/END
- `langchain/agents/middleware/types.py` — kontrak `AgentMiddleware`
- `deepagents/graph.py` — perakitan stack dan `.with_config`
- `deepagents/middleware/patch_tool_calls.py`, `filesystem.py`,
  `summarization.py`, `subagents.py`, `skills.py`, `memory.py`, `rubric.py`,
  `_tool_exclusion.py`

Verifikasi runtime `[code]`: node graph agent minimal
(`create_deep_agent(model=..., tools=[])`) adalah
`['PatchToolCallsMiddleware.before_agent', '__end__', '__start__', 'model',
'tools']`; dengan `permissions` bermode `interrupt` bertambah
`'HumanInTheLoopMiddleware.after_model'`. Middleware lain tidak menambah
node karena hanya memakai `wrap_model_call`/`wrap_tool_call`.

Stack penuh (`memory=`, `skills=`, `interrupt_on=`,
`middleware=[TodoListMiddleware(), ModelCallLimitMiddleware(thread_limit=5)]`)
menghasilkan node:

```
HumanInTheLoopMiddleware.after_model
MemoryMiddleware.before_agent
ModelCallLimitMiddleware.after_model
ModelCallLimitMiddleware.before_model
PatchToolCallsMiddleware.before_agent
SkillsMiddleware.before_agent
TodoListMiddleware.after_model
__end__  __start__  model  tools
```

Urutan eksekusi `before_agent`-nya mengikuti urutan list stack:
`SkillsMiddleware` → `PatchToolCallsMiddleware` → `MemoryMiddleware`.
Urutan `after_model`-nya terbalik: `HumanInTheLoopMiddleware` →
`ModelCallLimitMiddleware` → `TodoListMiddleware`.
