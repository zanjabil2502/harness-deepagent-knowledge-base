# Delta 01 — Workspace Agent

Basis: [`../_base.md`](../_base.md). File ini **hanya** selisihnya — baca
`_base.md` dulu. Rasional lengkap tiap keputusan ada di
[`../../archetypes/01-workspace-agent.md`](../../archetypes/01-workspace-agent.md)
§Bangun ini pakai deepagents; tidak diulang di sini kecuali sebagai kutipan
pendek yang menjelaskan diff-nya.

## Ganti

- **Backend**: `StoreBackend(namespace=...)` (`_base`, durable per-user,
  tanpa `execute`) → `LocalShellBackend(root_dir=<path repo/session>,
  virtual_mode=True)`. `root_dir` di-root-kan ke direktori repo/workspace
  sesi itu, bukan namespace per-user — arketipe ini memang menyentuh
  filesystem asli satu repo, bukan store abstrak. `[code]` sumber
  `deepagents/backends/local_shell.py`, dikutip archetype 01.
- **Blast radius berubah eksplisit dari "terisolasi" ke "mesin host"** —
  `LocalShellBackend` tidak seperti `StoreBackend`, tidak punya *hook*
  scoping (`isolation-and-scoping.md`); `virtual_mode=True` cuma mengurung
  operasi file (`read_file`/`write_file`/dst) ke `root_dir`, **tidak**
  membatasi `execute()` (`../../systems/deepagents.md` §6, kutipan
  `THREAT_MODEL.md`). Kalau isolasi lebih ketat dibutuhkan, ganti lagi ke
  backend sandbox (lihat delta 02) — bukan asumsi bawaan arketipe ini.

## Tambah

- **Safety gate**: `interrupt_on={"execute": True, "write_file": True,
  "edit_file": True}` pada `create_deep_agent(...)` di
  `deepagents_orchestrator.py` — `_base` tidak memasang `interrupt_on` sama
  sekali. `[code]` pola `interrupt_on` per-tool dikutip `test_hitl.py`,
  archetype 01.
- **Isolasi multi-user di luar backend**: karena `LocalShellBackend` tidak
  punya *hook* scoping, isolasi antar user harus dibangun di lapis
  proses/container (satu proses/container per sesi user), bukan lewat
  parameter backend — beda dari `_base` yang isolasinya cukup lewat
  `namespace=` `StoreBackend`. Konsekuensi deployment: komponen ini masuk
  kandidat pisah "Tool executor" lebih dulu (lihat `../serving.md`).

## Buang

- **`StoreBackend` sebagai backend utama** — dibuang total, bukan
  dikombinasi lewat `CompositeBackend`. Tidak ada state "durable lintas
  thread" terpisah yang perlu dipertahankan di luar repo itu sendiri; repo
  git ITU SENDIRI adalah state durable-nya, di luar kendali aplikasi.
- **Delegation/subagent** — `_base` tidak memasangnya juga, jadi tidak ada
  yang dibuang secara literal, tapi dinyatakan eksplisit di sini: arketipe
  ini sengaja tetap flat. Ini **bukan** penyimpangan dari vanilla — 5 dari
  10 pemanggilan `create_deep_agent` di `examples/` repo maintainer juga
  tanpa subagent sinkron (`[code]` archetype 01, `../../deepagents/conformance.md`
  D-01). Subagent cuma ditambah kalau ada subtugas panjang yang butuh
  context terisolasi (mis. jalankan test suite besar di latar) — bukan default.
