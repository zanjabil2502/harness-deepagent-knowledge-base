# browser-use

> Label tiap klaim: [code] / [docs] / [inferred]

Tier **T2**. `browser-use/browser-use`, library Python untuk agent yang
mengontrol browser lewat CDP (screenshot + DOM). Dipilih sebagai eksemplar
**computer-use** sesuai kandidat T2 spec §10.

## Arketipe

**Computer-Use Agent (07)** murni: loop lihat→klik→verifikasi, tool sempit
tapi dalam (27 action terdaftar, lihat sumbu 3), paling rapuh terhadap
konten halaman tak terpercaya (lihat sumbu 6, `sensitive_data`). `[code]` —
`browser_use/tools/service.py` (jumlah `@self.registry.action(...)`
dikonfirmasi via grep = 27).

## 1. Loop shape

Loop-until-done dengan **dua batas independen**, bukan satu: `max_steps`
(default **500**, diteruskan ke `Agent.run(max_steps=500)`) dan
`max_failures` (default **5**, dihitung sebagai `consecutive_failures` —
kegagalan **berturut-turut**, bukan total). Kalau `consecutive_failures >=
max_failures`, loop berhenti sepenuhnya (bukan hanya memaksa `done`):
*"Stopping due to {max_failures} consecutive failures"*. `[code]` —
`browser_use/agent/service.py` baris 171 (`max_failures: int = 5`), 2508
(`max_steps: int = 500`), 2603-2617 (`while self.state.n_steps <=
max_steps`, cek `consecutive_failures`).

Satu giliran (`Agent.step()`) adalah **tiga fase eksplisit**: `_prepare_context`
(ambil screenshot + ringkasan state browser — *"Always take screenshots for
all steps"*, plus jeda khusus `wait_if_captcha_solving()` sebelum context
disiapkan) → `_get_next_action` (panggil LLM) → `_execute_actions` →
`_post_process`, dibungkus `try/except`/`finally` tunggal
(`_handle_step_error`/`_finalize`) supaya satu step gagal tidak
mengotori state step berikutnya. `[code]` — `browser_use/agent/service.py`
baris 1029-1090 (`step()`, `_prepare_context` awal).

Saat `max_steps` tercapai, harness **tidak** membiarkan model memanggil tool
lain: *"You reached max_steps - this is your last step. Your only tool
available is the 'done' tool. No other tool is available."* — dipaksa lewat
prompt injection di langkah terakhir, plus ada peringatan anggaran
(`budget_ratio = steps_used / max_steps`) yang disuntik ke prompt sebelum
batas tercapai. `[code]` — `browser_use/agent/service.py` baris 1542-1566.

## 2. Context

Tidak ada condenser/summarizer riwayat pesan yang ditemukan di
`agent/service.py`. Sebaliknya, state kerja jangka-panjang dipindah ke
**filesystem virtual** (`browser_use/filesystem/file_system.py`) — agent
menulis/membaca file (mis. catatan progres, hasil ekstraksi) lewat tool
filesystem, bukan menyimpan semuanya di riwayat pesan. Modul ini juga
mem-blokir ekstensi biner (`UNSUPPORTED_BINARY_EXTENSIONS` — png/jpg/mp4/
zip/exe/dll/dst) dari ditulis lewat tool file-write, membatasi tool
filesystem ke konten teks. `[code]` — `browser_use/filesystem/file_system.py`
baris 1-40.

## 3. Tool surface

**Sedikit tool, sempit tapi dalam** — persis pola yang diprediksi archetype
07: `Tools.registry` (`browser_use/tools/service.py`) mendaftarkan **27**
action lewat decorator `@self.registry.action("<deskripsi>")`, di antaranya
`go_back`, `wait` (tunggu N detik), `find_text`/scroll-to-text (dikonfirmasi
lewat nama fungsi `find_text` dan deskripsi *"Scroll to text."*) — action
lain (klik-by-index, input-text, ekstraksi konten) ada di modul yang sama
tapi tidak semua nama fungsi terverifikasi lewat grep. `[code]` —
`browser_use/tools/service.py` (hitung decorator via grep = 27; 3 nama
fungsi dikonfirmasi langsung: `go_back`, `wait`, `find_text`).

## 4. Delegation

Tidak ditemukan mekanisme subagent/task-tool di `agent/service.py` (4166
baris, dibaca sebagian) — arsitektur flat: satu `Agent` mengontrol satu
`browser_session`. `[inferred]` — dari tidak ditemukannya import
subagent/delegation di bagian file yang dibaca.

## 5. State & resume

`filesystem/file_system.py` (sumbu 2) berperan ganda sebagai state
scratchpad. `AgentHistory` (`self.history.save_to_file(file_path,
sensitive_data=self.sensitive_data)`) — riwayat langkah bisa disimpan ke
file, dengan `sensitive_data` **disaring saat serialisasi** (tidak
diklaim apakah disensor sepenuhnya atau ditandai — hanya dikonfirmasi
parameter itu diteruskan). `[code]` — `browser_use/agent/service.py` baris
3918.

`browser_use/sandbox/sandbox.py` — modul terpisah untuk isolasi (nama
dikonfirmasi lewat listing, isi tidak dibaca) menunjukkan ada jalur
menjalankan browser session di sandbox/cloud terisolasi, bukan cuma browser
lokal — konsisten dengan blast radius "dunia luar" (agent ini menyentuh web
publik, isolasi proses/browser jadi penting). `[code]` (listing) /
`[inferred]` (cakupan isolasi persis).

## 6. Safety gate

Tidak ada gate approval per-aksi (klik/scroll/navigate berjalan otomatis
tanpa jeda manusia) — mitigasi utama adalah **`sensitive_data` terskop
domain** + **peringatan eksplisit saat konfigurasi berbahaya terdeteksi
saat startup**:

```
⚠️ Agent(sensitive_data=••••••••) was provided but Browser(allowed_domains=[...])
is not locked down! ⚠️
☠️ If the agent visits a malicious website and encounters a prompt-injection
attack, your sensitive_data may be exposed!
```

Kredensial di `sensitive_data` bisa berupa dict per-domain
(`has_domain_specific_credentials = any(isinstance(v, dict) for v in
self.sensitive_data.values())`); kalau domain pattern di `sensitive_data`
tidak tercakup pola apa pun di `Browser(allowed_domains=[...])`, harness
memperingatkan lagi secara terpisah. Ini bukan gate yang memblokir eksekusi
(agent tetap jalan setelah warning) — murni pesan log fail-open, tapi
eksplisit menandai kelas serangan (prompt injection dari konten halaman →
eksfiltrasi credential) yang relevan untuk `references/concepts/security.md`
dan `guardrails.md`. `[code]` — `browser_use/agent/service.py` baris
150, 385, 532-577.

## 7. Capability routing & policy

**Tidak ada routing internal antar mode/skill** — browser-use melakukan
satu hal (kontrol browser), tidak punya sistem skill/subagent yang
dipilihkan model. Yang menarik: browser-use **membungkus dirinya sendiri**
sebagai skill format Anthropic (SKILL.md) untuk **dikonsumsi** harness lain
— `browser_use/skills/browser_use.py` menghasilkan teks skill
(`skill_text`) dengan metadata instalasi (`"openclaw": {"requires": {"bins":
["browser-use"]}, "install": [{"kind": "uv", "package": "browser-use", ...}]}`)
yang disinkronkan ke file `SKILL.md` lewat skrip
`scripts/sync_browser_harness_skill.py`. Artinya: capability routing untuk
browser-use terjadi **di harness pemanggilnya** (mis. deepagents/Claude
Code/OpenHands memilih kapan memuat skill "Browser Use" lewat judgment
model atas deskripsi skill itu), bukan di dalam browser-use sendiri.
`[code]` — `browser_use/skills/browser_use.py` baris 1-30 (docstring +
`OPENCLAW_METADATA_LINES`), `browser_use/skills/__init__.py`.

## Sumber

Repo `browser-use/browser-use` dikloning shallow (`git clone --depth 1`)
2026-08-23 dan dibaca langsung sebagai file:

- `browser_use/agent/service.py` (4166 baris total — **tidak** dibaca
  utuh) — baris yang dikutip: 133 (kelas `Agent`), 150, 171, 385
  (parameter `sensitive_data`, `max_failures`), 397, 532-577 (peringatan
  domain-lock), 786, 1029-1090 (`step()`, tiga fase), 1291,
  1542-1582 (`max_steps` budget warning & force-done), 2183-2248
  (`take_step`), 2444-2471, 2506-2627 (`run()`, loop utama, batas
  `consecutive_failures`), 3918 (`history.save_to_file`), 4066-4073
- `browser_use/filesystem/file_system.py` — baris 1-40
  (`UNSUPPORTED_BINARY_EXTENSIONS`, import)
- `browser_use/tools/service.py` — hitung decorator `@self.registry.action(`
  via `grep -c` = 27; nama fungsi `go_back`, `wait`, `find_text`
  dikonfirmasi via `grep -A1`
- `browser_use/skills/__init__.py`, `browser_use/skills/browser_use.py` —
  baris 1-30
- Listing direktori (nama file/folder, isi tak dibaca): `browser_use/sandbox/
  sandbox.py`, `browser_use/controller/`, `browser_use/mcp/`,
  `browser_use/beta/`, `browser_use/actor/`

Catatan kejujuran: `agent/service.py` adalah file 4166 baris, mayoritas
tidak dibaca — klaim di file ini dibatasi pada baris yang benar-benar
dikutip. Daftar lengkap 27 action di `tools/service.py` **tidak**
diverifikasi satu-satu (hanya 3 nama fungsi dikonfirmasi); klaim "tool
sempit tapi dalam" bertumpu pada jumlah total (27) dan pola nama yang
terlihat, bukan audit fungsi tiap action. `browser_use/sandbox/sandbox.py`
disebut lewat listing saja, mekanisme isolasi persis tidak diverifikasi.
