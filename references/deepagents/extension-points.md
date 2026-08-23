# `deepagents` — extension point

## Aturan keras

> **Jangan menulis kode custom di lapisan yang sudah punya extension point.**

Kode custom di lapisan yang salah biasanya **tetap jalan**. Itu masalahnya:
ia lolos tes, lolos review, dan baru terlihat salah saat perilaku bawaan
diam-diam dilewati — tool yang dikira sudah dibatasi ternyata masih terpasang,
permission yang dikira ditegakkan ternyata tidak dilewati sama sekali,
prompt cache yang dikira aktif ternyata miss tiap sesi. Semuanya gagal tanpa
error.

Sebelum menulis kelas/fungsi baru, cocokkan dulu kebutuhannya ke tabel di
bawah. Kalau ada barisnya, pakai itu.

## Inventaris extension point resmi

| # | Extension point | Bentuk | Untuk kebutuhan | `[code]` |
|---|---|---|---|---|
| 1 | **Middleware** | subclass `AgentMiddleware` atau decorator `@before_model`/`@wrap_tool_call`/dst, dipasang lewat `middleware=[...]` | mengubah prompt, tool, request, hasil tool, state, atau menghentikan loop | `langchain/agents/middleware/types.py:385` |
| 2 | **Backend** | implementasi `BackendProtocol` (atau `SandboxBackendProtocol` untuk `execute`), dipasang lewat `backend=` | ke mana file dibaca/ditulis dan di mana shell berjalan | `deepagents/backends/protocol.py:378,840` |
| 3 | **Composite backend** | `CompositeBackend(default=..., routes={prefix: backend})` | sebagian path ephemeral, sebagian durable/ter-scope | `deepagents/backends/composite.py:180` |
| 4 | **Subagent** | `SubAgent` / `CompiledSubAgent` / `AsyncSubAgent` lewat `subagents=` | isolasi context per subtugas, tool surface berbeda, model berbeda | `deepagents/middleware/subagents.py:36,166` |
| 5 | **Tool** | fungsi/`BaseTool` lewat `tools=` | kemampuan baru yang dipanggil model | `deepagents/graph.py:319` |
| 6 | **State schema** | `state_schema` pada middleware (disarankan) atau `create_deep_agent(state_schema=)` (global) | field state tambahan lintas turn; `PrivateStateAttr` untuk yang tidak boleh menyeberang ke subagent | `deepagents/middleware/_state.py:14`, `graph.py:330` |
| 7 | **Handler / hook** | `interrupt_on`, `permissions`, `InterruptOnConfig.when` | jeda approval manusia dan aturan izin filesystem | `deepagents/middleware/_fs_interrupt.py`, `graph.py:326,328` |
| 8 | **Harness profile** | `register_harness_profile(key, HarnessProfile(...))` | buang tool bawaan, timpa deskripsi tool, tambah middleware ke **semua** stack (main + GP subagent + subagent deklaratif), atur base/suffix prompt per model | `deepagents/profiles/harness/harness_profiles.py:483,977` |
| 9 | **Provider profile** | `register_provider_profile(key, ProviderProfile(...))` | mengubah cara model dikonstruksi per provider | `deepagents/profiles/provider/provider_profiles.py:38` |
| 10 | **Graph config** | `.with_config({...})` / `invoke(config=...)` | `recursion_limit`, `thread_id`, metadata, callback | `deepagents/graph.py:984-993` |
| 11 | **Skill** | direktori `SKILL.md` lewat `skills=` | instruksi berjenjang (progressive disclosure) tanpa membengkakkan system prompt | `deepagents/middleware/skills.py:764` |
| 12 | **Memory** | file `AGENTS.md` lewat `memory=` | konteks persisten yang selalu masuk system prompt | `deepagents/middleware/memory.py:178` |

Yang **bukan** extension point (dan karena itu boleh/harus ditulis sendiri di
lapisan aplikasi): trigger (kapan agent dipanggil), antrian, kill switch
armada, autentikasi/penentuan identitas user, dan storage checkpointer/store
itu sendiri. `deepagents` sengaja tidak menyentuh keempatnya.

## Anti-pattern

### 1. Menyubclass middleware bawaan untuk mempersempit tool

**Yang biasa ditulis**

```python
class RestrictedFilesystem(FilesystemMiddleware):
    def __init__(self):
        super().__init__(tools=["read_file", "ls"])

agent = create_deep_agent(model=m, middleware=[RestrictedFilesystem()])
```

**Kenapa salah**: `_apply_custom_middleware` mengganti entri stack
**berdasarkan `.name`**, dan `.name` default adalah nama kelas. Kelas
`RestrictedFilesystem` namanya berbeda dari `FilesystemMiddleware`, jadi ia
**ditambahkan**, bukan menggantikan. `FilesystemMiddleware` bawaan tetap
terpasang dengan seluruh 8 tool-nya.

Verifikasi runtime `[code]`:

```
default                                    → delete, edit_file, execute, glob,
                                             grep, ls, read_file, task, write_file
middleware=[FilesystemMiddleware(          → ls, read_file, task
    tools=["read_file","ls"])]
middleware=[MyFS(tools=["read_file"])]     → delete, edit_file, execute, glob,
  (subclass, nama kelas berbeda)             grep, ls, read_file, task, write_file
```

Pembatasan pada baris ketiga **hilang tanpa jejak** — tidak ada warning,
tidak ada error.

**Cara resmi**: kirim **instance kelas aslinya** dengan konfigurasi berbeda.

```python
agent = create_deep_agent(
    model=m,
    backend=backend,                      # backend yang sama, wajib
    middleware=[FilesystemMiddleware(backend=backend, tools=["read_file", "ls"])],
)
```

Untuk per-subagent, taruh instance yang sama di `spec["middleware"]` —
docstring `SubAgent` menyebut ini eksplisit: *"To restrict filesystem tools,
include a `FilesystemMiddleware(tools=...)` instance here."*
Untuk menyembunyikan tool dari **semua** stack sekaligus, pakai
`HarnessProfile(excluded_tools=frozenset({"execute", "delete"}))`.

`[code]` — `deepagents/graph.py` baris 250-284 (`_apply_custom_middleware`);
`deepagents/middleware/subagents.py` baris 62-66;
`deepagents/middleware/filesystem.py` baris 1714-1744.

### 2. Membungkus fungsi tool satu per satu untuk audit/guard/retry

**Yang biasa ditulis**

```python
def audited(fn):
    def wrapper(*a, **kw):
        log.info("tool call: %s", fn.__name__)
        try:
            return fn(*a, **kw)
        except Exception as e:
            return f"error: {e}"
    return wrapper

tools = [audited(search), audited(fetch), audited(publish)]
```

**Kenapa salah**: tiga masalah sekaligus. (a) Tool bawaan middleware
(`read_file`, `write_file`, `execute`, `task`) tidak pernah lewat wrapper ini
— justru tool paling berisiko yang luput. (b) Wrapper kehilangan `tool_call_id`
sehingga tidak bisa mengembalikan `ToolMessage` yang benar. (c) Setiap tool
baru harus diingat untuk dibungkus; yang terlupa gagal diam-diam.

**Cara resmi**: `wrap_tool_call` melihat **setiap** tool call, termasuk yang
diinjeksi middleware, dan menerima `ToolCallRequest` lengkap.

```python
class AuditMiddleware(AgentMiddleware):
    def wrap_tool_call(self, request, handler):
        log.info("tool call: %s %s", request.tool_call["name"], request.tool_call["args"])
        return handler(request)
```

Untuk error dan retry jangan tulis sendiri sama sekali — sudah ada
`ToolErrorMiddleware(on_error=...)` dan
`ToolRetryMiddleware(max_retries=..., backoff_factor=...)`. Maintainer
sendiri memakai jalur `wrap_tool_call` untuk hal ini
(`ShellAllowListMiddleware`, `libs/code/deepagents_code/agent.py:774`).

`[code]` — `deepagents/middleware/filesystem.py` baris 3471;
`langchain/agents/middleware/tool_error.py:75`, `tool_retry.py:133`.

### 3. Loop `while` sendiri untuk membatasi jumlah langkah

**Yang biasa ditulis**

```python
for i in range(20):
    result = agent.invoke(state)
    if not result["messages"][-1].tool_calls:
        break
    state = result
```

**Kenapa salah**: `agent.invoke` **sudah** menjalankan loop sampai selesai;
membungkusnya lagi berarti menjalankan agent 20 kali dari awal, masing-masing
dengan riwayat yang tumbuh. `recursion_limit` default `9_999` tetap berlaku
di dalam tiap panggilan, jadi batas 20 di luar tidak membatasi apa-apa.
Ini juga merusak akuntansi `run_limit` pada middleware limit, karena tiap
`invoke` adalah run baru.

**Cara resmi**: satu `invoke`, batas ditaruh di config atau middleware.

```python
agent = create_deep_agent(model=m, tools=tools).with_config(
    {"recursion_limit": 60}
)
# atau, dengan pesan yang bisa dibaca model:
agent = create_deep_agent(
    model=m,
    tools=tools,
    middleware=[ModelCallLimitMiddleware(thread_limit=25, exit_behavior="end")],
)
```

`.with_config({"recursion_limit": N})` persis pola yang dipakai maintainer di
`examples/better-harness/better_harness/agent.py:225` dan
`libs/code/deepagents_code/agent.py:3110`.

Pengecualian yang **memang** loop luar: pola Ralph (`examples/ralph_mode/`) —
tiap iterasi sengaja mulai dari **thread baru dengan context kosong**, dan
filesystem yang jadi memori antar-iterasi. Itu bukan pembatas langkah, itu
strategi context. Loop luar yang hanya "membatasi jumlah langkah" tidak punya
alasan seperti itu.

`[code]` — `deepagents/graph.py` baris 984-993;
`langchain/agents/middleware/model_call_limit.py:126`;
repo `langchain-ai/deepagents` commit `23b83ad`.

### 4. Filter path/izin di dalam fungsi tool

**Yang biasa ditulis**

```python
@tool
def safe_write(path: str, content: str) -> str:
    if path.startswith("/secrets"):
        return "denied"
    return backend.write(path, content)
```

**Kenapa salah**: hanya berlaku untuk tool tulisan sendiri. `write_file`,
`edit_file`, `delete`, `execute`, `glob`, dan `grep` bawaan tidak lewat sini.
Dan `grep(path=None)` bisa mengembalikan isi file yang sedang "dilindungi".

**Cara resmi**: `permissions=[FilesystemPermission(...)]`. Rule dievaluasi
berurutan (match pertama menang), berlaku ke semua tool filesystem bawaan,
dan `mode="interrupt"` otomatis menyambung ke HITL — termasuk untuk tool bulk
(`ls`/`glob`/`grep`) yang subtree pencariannya bersinggungan dengan pola rule.

```python
permissions = [
    FilesystemPermission(operations=["read", "write"], paths=["/secrets/**"], mode="deny"),
    FilesystemPermission(operations=["write"], paths=["/**"], mode="interrupt"),
]
```

⚠️ Batasnya nyata dan harus diketahui: `permissions` **tidak** berlaku pada
tool `execute` — `FilesystemMiddleware.__init__` malah **raise
`NotImplementedError`** kalau `permissions` dipasang bersama backend
`SandboxBackendProtocol` yang path-nya tidak ter-scope ke route. Untuk backend
ber-shell, penegakan izin harus di lapisan lain (allow-list command lewat
`wrap_tool_call`, atau sandbox itu sendiri).

`[code]` — `deepagents/middleware/filesystem.py` baris 384-417, 1691-1700;
`deepagents/middleware/_fs_interrupt.py` baris 20-46.

### 5. Menyalin-tempel `create_deep_agent` untuk mengubah stack

**Yang biasa ditulis**: menyalin isi `graph.py` ke `my_agent.py` lalu
menghapus/menukar beberapa baris middleware, karena "tidak ada parameter
untuk membuang X".

**Kenapa salah**: begitu disalin, agent berhenti mengikuti versi library —
perbaikan bug, middleware baru, dan perubahan urutan tail stack tidak ikut.
Dan `_REQUIRED_MIDDLEWARE` ada justru untuk mencegah agent yang "diam-diam
terdegradasi"; salinan manual kehilangan penjagaan itu.

**Cara resmi**: `HarnessProfile`.

```python
register_harness_profile(
    "anthropic:claude-sonnet-4-6",
    HarnessProfile(
        system_prompt_suffix="Jawab dalam Bahasa Indonesia.",
        excluded_tools=frozenset({"execute"}),
        excluded_middleware=frozenset({"SummarizationMiddleware"}),
        extra_middleware=[AuditMiddleware()],
        general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
    ),
)
```

Profil berlaku ke main agent **dan** subagent deklaratif **dan** GP subagent
sekaligus — cakupan yang tidak bisa dicapai `middleware=[...]`. Registrasi
bersifat merge, jadi beberapa modul boleh melapisinya.

⚠️ `excluded_middleware` menolak `FilesystemMiddleware` dan
`SubAgentMiddleware` dengan `ValueError` (scaffolding wajib), dan menolak
entri yang tidak match apa pun di stack (indikasi typo/profil basi). Untuk
menghilangkan tool `task`, pakai
`general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)` +
tidak mengirim subagent sinkron.

`[code]` — `deepagents/graph.py` baris 287-314;
`deepagents/profiles/harness/harness_profiles.py` baris 483-700 (field `HarnessProfile`), 977-1026 (`register_harness_profile`).

### 6. Menyimpan file agent lewat modul storage sendiri

**Yang biasa ditulis**: fungsi `save_artifact(user_id, path, content)` yang
menulis ke S3/Postgres, dipanggil dari dalam tool custom, sementara agent
tetap memakai `StateBackend` default.

**Kenapa salah**: agent jadi punya dua filesystem yang tidak saling tahu.
`read_file`/`glob`/`grep` tidak melihat artefak yang disimpan jalur kedua;
eviction hasil tool besar menulis ke backend pertama; skill dan memory
dimuat dari backend pertama. Model akan menulis file, lalu tidak menemukannya.

**Cara resmi**: satu backend, dirutekan.

```python
backend = CompositeBackend(
    default=StateBackend(),
    routes={"/memories/": StoreBackend(namespace=lambda rt: (user_id, "memories"))},
)
```

Storage yang benar-benar baru = implementasi `BackendProtocol` baru, bukan
modul di samping. `namespace` pada `StoreBackend` adalah satu-satunya *hook*
scoping per-user yang resmi.

`[code]` — `deepagents/backends/composite.py` baris 180-240;
`deepagents/backends/store.py` baris 89-120;
`deepagents/middleware/filesystem.py` baris 1602-1614 (contoh di docstring).

## Catatan: dua arti kata "middleware"

Di scaffold [`../scaffolds/_base.md`](../scaffolds/_base.md) ada
`ScopeMiddleware`, dan itu **bukan** `AgentMiddleware` — itu
`starlette.middleware.base.BaseHTTPMiddleware`, lapisan HTTP yang
me-resolve identitas dari request sebelum agent dipanggil sama sekali.
Dua hal berbeda dengan nama sama. Aturan keras di atas hanya berlaku untuk
`AgentMiddleware`.

## Sumber

**Versi yang dibaca**: `deepagents==0.7.8`, `langchain==1.3.16`, dari
`references/recipes/.venv/lib/python3.13/site-packages/`.

`[code]`: `deepagents/graph.py`, `deepagents/backends/{protocol,composite,store,state,filesystem,local_shell}.py`,
`deepagents/middleware/{filesystem,subagents,_state,_fs_interrupt,_tool_exclusion,skills,memory}.py`,
`deepagents/profiles/harness/harness_profiles.py`,
`langchain/agents/middleware/{types,tool_error,tool_retry,model_call_limit}.py`.

`[code]` dari `git clone --depth 1 langchain-ai/deepagents` (commit
`23b83ad`, 2026-08-21): `libs/code/deepagents_code/agent.py`,
`examples/better-harness/better_harness/agent.py`,
`examples/ralph_mode/ralph_mode.py`.

Verifikasi runtime `[code]` untuk anti-pattern #1: tiga agent dibangun
(`default`, `FilesystemMiddleware(tools=[...])`, dan subclass dengan nama
kelas berbeda) lalu `sorted(agent.nodes["tools"].bound.tools_by_name)`
dibandingkan — hasilnya persis seperti tabel di anti-pattern #1.
