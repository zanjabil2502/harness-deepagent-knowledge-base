# `deepagents` — handler & hook

Daftar titik intercept yang tersedia, apa yang bisa diubah di masing-masing,
apa yang **tidak** bisa, dan pola penanganan error yang resmi.

Semua hook di sini berasal dari `langchain.agents.middleware.AgentMiddleware`;
`deepagents` tidak menambah jenis hook baru — ia hanya merakit middleware yang
memakainya. `[code]` — `langchain/agents/middleware/types.py` baris 385-740.

## Tabel hook

| Hook | Kapan | Menerima | Boleh mengubah | **Tidak** bisa |
|---|---|---|---|---|
| `before_agent` / `abefore_agent` | sekali per run, sebelum loop | `state`, `runtime` | state update (`dict`), termasuk menulis ulang `messages` | tidak melihat `ModelRequest`; tidak bisa mengubah daftar tool |
| `before_model` / `abefore_model` | tiap iterasi, sebelum node `model` | `state`, `runtime` | state update; `jump_to` bila di-`@hook_config(can_jump_to=[...])` | tidak melihat/mengubah `request.tools` maupun system message |
| `wrap_model_call` / `awrap_model_call` | membungkus panggilan LLM | `ModelRequest`, `handler` | `model`, `tools`, `system_message`, `messages`, `response_format`, `tool_choice` lewat `request.override(...)`; boleh memanggil `handler` 0..N kali; boleh mengembalikan `AIMessage` langsung | ⚠️ `Command` dengan `goto`, `resume`, atau `graph` **ditolak** (`factory.py` baris 245-256). State update hanya lewat `ExtendedModelResponse(command=...)` |
| `after_model` / `aafter_model` | tiap iterasi, setelah node `model`, **urutan terbalik** | `state`, `runtime` | state update; `jump_to`; `interrupt()` | tidak bisa membatalkan panggilan LLM yang sudah terjadi (biayanya sudah keluar) |
| `wrap_tool_call` / `awrap_tool_call` | membungkus tiap eksekusi tool | `ToolCallRequest`, `handler` | argumen tool sebelum eksekusi; hasil setelah eksekusi; boleh tidak memanggil `handler` (short-circuit); boleh mengembalikan `ToolMessage` atau `Command` | tidak melihat tool call lain di `AIMessage` yang sama |
| `after_agent` / `aafter_agent` | sekali per run, sebelum END, **urutan terbalik** | `state`, `runtime` | state update; `jump_to` kembali ke model | tidak bisa mengubah struktur graph |

Versi async: kalau sebuah middleware hanya mengimplementasi versi sync dan
graph dijalankan lewat `ainvoke`, `create_agent` tetap memasangnya lewat
`RunnableCallable`, tapi untuk `wrap_*` `NotImplementedError` bisa muncul —
`factory.py` sengaja mengumpulkan middleware yang punya **salah satu** dari
sync/async supaya kegagalan jalur yang salah terlihat, bukan diam.
`[code]` — `langchain/agents/factory.py` baris 1040-1060.

## Human-in-the-loop

Dua jalur, keduanya berujung ke `HumanInTheLoopMiddleware`:

1. `create_deep_agent(interrupt_on={...})` — eksplisit per nama tool.
2. `create_deep_agent(permissions=[FilesystemPermission(..., mode="interrupt")])`
   — `_build_interrupt_on_from_permissions` mensintesis entri `interrupt_on`
   dengan predikat `when` yang mengevaluasi path per panggilan.

Keduanya digabung `_merge_fs_interrupt_on`; entri user menang per nama tool.
Kalau gabungannya kosong, middleware-nya **tidak dipasang sama sekali**.
`[code]` — `deepagents/graph.py` baris 231-247, 920-925;
`deepagents/middleware/_fs_interrupt.py`.

### Bentuk `InterruptOnConfig`

`[code]` — `langchain/agents/middleware/human_in_the_loop.py` baris 51,
146-215.

| Field | Tipe | Catatan |
|---|---|---|
| `allowed_decisions` | `list[Literal["approve","edit","reject","respond"]]` | Wajib. `respond` = manusia menjawab **menggantikan** tool; tool tidak dieksekusi, `ToolMessage` sintetis berstatus `success` dikirim ke model. |
| `description` | `str` atau callable `(tool_call, state, runtime) -> str` | Teks yang dilihat approver. |
| `args_schema` | `dict` | JSON schema untuk keputusan `edit`. |
| `when` | `(ToolCallRequest) -> bool` | Predikat auto-approve. Inilah satu-satunya cara resmi menyaring "interrupt hanya kalau kondisi X". |

`interrupt_on={"execute": True}` adalah gula untuk
`allowed_decisions=["approve","edit","reject"]`.

### Resume

Interrupt LangGraph berarti run **berhenti** dan checkpointer menyimpan
posisinya. Melanjutkan = `invoke(Command(resume=HITLResponse(...)), config)`
dengan `thread_id` yang sama. Tanpa `checkpointer`, `interrupt_on` tidak
berguna — tidak ada tempat menyimpan titik jeda.

⚠️ Pewarisan: `SubAgent` deklaratif mewarisi `interrupt_on` top-level;
`CompiledSubAgent` dan `AsyncSubAgent` **tidak**. Subagent yang menyediakan
`interrupt_on` sendiri **mengganti** warisan, tidak menambah.

## Pola penanganan error

### Tool gagal (exception)

`FilesystemMiddleware.wrap_tool_call` **sengaja meloloskan** exception tool,
termasuk `ToolException` (docstring: "propagate through this wrapper
unhandled by design"). Yang resmi menangani:

| Kebutuhan | Middleware | Konfigurasi kunci |
|---|---|---|
| Ubah exception jadi `ToolMessage` error | `ToolErrorMiddleware` | `on_error=<callable>`, `aon_error=`, `tools=` (subset). Handler yang mengembalikan `None` **melepas exception kembali** |
| Retry dengan backoff | `ToolRetryMiddleware` | `max_retries=2`, `retry_on=`, `on_failure="continue"\|"error"\|callable`, `backoff_factor=2.0`, `initial_delay=1.0`, `max_delay=60.0`, `jitter=True` |
| Tolak sebelum eksekusi | `wrap_tool_call` sendiri, kembalikan `ToolMessage(status="error")` | pola `ShellAllowListMiddleware` maintainer |

`[code]` — `langchain/agents/middleware/tool_error.py` baris 75-105,
`tool_retry.py` baris 133-175.

### Model gagal / timeout

| Kebutuhan | Middleware | Konfigurasi kunci |
|---|---|---|
| Retry panggilan model | `ModelRetryMiddleware` | `max_retries=2`, `retry_on=`, `on_failure="continue"\|"error"\|callable`, backoff sama seperti tool |
| Pindah ke model cadangan | `ModelFallbackMiddleware` | `ModelFallbackMiddleware(first_model, *additional_models)` — dicoba berurutan |
| Konteks kelebihan | sudah tertangani `SummarizationMiddleware` `deepagents`: `ContextOverflowError` ditangkap, riwayat dikompaksi, request diulang | `create_summarization_middleware(...)` |

Timeout murni jaringan bukan urusan middleware — atur di konstruktor model
(`ChatAnthropic(default_request_timeout=..., max_retries=...)` — alias `timeout` juga diterima).

### Budget habis

| Batas | Mekanisme | Perilaku saat terlampaui |
|---|---|---|
| Langkah graph | `recursion_limit` LangGraph, default `9_999` dari `create_deep_agent` | `GraphRecursionError` |
| Panggilan model | `ModelCallLimitMiddleware(thread_limit=, run_limit=, exit_behavior="end"\|"error")` | `"end"` = lompat ke END + `AIMessage` penjelasan; `"error"` = `ModelCallLimitExceededError` |
| Panggilan tool | `ToolCallLimitMiddleware(tool_name=, thread_limit=, run_limit=, exit_behavior="continue"\|"error"\|"end")` | `"continue"` = tool yang lewat batas diblokir dengan pesan error, tool lain jalan; `"end"` = hentikan sekarang |

`recursion_limit` di-override lewat
`agent.with_config({"recursion_limit": N})` atau
`agent.invoke(..., config={"recursion_limit": N})` — ini yang dipakai
maintainer di `examples/better-harness/better_harness/agent.py` dan di
`libs/code/deepagents_code/agent.py` (`.with_config({**config,
"recursion_limit": effective_recursion_limit})`). `[code]` — repo
`langchain-ai/deepagents` commit `23b83ad`.

⚠️ Default `9_999` bukan pengaman; ia praktis berarti "tak terbatas".
Setiap deployment harus menurunkannya secara eksplisit.

`ToolCallLimitMiddleware` menghitung **jumlah** panggilan, bukan
pengulangan identik. Deteksi "berputar di tempat" tidak ada bawaan — lihat
contoh di [`middleware.md`](middleware.md).

### Interupsi manusia (cancel/kill)

Tidak ada API "hentikan semua run" di `deepagents`. Yang ada:

- `interrupt()` (HITL) — jeda kooperatif, menunggu `Command(resume=...)`.
- Membatalkan task asyncio / menutup proses — meninggalkan tool call
  dangling di checkpoint. `PatchToolCallsMiddleware.before_agent` yang
  merapikannya pada run berikutnya, dengan `ToolMessage` sintetis berisi
  "was cancelled - another message came in before it could be completed".
  Ini satu-satunya jaring pengaman resmi untuk pembatalan mendadak.
- Kill switch tingkat armada = tanggung jawab orchestrator/queue di atas
  `deepagents`.

`[code]` — `deepagents/middleware/patch_tool_calls.py` baris 30-45.

### Subagent gagal

Kalau `subagent_type` tidak dikenal, tool `task` mengembalikan **string**
error biasa ("we cannot invoke subagent X ... the only allowed types are
..."), bukan exception — model bisa mencoba nama lain.
Kalau `CompiledSubAgent` mengembalikan state tanpa key `messages`,
`_return_command_with_state_update` **raise `ValueError`** dan run gagal.
`[code]` — `deepagents/middleware/subagents.py` baris 474-482, 549 (jalur sync) dan 577 (jalur async).

## Yang tidak bisa di-intercept

- **Isi request HTTP ke provider** — itu urusan objek `BaseChatModel`.
- **Urutan pemanggilan tool.** Tidak ada hook "tool B wajib setelah tool A".
  `PatchToolCallsMiddleware` sering disalahpahami sebagai penegak urutan;
  ia hanya menambal `ToolMessage` yang hilang. Penegakan urutan hanya bisa
  lewat instruksi prompt, atau `wrap_tool_call` yang menolak panggilan yang
  melanggar urutan — keduanya bukan jaminan struktural.
- **Menghapus `FilesystemMiddleware`/`SubAgentMiddleware`** —
  `HarnessProfile.excluded_middleware` menolaknya dengan `ValueError`.
- **Membuat `after_model` berjalan setelah HITL** — HITL selalu paling awal
  di fase itu (lihat [`middleware.md`](middleware.md) §5).

## Sumber

**Versi yang dibaca**: `deepagents==0.7.8`, `langchain==1.3.16`.

`[code]` dari `references/recipes/.venv/lib/python3.13/site-packages/`:

- `langchain/agents/middleware/types.py` (kontrak `AgentMiddleware`, decorator)
- `langchain/agents/middleware/human_in_the_loop.py` (`DecisionType`,
  `InterruptOnConfig`, `HITLRequest`/`HITLResponse`)
- `langchain/agents/middleware/tool_error.py`, `tool_retry.py`,
  `model_retry.py`, `model_fallback.py`, `model_call_limit.py`,
  `tool_call_limit.py` (signature `__init__` + docstring)
- `langchain/agents/factory.py` (penolakan `Command` di `wrap_model_call`,
  pengumpulan middleware per hook)
- `deepagents/graph.py`, `deepagents/middleware/_fs_interrupt.py`,
  `patch_tool_calls.py`, `filesystem.py`, `subagents.py`,
  `summarization.py`

`[code]` dari `git clone --depth 1 langchain-ai/deepagents` (commit
`23b83ad`, 2026-08-21): `examples/better-harness/better_harness/agent.py`
baris 206-226 dan `libs/code/deepagents_code/agent.py` baris 3093-3110
(pola `recursion_limit`).
