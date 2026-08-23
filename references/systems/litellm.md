# LiteLLM (Proxy)

> Label tiap klaim: [code] / [docs] / [inferred]

Tier **T2**. `BerriAI/litellm`, gateway/proxy Python (FastAPI) di depan
100+ provider LLM, dipilih sebagai eksemplar **kuota & rate-limit per user**
sesuai kandidat T2 spec §10. **Catatan penting**: LiteLLM Proxy bukan agent
harness — ia tidak punya loop tool-calling atau delegasi subagent. Tujuh
sumbu di bawah dijawab apa adanya untuk sistem ini: sebagian sumbu (loop
shape, delegation) dipetakan ke konsep terdekat yang benar-benar ada
(retry/fallback loop, multi-deployment routing), bukan dipaksakan ke bentuk
agent-loop yang tidak dimilikinya — kejujuran didahulukan atas kelengkapan
artifisial.

## Arketipe

Bukan salah satu dari tujuh arketipe agent — LiteLLM adalah **infrastruktur
serving** (lapisan Runtime/gateway) yang dipakai *oleh* arketipe mana pun
sebagai jalur ke LLM. Paling dekat secara fungsi dengan baris "Gateway / SSE"
dan "State store" di tabel serving §8.3 spec desain: IO-bound, disinyal HPA
lewat koneksi aktif, bukan RPS. `[code]` — struktur direktori
`litellm/proxy/` (puluhan sub-router endpoint: `auth/`, `guardrails/`,
`hooks/`, `management_endpoints/`, `db/`).

## 1. Loop shape

Bukan ReAct — **retry-with-cooldown** di dalam `Router.completion()`/
`Router.acompletion()`. Parameter `num_retries` (default: `litellm.num_retries`
jika diset, kalau tidak jatuh ke `openai.DEFAULT_MAX_RETRIES`) mengulang
panggilan ke deployment lain dalam model group yang sama saat satu deployment
gagal. Deployment yang gagal berulang (`allowed_fails`) dimasukkan ke
**cooldown** (`cooldown_time`, default `DEFAULT_COOLDOWN_TIME_SECONDS`) lewat
`CooldownCache`/`_set_cooldown_deployments`, dikeluarkan sementara dari
kandidat routing — bukan dihapus permanen. `enable_weighted_failover=True`
(khusus strategi `"simple-shuffle"`, khusus jalur async) membuat kegagalan
retryable memicu pemilihan ulang berbobot di deployment lain **sebelum**
fallback lintas-group dicoba, dibatasi `max_fallbacks`. Siapa yang
"memutuskan berhenti": bukan model — murni counter retry + status HTTP/
exception dari provider. `[code]` — `litellm/router.py` baris 416, 437-440,
479-498, 665-682.

## 2. Context

Bukan compaction pesan (LiteLLM tidak menyimpan riwayat percakapan sisi
server per default — itu tanggung jawab klien). Yang ada: **cache prompt**
lintas-request via hook `cache_control_check.py` (menghormati/menyuntik
`cache_control` provider-level, mis. Anthropic prompt caching) dan caching
respons (`DualCache` — in-memory + Redis) dipakai luas untuk rate-limit
counter, bukan untuk isi percakapan. `[code]` — listing
`litellm/proxy/hooks/cache_control_check.py`;
`litellm/proxy/hooks/parallel_request_limiter.py` baris 10 (import
`DualCache`).

## 3. Tool surface

Satu permukaan API **luas dan seragam** (kompatibel-OpenAI:
`/chat/completions`, `/embeddings`, `/responses`, dst — terlihat dari
sub-router `openai_files_endpoints`, `realtime_endpoints`,
`fine_tuning_endpoints`, `batches_endpoints`) yang menerjemahkan ke 100+
provider berbeda di baliknya — ini kebalikan pola "tool" dalam arti agent:
di sini "tool surface" berarti **satu kontrak API dipetakan ke banyak
backend**, bukan banyak tool dipanggil satu model. `[code]` — listing
`litellm/proxy/*_endpoints/` (>15 sub-router).

## 4. Delegation

Tidak ada subagent dalam arti agent-harness. Yang paling dekat secara
struktural adalah **routing lintas-deployment**: `routing_strategy` (Literal
`"simple-shuffle"`, `"least-busy"`, `"usage-based-routing"`,
`"latency-based-routing"`, `"cost-based-routing"`, plus `"lar1"` — strategi
khusus lewat `apply_lar1_routing_strategy`) memilih **deployment mana** yang
menangani satu request dari sekumpulan deployment yang mengklaim
`model_name` sama. `RoutingGroup` (`routing_groups: Optional[List[RoutingGroup]]`)
membolehkan strategi routing **berbeda per grup model bernama**, sisanya
jatuh ke grup implisit `"default"`. Ini bukan delegasi hasil-kembali seperti
subagent — hasil satu deployment terpilih langsung jadi respons request,
tidak ada agregasi hasil dari beberapa panggilan paralel di jalur normal.
`[code]` — `litellm/router.py` baris 441-449, 491-493, 700, 754-761.

## 5. State & resume

"Resume" tidak berlaku (proxy stateless per-request). "State" di sini adalah
**ledger kuota/spend durable**, disimpan lewat skema Prisma/Postgres:
`LiteLLM_BudgetTable`, `LiteLLM_UserTable`, `LiteLLM_TeamTable`,
`LiteLLM_VerificationToken` (API key + scope), `LiteLLM_SpendLogs` (log
transaksi per-call). Ini persis lapisan "kuota & rate-limit per user" yang
jadi alasan LiteLLM masuk kandidat T2 — state kuota hidup di DB durable,
bukan di memori proses, sehingga bertahan lintas restart & konsisten
lintas-instance proxy horizontal. `[code]` — `litellm/proxy/schema.prisma`
baris 12, 118, 234, 416, 611 (nama model, dikonfirmasi lewat grep, isi field
detail tidak dibaca semua).

Counter rate-limit jangka pendek (RPM/TPM per key/user/team/end-user/model)
memakai `DualCache` (in-memory + Redis) — cepat tapi bisa direset/di-scale
horizontal lewat Redis; bukan durable seperti tabel spend. `[code]` —
`litellm/proxy/hooks/parallel_request_limiter.py` baris 43-49 (`CacheObject`
dengan field `request_count_api_key`, `request_count_user_id`,
`request_count_team_id`, `request_count_end_user_id`).

## 6. Safety gate

Enam+ hook `CustomLogger.async_pre_call_hook`/`async_post_call_*` terpisah,
tiap satu = satu kebijakan spesifik, dijalankan berurutan sebelum request
diteruskan ke provider — pola persis "bertingkat: cek murah dulu" di §8.4
spec desain:

- `max_budget_limiter.py` — `_PROXY_MaxBudgetLimiter.async_pre_call_hook`
  membaca `user_api_key_dict.user_max_budget`; kalau `None`, **lolos tanpa
  cek** (fail-open by absence-of-config, bukan fail-open by design eksplisit
  — tidak ada budget diset berarti tidak ada gate). `[code]` —
  `litellm/proxy/hooks/max_budget_limiter.py` baris 19-33.
- `parallel_request_limiter.py`/`_v3.py` — RPM/TPM per key/user/team/
  end-user/model, `HTTPException` (fail-closed, request ditolak) kalau
  limit terlampaui. `[code]` — nama file + import `ProxyRateLimitError`.
- `dynamic_rate_limiter.py`/`_v3.py`, `batch_rate_limiter.py`,
  `model_max_budget_limiter.py`, `max_budget_per_session_limiter.py`,
  `max_iterations_limiter.py` — variasi limit lain (per-model budget,
  per-sesi, per-iterasi — nama terakhir relevan untuk agent yang lewat
  proxy ini, membatasi jumlah *langkah* agent, bukan cuma token/request).
  `[code]` — listing `litellm/proxy/hooks/*.py`.
- `prompt_injection_detection.py`, `sensitive_data_routing.py`,
  `responses_id_security.py` — deteksi/mitigasi di titik input & routing.
  `[code]` — listing.

Guardrail konten (bukan kuota) hidup di `litellm/proxy/guardrails/`,
diregistrasi lewat `guardrail_registry.py` — **plugin registry deklaratif**:
tiap provider guardrail (Bedrock, GraySwan, Lakera AI v1/v2, Presidio PII
masking, `ToolPermissionGuardrail`, dan puluhan lain — `aim`, `akto`,
`aporia_ai`, `azure`, `cisco_ai_defense`, `crowdstrike_aidr`, `javelin`,
`microsoft_purview`, dst, >25 direktori) diimpor dan didaftarkan sebagai
kelas `CustomGuardrail` yang diaktifkan lewat config, bukan hardcode di jalur
request. `[code]` — `litellm/proxy/guardrails/guardrail_registry.py` baris
1-38; listing `litellm/proxy/guardrails/guardrail_hooks/` (>25 entri).

## 7. Capability routing & policy

**Manifest deklaratif (config YAML/DB) yang menjalankan strategi
deterministik di kode — bukan judgment model, bukan classifier ML.** Dua
lapis:

1. **Model routing** — `routing_strategy` per `RoutingGroup` (sumbu 4) adalah
   pilihan algoritmik eksplisit (round-robin/simple-shuffle, least-busy
   berbasis counter in-flight, usage-based, latency-based dari histori
   observasi, cost-based, atau `lar1` custom) — dipilih lewat konfigurasi
   proxy (`litellm_config.yaml` / DB), dievaluasi ulang tiap request oleh
   kode router, tidak pernah diserahkan ke LLM untuk memutuskan. `[code]` —
   `litellm/router.py` baris 441-449, 700-761.
2. **Guardrail routing** — `guardrail_registry.py` memuat guardrail mana
   yang aktif dari konfigurasi (import dinamis per nama provider), lalu tiap
   guardrail konkret menjalankan pemeriksaannya sendiri (regex/PII
   detector/model klasifikasi khusus guardrail — bukan model agen utama).
   Ini pola *policy as data*: aturan (guardrail mana aktif untuk endpoint/
   key/team mana) adalah konfigurasi yang bisa diverifikasi & diaudit,
   sejalan dengan argumen `references/concepts/policy-as-data.md`. `[code]`
   — `litellm/proxy/guardrails/guardrail_registry.py`.

Tidak ada "capability routing" dalam arti pemilihan skill/persona oleh model
— LiteLLM tidak menjalankan model agen sama sekali, hanya meneruskan/
memutuskan **ke mana** panggilan model diarahkan dan **kebijakan mana**
diterapkan sebelum/sesudahnya.

## Sumber

Repo `BerriAI/litellm` dikloning shallow (`git clone --depth 1`) 2026-08-23
dan dibaca langsung sebagai file:

- `litellm/router.py` (12.489 baris total — **tidak** dibaca utuh) — baris
  yang dikutip: 131-147 (import cooldown/retry util), 416-500 (docstring
  parameter `Router.__init__`: `routing_strategy`, `routing_strategy_args`,
  `routing_groups`, `enable_weighted_failover`, `num_retries`,
  `allowed_fails`, `cooldown_time`, `disable_cooldowns`), 665-682 (default
  `num_retries`/`cooldown_time`), 700-761 (`_normalize_strategy`, cabang
  `"lar1"`), 1912-2130 (`completion`/`acompletion` — nama & signature saja)
- `litellm/proxy/schema.prisma` baris 12, 118, 234, 416, 611 (nama model
  `LiteLLM_BudgetTable`, `LiteLLM_TeamTable`, `LiteLLM_UserTable`,
  `LiteLLM_VerificationToken`, `LiteLLM_SpendLogs`)
- `litellm/proxy/hooks/max_budget_limiter.py` — utuh untuk bagian
  `async_pre_call_hook` (baris 1-40)
- `litellm/proxy/hooks/parallel_request_limiter.py` — baris 1-50 (import,
  `_response_total_tokens`, `CacheObject`)
- `litellm/proxy/guardrails/guardrail_registry.py` — baris 1-38 (import
  guardrail konkret)
- Listing direktori (nama file/folder via `find`/`ls`, isi tidak dibaca):
  `litellm/proxy/hooks/*.py` (23 file — `dynamic_rate_limiter*.py`,
  `batch_rate_limiter.py`, `max_iterations_limiter.py`,
  `model_max_budget_limiter.py`, `max_budget_per_session_limiter.py`,
  `prompt_injection_detection.py`, `sensitive_data_routing.py`,
  `responses_id_security.py`, `cache_control_check.py`),
  `litellm/proxy/guardrails/guardrail_hooks/*` (>25 subdirektori provider),
  `litellm/proxy/*_endpoints/` (>15 sub-router)

Catatan kejujuran: `router.py` adalah file 12K+ baris, hanya ~150 baris yang
benar-benar dikutip di atas — klaim soal `completion()`/`acompletion()`
dibatasi pada apa yang terlihat dari signature dan docstring parameter
`__init__`, bukan dari menelusuri seluruh alur eksekusi baris-per-baris.
Isi tiap file di `guardrail_hooks/*` (regex/model spesifik per provider)
tidak dibaca — hanya keberadaan & namanya yang dikutip sebagai bukti "plugin
registry", bukan cara kerja internal tiap guardrail.
