# `deepagents` — middleware

Middleware adalah *extension point* utama `deepagents`. File ini: apa saja
yang bawaan, di tahap lifecycle mana masing-masing menyisip, urutannya, dan
interaksi antar-middleware yang berbahaya kalau urutannya salah.

Untuk tahapan lifecycle-nya sendiri lihat [`lifecycle.md`](lifecycle.md).

## Urutan stack yang dirakit `create_deep_agent`

Verifikasi runtime (`[code]`, dengan menyadap `create_agent` yang dipanggil
`deepagents/graph.py` baris 922):

```
minimal   : FilesystemMiddleware, SubAgentMiddleware, SummarizationMiddleware,
            PatchToolCallsMiddleware, AnthropicPromptCachingMiddleware

skills+memory+interrupt_on:
            SkillsMiddleware, FilesystemMiddleware, SubAgentMiddleware,
            SummarizationMiddleware, PatchToolCallsMiddleware,
            AnthropicPromptCachingMiddleware, MemoryMiddleware,
            HumanInTheLoopMiddleware

+ middleware=[TodoListMiddleware(), ModelCallLimitMiddleware(...)]:
            FilesystemMiddleware, SubAgentMiddleware, SummarizationMiddleware,
            PatchToolCallsMiddleware,
            ▲ TodoListMiddleware, ModelCallLimitMiddleware ▲   ← disisipkan di sini
            AnthropicPromptCachingMiddleware, MemoryMiddleware
```

Struktur formalnya: **base stack** → *middleware user* → **tail stack**.
`[code]` — `deepagents/graph.py` baris 817-876 (perakitan), 361-406
(docstring urutan resmi).

| Slot | Isi | Syarat |
|---|---|---|
| base | `SkillsMiddleware` | `skills=` diisi |
| base | `FilesystemMiddleware` | selalu (scaffolding wajib) |
| base | `SubAgentMiddleware` | ada subagent inline (termasuk `general-purpose` default) |
| base | `SummarizationMiddleware` | selalu |
| base | `PatchToolCallsMiddleware` | selalu |
| base | `AsyncSubAgentMiddleware` | ada `AsyncSubAgent` |
| — | **middleware user** | `middleware=[...]` |
| tail | `HarnessProfile.extra_middleware` | profil punya isi |
| tail | `_ToolExclusionMiddleware` | profil punya `excluded_tools` |
| tail | `AnthropicPromptCachingMiddleware` (+Bedrock/Fireworks bila paketnya ada) | selalu |
| tail | `MemoryMiddleware` | `memory=` diisi |
| tail | `HumanInTheLoopMiddleware` | `interrupt_on` gabungan tidak kosong |

Catatan: `_ToolExclusionMiddleware` di-`append` **setelah** merge middleware
user (`graph.py` baris 892-893), jadi urutan efektifnya adalah paling akhir —
lebih belakang daripada posisi tabel di atas. Komentar source-nya eksplisit:
"so excluded tool names are stripped last and cannot be restored by a custom
`wrap_model_call`".

## Tabel middleware bawaan

| Middleware | Hook yang dipakai | Yang dilakukan | `[code]` |
|---|---|---|---|
| `SkillsMiddleware` | `before_agent`, `wrap_model_call` | Muat index skill dari backend ke state, suntik ke system prompt | `middleware/skills.py:928,1018` |
| `FilesystemMiddleware` | `wrap_model_call`, `wrap_tool_call` | Registrasi 8 tool file, saring tool tak didukung backend, tegakkan `permissions`, evict hasil tool & `HumanMessage` besar ke backend, scrub blok multimodal | `middleware/filesystem.py:3018,3066,3471` |
| `SubAgentMiddleware` | `wrap_model_call` | Sediakan tool `task` + daftar subagent di deskripsinya | `middleware/subagents.py:722` |
| `SummarizationMiddleware` (dari `create_summarization_middleware`) | `wrap_model_call` | Truncate arg tool lama, kompaksi riwayat bila lewat threshold, offload pesan ter-evict ke `/conversation_history/...`, fallback saat `ContextOverflowError` | `middleware/summarization.py:1335,1626` |
| `PatchToolCallsMiddleware` | `before_agent` | Tambal `ToolMessage` sintetis untuk tool call dangling/invalid, lalu tulis ulang seluruh `messages` | `middleware/patch_tool_calls.py:14` |
| `AsyncSubAgentMiddleware` | `wrap_model_call` | 5 tool background: `start/check/update/cancel/list_async_task(s)` | `middleware/async_subagents.py:908` |
| `MemoryMiddleware` | `before_agent`, `wrap_model_call` | Muat `AGENTS.md` ke state, suntik ke system prompt dengan `cache_control` bila model Anthropic | `middleware/memory.py:274,380` |
| `AnthropicPromptCachingMiddleware` | (langchain-anthropic) | Pasang breakpoint cache; `unsupported_model_behavior="ignore"` jadi no-op di provider lain | `middleware/_prompt_caching.py:42` |
| `_ToolExclusionMiddleware` (privat) | `wrap_model_call` | Buang nama tool di `HarnessProfile.excluded_tools` dari `request.tools` | `middleware/_tool_exclusion.py:32` |
| `HumanInTheLoopMiddleware` (langchain) | `after_model` | `interrupt()` sebelum tool berjalan | `langchain/agents/middleware/human_in_the_loop.py:219` |
| `RubricMiddleware` | `before_agent`, `after_agent` | Nilai transkrip terhadap rubric, paksa iterasi ulang bila gagal — **tidak** di stack default | `middleware/rubric.py:522,573` |
| `SummarizationToolMiddleware` | `wrap_model_call` | Tool `compact_conversation` yang dipanggil model sendiri — **tidak** di stack default | `middleware/summarization.py:1793,2110` |
| `TodoListMiddleware` (langchain, **bukan** `deepagents`) | `after_model` | Tool `write_todos` + state `PlanningState.todos` — **tidak** di stack default | `langchain/agents/middleware/todo.py` |

## Interaksi berbahaya

Tiga aturan komposisi yang berbeda hidup berdampingan. Menyamakannya adalah
sumber bug urutan:

| Hook | Komposisi | Konsekuensi |
|---|---|---|
| `before_agent`, `before_model` | **Berurutan, sesuai urutan list** | `m[0]` jalan duluan |
| `after_model`, `after_agent` | **Berurutan, urutan TERBALIK** | `m[-1]` jalan duluan |
| `wrap_model_call`, `wrap_tool_call` | **Onion, `m[0]` = terluar** | `m[-1]` yang paling dekat ke model/tool = kata terakhir atas `request` |

`[code]` — `langchain/agents/factory.py` baris 1793 (`add_edge("model",
m[-1].after_model)`), 349 (`for h in reversed(handlers[:-2])`, komentar
"first in list becomes outermost layer"), 1758-1790 (rantai `before_*`).

### 1. Middleware yang menyaring tool vs middleware yang menambah tool

Penyaring harus **lebih dalam** (lebih belakang di list) daripada penambah.
Kalau tidak, penyaring melihat `request.tools` sebelum tool baru masuk dan
penyaringannya percuma. Inilah alasan `_ToolExclusionMiddleware`
di-`append` setelah semua merge. Kalau ditulis middleware penyaring sendiri
dan ditaruh lewat `middleware=[...]`, ia mendarat **sebelum** tail stack —
cukup dalam untuk menyaring tool base stack, tapi **tidak** menyaring tool
yang ditambahkan `extra_middleware` profil.

### 2. `MemoryMiddleware` vs middleware prompt-caching

Urutan terpasang: `AnthropicPromptCachingMiddleware` **lalu**
`MemoryMiddleware`. Ini disengaja — komentar source
(`graph.py` baris 856-858): profil dan caching ditaruh sebelum memory
"so that memory updates (which change the system prompt) don't invalidate
the Anthropic prompt cache prefix". Membalik urutannya (mis. dengan menaruh
`MemoryMiddleware()` sendiri lewat `middleware=[...]`, yang akan mendarat
**sebelum** tail stack) memindahkan konten yang berubah tiap sesi ke dalam
prefix yang di-cache → cache miss tiap kali `AGENTS.md` berubah. Biayanya
tagihan token, bukan crash — jadi tidak akan pernah terdeteksi tes.

### 3. `SummarizationMiddleware` vs middleware yang membaca `state["messages"]`

Versi `deepagents` **sengaja tidak memutasi** `state["messages"]`; kompaksi
hanya berlaku pada `request.messages` di dalam `wrap_model_call` dan dilacak
di field privat `_summarization_event`. Middleware `after_model`/`after_agent`
yang membaca `state["messages"]` karena itu tetap melihat transkrip **penuh**,
bukan versi terkompaksi — bagus untuk replay/eval, menyesatkan kalau dipakai
untuk memperkirakan berapa token yang benar-benar dikirim.
Sebaliknya `langchain.agents.middleware.SummarizationMiddleware` polos
menulis ulang state lewat `before_model` + `RemoveMessage(REMOVE_ALL_MESSAGES)`.
Mencampur keduanya = riwayat ditulis ulang dua kali.
`[code]` — `middleware/summarization.py` baris 1636-1668 (docstring
"Non-mutating message state").

### 4. `PatchToolCallsMiddleware` vs middleware `before_agent` lain

`PatchToolCallsMiddleware.before_agent` mengembalikan
`{"messages": [RemoveMessage(REMOVE_ALL_MESSAGES), *patched]}` — **seluruh**
riwayat ditulis ulang. Middleware `before_agent` yang jalan **sebelumnya**
dan menambahkan pesan akan melihat pesannya ikut ditulis ulang (masih ada,
karena `patched_messages` menyalin semuanya) — tapi middleware yang
mengandalkan identitas objek/ID pesan bisa kaget. `SkillsMiddleware` jalan
sebelum `PatchToolCalls`; `MemoryMiddleware` sesudahnya.

### 5. `HumanInTheLoopMiddleware` selalu terakhir → `after_model` pertama

Karena `create_deep_agent` menaruhnya di ujung tail stack, ia adalah
`after_model` yang dieksekusi **paling awal**. Middleware `after_model`
kustom yang ingin melihat/menyunting tool call *sebelum* manusia
menyetujuinya harus ditaruh **lebih belakang lagi** dari HITL — dan itu
tidak mungkin lewat `middleware=[...]` (yang mendarat sebelum tail).
Jalurnya: `HarnessProfile.extra_middleware`? Bukan juga — itu pun sebelum
HITL. Satu-satunya jalan resmi adalah `interrupt_on` dengan
`InterruptOnConfig.when` (predikat per tool call) atau
`description` berbentuk callable.

### 6. Nama duplikat = `AssertionError`

`create_agent` menolak dua middleware dengan `.name` sama
(`factory.py` baris 1108-1110). `_apply_custom_middleware` mencegah ini
dengan **mengganti di tempat** entri yang namanya cocok. Efek sampingnya:
mengirim `FilesystemMiddleware(...)` lewat `middleware=[...]` **mengganti**
yang bawaan (ini yang diinginkan); mengirim **subclass** dengan nama kelas
berbeda **tidak** mengganti, dan hasilnya dua filesystem middleware aktif.
Lihat [`extension-points.md`](extension-points.md) anti-pattern #1.

## Menulis middleware sendiri

Kontrak: subclass `langchain.agents.middleware.AgentMiddleware`, override
hook yang dibutuhkan saja. Atribut kelas yang relevan: `state_schema`,
`tools`, `name` (property, default `__class__.__name__`), `trace_policy`.

Contoh minimal yang benar-benar jalan — membatasi berapa kali satu nama tool
boleh dipanggil berturut-turut dengan argumen identik (kasus "agent berputar
di tempat" yang tidak ditangkap `ToolCallLimitMiddleware`, karena yang itu
menghitung total panggilan, bukan pengulangan):

```python
import json

from langchain.agents.middleware import AgentMiddleware, ToolCallRequest
from langchain_core.messages import ToolMessage


class RepeatedToolCallGuard(AgentMiddleware):
    """Tolak tool call yang identik dengan N panggilan sebelumnya berturut-turut."""

    def __init__(self, *, max_repeats: int = 3) -> None:
        super().__init__()
        self._max_repeats = max_repeats
        self._last: tuple[str, str] | None = None
        self._streak = 0

    def wrap_tool_call(self, request: ToolCallRequest, handler):
        call = request.tool_call
        key = (call["name"], json.dumps(call.get("args") or {}, sort_keys=True))
        self._streak = self._streak + 1 if key == self._last else 1
        self._last = key
        if self._streak > self._max_repeats:
            return ToolMessage(
                content=(
                    f"Tool `{call['name']}` sudah dipanggil {self._streak} kali "
                    "berturut-turut dengan argumen yang sama. Ubah pendekatan "
                    "atau laporkan kebuntuan ke pengguna."
                ),
                tool_call_id=call["id"],
                status="error",
            )
        return handler(request)


agent = create_deep_agent(
    model=model,
    tools=[...],
    middleware=[RepeatedToolCallGuard(max_repeats=3)],
)
```

Yang membuat contoh ini idiomatik:

- Memakai `wrap_tool_call`, bukan membungkus fungsi tool satu per satu.
- Mengembalikan `ToolMessage` berstatus `error`, bukan raise — model
  mendapat umpan balik dan bisa berbelok, sesuai pola
  `ShellAllowListMiddleware` di `libs/code/deepagents_code/agent.py`
  (repo maintainer) yang persis melakukan ini untuk command shell.
- Tidak memberi `name` kustom, sehingga tidak sengaja bertabrakan/mengganti
  middleware bawaan.
- State per-instance disimpan di atribut instance karena tidak perlu
  bertahan lintas checkpoint; kalau perlu bertahan, deklarasikan
  `state_schema` dengan field bertanda `PrivateStateAttr` dan kembalikan
  update lewat `Command`.

⚠️ Middleware dengan state instance seperti di atas **tidak** aman kalau
satu objek agent dipakai bersamaan oleh banyak thread. Untuk itu simpan
hitungan di `state_schema`, bukan di `self`.

Untuk kasus sederhana tersedia juga decorator: `@before_agent`,
`@before_model`, `@after_model`, `@after_agent`, `@wrap_model_call`,
`@wrap_tool_call`, `@dynamic_prompt` — semuanya dari
`langchain.agents.middleware`. `[code]` —
`langchain/agents/middleware/types.py` baris 934-2175.

## Sumber

**Versi yang dibaca**: `deepagents==0.7.8`, `langchain==1.3.16`.

`[code]` dari `references/recipes/.venv/lib/python3.13/site-packages/`:
`deepagents/graph.py`, `deepagents/middleware/*.py` (semua),
`langchain/agents/factory.py`,
`langchain/agents/middleware/types.py`,
`langchain/agents/middleware/__init__.py` (daftar `__all__`),
`langchain/agents/middleware/human_in_the_loop.py`,
`langchain/agents/middleware/todo.py`.

`[code]` dari `git clone --depth 1 langchain-ai/deepagents` (commit
`23b83ad`, 2026-08-21): `libs/code/deepagents_code/agent.py` baris 774-845
(`ShellAllowListMiddleware`) sebagai contoh middleware kustom tulisan
maintainer sendiri.

Verifikasi runtime `[code]`: urutan stack di atas dicetak dengan menyadap
`deepagents.graph.create_agent` dan membaca `[m.name for m in
kw["middleware"]]`.
