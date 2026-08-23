# `deepagents` — API reference

Referensi parameter tiap entrypoint publik `deepagents`, dibaca dari source
paket terinstal (bukan README). Untuk gambaran arsitektur baca dulu
[`../systems/deepagents.md`](../systems/deepagents.md); file ini adalah
lapisan detail di bawahnya.

Konvensi: tipe dan default ditulis **persis** seperti di signature.
Parameter bertanda ⚠️ adalah yang paling sering salah pakai — alasannya
ditulis di kolom efek.

## `create_deep_agent(...)`

`[code]` — `deepagents/graph.py` baris 268-288 (signature), 289-579
(docstring), 629-993 (implementasi).

Mengembalikan `CompiledStateGraph`, sudah dibungkus
`.with_config({"recursion_limit": 9_999, "metadata": {...}})`.

| Parameter | Tipe | Default | Efek |
|---|---|---|---|
| `model` | `str \| BaseChatModel \| None` | `None` ⚠️ | `None` **deprecated sejak 0.5.3**, dihapus di 1.0.0 — memicu `warn_deprecated` lalu memakai `ChatAnthropic(model_name="claude-sonnet-4-6")`. String `provider:model` diresolusi lewat `resolve_model` (`deepagents/_models.py`). Model yang dipilih juga menentukan `HarnessProfile` aktif lewat `_harness_profile_for_model`. |
| `tools` | `Sequence[BaseTool \| Callable \| dict] \| None` | `None` | **Aditif** — digabung dengan tool bawaan middleware, tidak pernah menggantinya. Untuk membuang tool bawaan pakai `HarnessProfile.excluded_tools` atau `FilesystemMiddleware(tools=[...])`, bukan parameter ini. Deskripsi tiap tool bisa ditimpa profil lewat `tool_description_overrides`. |
| `system_prompt` | `str \| SystemMessage \| None` | `None` | Slot `USER` pada rakitan `USER` → `BASE` → `SUFFIX`, dipisah baris kosong. `BASE`/`SUFFIX` datang dari `HarnessProfile.base_system_prompt`/`system_prompt_suffix`. `None` + profil kosong = system prompt authored kosong (sejak 0.7.0 `deepagents` tidak lagi menulis base prompt sendiri; `BASE_AGENT_PROMPT` deprecated). `SystemMessage` mempertahankan marker `cache_control` yang sudah ada. |
| `middleware` | `Sequence[AgentMiddleware]` | `()` ⚠️ | Disisipkan **setelah** base stack dan **sebelum** tail stack. Entri yang `.name`-nya sama dengan anggota stack yang ada **mengganti di tempat**; yang namanya baru disisipkan setelah anggota core terakhir. Lihat [`middleware.md`](middleware.md) — perilaku "ganti berdasarkan nama" ini adalah sumber bug diam paling umum. |
| `subagents` | `Sequence[SubAgent \| CompiledSubAgent \| AsyncSubAgent] \| None` | `None` | Routing berdasarkan bentuk dict: ada key `graph_id` → `AsyncSubAgent`; ada key `runnable` → `CompiledSubAgent`; selain itu `SubAgent` deklaratif. Subagent `general-purpose` ditambahkan otomatis kecuali caller sudah menyediakan yang bernama sama atau profil mematikannya. |
| `skills` | `list[str] \| None` | `None` | Path POSIX relatif terhadap root backend. Memasang `SkillsMiddleware` di posisi **paling depan** stack. Sumber belakangan menimpa sumber sebelumnya untuk nama skill yang sama. |
| `memory` | `list[str] \| None` | `None` | Path file `AGENTS.md`. Memasang `MemoryMiddleware(add_cache_control=True)` di **tail** stack, setelah middleware prompt-caching — urutan ini disengaja supaya update memory tidak membatalkan prefix cache Anthropic. |
| `permissions` | `list[FilesystemPermission] \| None` | `None` ⚠️ | Ditegakkan `FilesystemMiddleware` di level **tool**, bukan level backend — pemakaian backend langsung tidak lewat permission. Rule dievaluasi berurutan, match pertama menang; tanpa match = diizinkan. `mode="interrupt"` otomatis membangkitkan entri `interrupt_on` (lihat `handlers.md`). Kombinasi `permissions` + backend `SandboxBackendProtocol` **raise `NotImplementedError`** kecuali semua path ter-scope ke route non-eksekusi. |
| `backend` | `BackendProtocol \| None` | `None` → `StateBackend()` ⚠️ | Default adalah `StateBackend` (ephemeral, hidup di state LangGraph), **bukan** `LocalShellBackend`. Tool `execute` baru berguna kalau backend mengimplementasi `SandboxBackendProtocol`. Factory (callable) ditolak sejak 0.7 — kirim instance. |
| `interrupt_on` | `dict[str, bool \| InterruptOnConfig] \| None` | `None` | Digabung dengan entri hasil `permissions` (entri user menang per nama tool). Kalau gabungannya kosong, `HumanInTheLoopMiddleware` tidak dipasang sama sekali. `SubAgent` deklaratif mewarisi ini; `CompiledSubAgent` dan `AsyncSubAgent` **tidak**. |
| `response_format` | `ResponseFormat[ResponseT] \| type[ResponseT] \| dict \| None` | `None` | Diteruskan ke `create_agent`. Memvalidasi **bentuk** keluaran saja, bukan kebenaran isinya. |
| `state_schema` | `type[DeepAgentState] \| None` | `None` → `DeepAgentState` ⚠️ | Harus subclass `DeepAgentState` agar reducer `DeltaChannel` pada `messages` tetap ada — **tidak divalidasi runtime** (TypedDict tidak bisa `issubclass`), jadi salah pakai baru terlihat sebagai checkpoint membengkak. Diteruskan ke `SubAgent` deklaratif, **tidak** ke `CompiledSubAgent`/`AsyncSubAgent`. Docstring menyarankan menaruh field tambahan di `state_schema` middleware, bukan di sini. |
| `context_schema` | `type[ContextT] \| None` | `None` | Context run-scoped immutable, diteruskan apa adanya ke `create_agent`. |
| `checkpointer` | `Checkpointer \| None` | `None` | Diteruskan apa adanya. `deepagents` tidak pernah membangun checkpointer sendiri. Wajib ada kalau memakai `interrupt_on`. |
| `store` | `BaseStore \| None` | `None` | Diteruskan apa adanya. `StoreBackend(store=None)` mengambil store dari execution context LangGraph. |
| `debug` | `bool` | `False` | Diteruskan apa adanya. |
| `name` | `str \| None` | `None` | Diteruskan apa adanya, dan masuk metadata `lc_agent_name`. |
| `cache` | `BaseCache \| None` | `None` | Diteruskan apa adanya. |

**Yang tidak ada di signature ini** (sering dikira ada): tidak ada
`recursion_limit`, `max_iterations`, `timeout`, `temperature`, `verbose`,
`memory_store`, `todo`, maupun `planning`. Batas loop diatur lewat
`.with_config({"recursion_limit": N})` atau `config=` saat `invoke`
(lihat [`handlers.md`](handlers.md)).

## `DeepAgentState`

`[code]` — `deepagents/graph.py` baris 70-73.

`AgentState` dengan satu perbedaan: field `messages` di-annotate
`DeltaChannel(_messages_delta_reducer, snapshot_frequency=50)` sehingga
pertumbuhan checkpoint turun dari O(N²) ke O(N). Turunkan dari kelas ini,
jangan dari `AgentState`, kalau memakai `state_schema=`.

## Spec subagent

`[code]` — `deepagents/middleware/subagents.py` baris 36-243;
`deepagents/middleware/async_subagents.py` baris 34-79.

| Key | Bentuk | Wajib | Catatan |
|---|---|---|---|
| `name` | `str` | ya | Dipakai model sebagai argumen `subagent_type` tool `task`. |
| `description` | `str` | ya | Ini yang dibaca model untuk memutuskan delegasi — tulis action-oriented. |
| `system_prompt` | `str` | ya (`SubAgent`) | Profil harness ikut menambahkan `BASE`/`SUFFIX` di atasnya. |
| `tools` | `Sequence[...]` | tidak | ⚠️ Kalau key `tools` **tidak ada**, subagent mewarisi `tools` agent utama. Kalau ada tapi `[]`, subagent tidak dapat tool caller sama sekali (tool middleware tetap ada). |
| `model` | `str \| BaseChatModel` | tidak | Diresolusi terpisah, dan memilih `HarnessProfile`-nya sendiri. |
| `middleware` | `list[AgentMiddleware]` | tidak | Aturan ganti-berdasarkan-nama yang sama berlaku. Ini jalur resmi untuk `FilesystemMiddleware(tools=[...])` per subagent. |
| `interrupt_on` | `dict[...]` | tidak | Kalau ada, **menggantikan** warisan dari top-level, tidak menambah. |
| `skills` | `list[str]` | tidak | Memasang `SkillsMiddleware` khusus subagent itu. |
| `permissions` | `list[FilesystemPermission]` | tidak | Kalau ada, **mengganti total** rule parent, tidak menambah. |
| `response_format` | `ResponseFormat \| type \| dict` | tidak | Kalau diisi, `structured_response` yang diserialkan JSON menjadi isi `ToolMessage`, menggantikan ekstraksi pesan terakhir. |
| `runnable` | `Runnable` | ya (`CompiledSubAgent`) | State schema-nya **wajib** punya key `messages`, kalau tidak `_return_command_with_state_update` raise `ValueError`. |
| `graph_id` | `str` | ya (`AsyncSubAgent`) | Keberadaan key ini yang me-route spec ke `AsyncSubAgentMiddleware`. |
| `url`, `headers` | `str`, `dict[str, str]` | tidak (`AsyncSubAgent`) | Endpoint Agent Protocol dan header auth. |

## Backend

`[code]` — `deepagents/backends/*.py`, signature `__init__` masing-masing.

| Konstruktor | Signature | Catatan |
|---|---|---|
| `StateBackend()` | tanpa argumen | Default. Ephemeral, isi file hidup di state LangGraph. |
| `FilesystemBackend(root_dir=None, virtual_mode=True, max_file_size_mb=10)` | positional | `root_dir=None` → cwd. `virtual_mode=True` memblokir `..`, `~`, dan path absolut di luar `root_dir` untuk **operasi file** — bukan sandbox. |
| `LocalShellBackend(root_dir=None, *, virtual_mode=True, timeout=DEFAULT_EXECUTE_TIMEOUT, max_output_bytes=100_000, env=None, inherit_env=False)` | ⚠️ | Subclass `FilesystemBackend` + `SandboxBackendProtocol`. Docstring-nya sendiri menyatakan `virtual_mode` **tidak memberi keamanan apa pun** begitu shell aktif. |
| `StoreBackend(*, namespace: NamespaceFactory, store=None)` | keyword-only | `namespace` adalah satu-satunya *hook* scoping resmi. Wildcard `*` ditolak. `store=None` → diambil dari execution context LangGraph. |
| `CompositeBackend(default, routes, *, artifacts_root="/")` | `default` & `routes` positional | Prefix route harus diawali `/` dan sebaiknya diakhiri `/`. Match prefix terpanjang menang. |
| `ContextHubBackend(identifier, client=None)` | positional | Persisten di LangSmith Hub agent repo. |
| `LangSmithSandbox(sandbox)` | positional | Membungkus sandbox terkelola LangSmith. |
| `DaytonaSandbox(*, sandbox, timeout=30*60, sync_polling_interval=0.1)` | keyword-only | Paket terpisah `langchain-daytona`, bukan bagian `deepagents`. `[code]` — `libs/partners/daytona/langchain_daytona/sandbox.py` baris 30-59 (repo `langchain-ai/deepagents`). |

## `FilesystemMiddleware(...)`

`[code]` — `deepagents/middleware/filesystem.py` baris 1620-1744.

Semua keyword-only.

| Parameter | Default | Efek |
|---|---|---|
| `backend` | `None` → `StateBackend()` | Kalau dipasang manual lewat `middleware=[...]`, **harus** dikirim backend yang sama dengan yang dipakai agent; kalau tidak agent punya dua filesystem berbeda. |
| `system_prompt` | `None` | Mengganti fragmen prompt filesystem. |
| `custom_tool_descriptions` | `None` | Map nama tool → deskripsi. |
| `tool_token_limit_before_evict` | `20000` | Hasil tool di atas ambang ini ditulis ke backend dan diganti preview. `None` mematikan eviction. |
| `human_message_token_limit_before_evict` | `50000` | Sama, untuk `HumanMessage` terakhir. |
| `max_execute_timeout` | `3600` | Batas atas timeout per command yang boleh diminta model. |
| `grep_max_count` | `1000` | Cap total match; `None` mematikan cap default. |
| `tools` | `None` → semua ⚠️ | `list[FsToolName]` atau `"all"`. `FsToolName = Literal["ls","read_file","write_file","edit_file","delete","glob","grep","execute"]`. `read_file` **wajib** ada dalam list, kalau tidak `ValueError`. Tool di luar list tidak diregistrasi sama sekali (bukan sekadar disembunyikan). |
| `_permissions` | `None` | Privat — lewat `create_deep_agent(permissions=...)`, bukan langsung. |

Catatan surface: dengan `StateBackend` default, tool node berisi
`delete, edit_file, execute, glob, grep, ls, read_file, task, write_file`.
`execute` **terdaftar** tapi disaring dari view model saat `wrap_model_call`
karena backend tidak mendukung eksekusi. `[code]` — verifikasi runtime,
`FilesystemMiddleware._filter_unsupported_tools_and_apply_prompt`
(`middleware/filesystem.py` baris 3018-3064, dipanggil dari `wrap_model_call` baris 3094).

## `FilesystemPermission`

`[code]` — `deepagents/middleware/filesystem.py` baris 384-417.

Dataclass dengan `operations: list[FilesystemOperation]`,
`paths: list[str]`, `mode: Literal["allow","deny","interrupt"] = "allow"`.
Path **wajib** diawali `/`, tidak boleh mengandung `..` (`ValueError`)
maupun `~` (`NotImplementedError`).

## Profil

`[code]` — `deepagents/profiles/harness/harness_profiles.py`,
`deepagents/profiles/provider/provider_profiles.py`.

`register_harness_profile(key, profile)` — `key` adalah `"provider"` atau
`"provider:model"`. Registrasi bersifat **aditif/merge**, bukan replace.
Field `HarnessProfile` yang relevan: `base_system_prompt`,
`system_prompt_suffix`, `tool_description_overrides`, `excluded_tools`,
`excluded_middleware`, `extra_middleware`, `general_purpose_subagent`.

⚠️ `excluded_middleware` **menolak** `FilesystemMiddleware` dan
`SubAgentMiddleware` (scaffolding wajib) dengan `ValueError` saat konstruksi
profil; entri yang tidak match apa pun di stack juga `ValueError`. Untuk
menghilangkan tool `task`, pakai
`general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)` dan
jangan kirim subagent sinkron — bukan `excluded_middleware`.

`HarnessProfileConfig` adalah varian **deklaratif** dari `HarnessProfile`,
untuk profil yang dimuat dari YAML/JSON. Bedanya satu: `excluded_middleware`
hanya menerima **string** nama, tidak menerima kelas — karena file konfigurasi
tidak bisa mengimpor. `register_harness_profile` menerima keduanya dan
mengonversi `HarnessProfileConfig` ke `HarnessProfile` saat registrasi, jadi
tidak ada langkah konversi manual. `HarnessProfileConfig.from_harness_profile`
melakukan arah sebaliknya, memakai `serialized_name` sebuah middleware kalau
ada supaya round-trip ke file konfigurasi stabil. `[code]` —
`deepagents/profiles/harness/harness_profiles.py` baris 192-330 (kelas), 439 (`from_harness_profile`).

`register_provider_profile(key, profile)` mengatur fase **konstruksi model**,
ortogonal terhadap `HarnessProfile` yang mengatur perilaku runtime setelah
model jadi.

Cakupan file ini terhadap `deepagents.__all__` (19 nama): **18 tercakup**.
Yang tidak: `__version__`, sebuah konstanta string versi tanpa parameter —
di luar lingkup referensi parameter.

## Sumber

**Versi yang dibaca**: `deepagents==0.7.8`, dari
`references/recipes/.venv/lib/python3.13/site-packages/`, bersama
`langchain==1.3.16` dan `langchain-anthropic==1.6.1`.

File `[code]` yang dibaca untuk file ini:

- `deepagents/__init__.py`, `deepagents/graph.py` (utuh)
- `deepagents/middleware/filesystem.py` (`FilesystemPermission`, `FsToolName`, `FilesystemMiddleware.__init__`, `wrap_model_call`, `wrap_tool_call`)
- `deepagents/middleware/subagents.py`, `async_subagents.py` (TypedDict spec, `_return_command_with_state_update`)
- `deepagents/middleware/patch_tool_calls.py`, `_prompt_caching.py`, `_state.py`, `_tool_exclusion.py`, `_fs_interrupt.py` (utuh)
- `deepagents/middleware/summarization.py` (`create_summarization_middleware`, `compute_summarization_defaults`)
- `deepagents/backends/__init__.py`, `state.py`, `store.py`, `filesystem.py`, `local_shell.py`, `composite.py` (signature `__init__` + docstring kelas)
- `deepagents/profiles/harness/harness_profiles.py` (field `HarnessProfile`, `register_harness_profile`)
- `langchain/agents/factory.py`, `langchain/agents/middleware/types.py`

Sumber `[code]` di luar paket terinstal, dibaca dari `git clone --depth 1`
repo `langchain-ai/deepagents` (commit `23b83ad`, 2026-08-21):

- `libs/partners/daytona/langchain_daytona/sandbox.py` — signature `DaytonaSandbox.__init__`
