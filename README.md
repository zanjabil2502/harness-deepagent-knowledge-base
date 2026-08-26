# Agent Harness Engineering Knowledge Base

Knowledge base tentang rekayasa harness agent, dikemas sebagai **Claude Code
Skill**. Diberi deskripsi project apa pun — goal, output, journey,
constraint, bentuk apa pun — KB ini membantu menghasilkan tiga hal secara
berurutan:

1. **Klasifikasi arketipe** — ini AI Assistant jenis apa (dari 7 arketipe,
   bisa hibrida).
2. **Harness Blueprint** — keputusan arsitektural konkret di 7 sumbu
   (loop shape, context, tool surface, delegation, state & resume,
   guardrail, deployment & resource).
3. **Scaffold** — struktur project production-grade siap dikoding, di atas
   `deepagents`.

Ini bukan template repo yang di-`cp -r`, dan bukan tutorial `deepagents`.
Scaffold-nya adalah spesifikasi + snippet terverifikasi terhadap source;
kedalamannya ada di `references/`, `SKILL.md` cuma router tipis.

Setiap klaim di KB ini dilabeli sumbernya: `[code]` (dibaca langsung dari
source), `[docs]` (dokumentasi resmi), `[inferred]` (disimpulkan dari
perilaku produk closed-source), atau `[ours]` (keputusan desain proyek ini
sendiri, selalu menyebut alternatif vanilla-nya dan alasan menyimpang —
didaftar lengkap di
[`references/deepagents/conformance.md`](references/deepagents/conformance.md)).
Sebagian kecil `[code]` mengutip bagian lain KB ini (mis. `systems/deepagents.md`)
alih-alih source langsung — itu sah selama bagian yang dikutip *sendiri*
source-verified: `[code]` di situ berarti "transitif dari klaim yang sudah
dibaca dari source di tempat lain", bukan pelonggaran definisi. Angka di
bawah menghitung label apa adanya, termasuk sitasi transitif itu.

## Pasang

Repo ini **adalah** skill-nya: root repo = root skill, dengan `SKILL.md` di
level atas. Tidak ada langkah build, tidak ada `pip install`, dan **tidak
ada API key** — skill ini murni berkas markdown yang dibaca Claude Code.

### Cara biasa: pasang sebagai plugin

Repo ini sekaligus **marketplace** dan **plugin**-nya sendiri. Tanpa clone,
tanpa symlink — dua perintah di dalam Claude Code:

```
/plugin marketplace add zanjabil2502/harness-deepagent-knowledge-base
/plugin install agent-harness-kb@harness-deepagent-kb
```

Claude Code yang mengunduh, menempatkan, dan memperbaruinya. Untuk
mengambil versi terbaru nanti:

```
/plugin marketplace update harness-deepagent-kb
```

### Alternatif: symlink untuk yang ikut mengembangkan

Pakai ini kalau kamu mau menyunting KB-nya, bukan sekadar memakainya —
perubahan lokal langsung terpakai tanpa reinstall.

```bash
git clone https://github.com/zanjabil2502/harness-deepagent-knowledge-base.git
cd harness-deepagent-knowledge-base

mkdir -p ~/.claude/skills                              # semua project
ln -s "$(pwd)" ~/.claude/skills/agent-harness-kb
# atau, dari root satu project saja:
# mkdir -p .claude/skills && ln -s /path/ke/repo .claude/skills/agent-harness-kb
```

Jangan pasang keduanya sekaligus — skill yang sama dari dua sumber membuat
mana yang aktif jadi tidak jelas.

### Pastikan terbaca

Mulai sesi Claude Code baru, lalu minta sesuatu yang masuk salah satu dari
tiga mode di [`SKILL.md`](SKILL.md) §Tiga mode pemakaian, mis. *"apa itu
fail-deferred"* (mode mencari) atau *"aku mau bangun agent yang bisa edit
file di repo lokal, ini jenis apa"* (mode menimbang). Kalau skill-nya
aktif, jawabannya merujuk berkas di `references/`.

### Prasyarat

| Untuk | Butuh |
|---|---|
| Memakai skill | Claude Code. Itu saja. |
| Menjalankan `tools/*.py` | Python 3.10+, pustaka standar saja — tanpa `pip install` |
| Menjalankan `references/recipes/` | [`uv`](https://docs.astral.sh/uv/) (opsional, lihat di bawah) |

### Opsional: verifikasi ulang klaim `[code]`

KB ini menyitasi source `deepagents` sampai nomor baris. Untuk membuktikan
sitasi itu masih tepat, siapkan venv recipes-nya:

```bash
cd references/recipes && uv sync    # pin deepagents 0.7.8
```

Setelah venv ada, `python3 tools/check_kb.py` ikut memeriksa bahwa 53
berkas source masih identik dengan keadaan saat graf AST dibangun. Tanpa
venv, cek itu dilewati dan sisanya tetap jalan.

### Perbarui

Kalau dipasang sebagai plugin, jalankan di dalam Claude Code:

```
/plugin marketplace update harness-deepagent-kb
```

Kalau memakai symlink:

```bash
git pull
python3 tools/check_kb.py     # gerbang struktural; harus "OK: semua cek lulus"
```

## Cara memakai

Ada dua mode, dijelaskan di [`SKILL.md`](SKILL.md) §Dua mode pemakaian:
**menimbang** (berangkat dari pertanyaan atau ide yang belum berbentuk,
keluarannya keputusan beserta alasannya) dan **membangun** (berangkat dari
deskripsi project, keluarannya blueprint lalu scaffold). Contoh di bawah
menelusuri mode membangun, yang jalurnya paling panjang.

### Contoh: dari deskripsi project sampai blueprint

Misal deskripsi project: *"CLI yang jalan di repo lokal developer, bisa baca/
edit file dan menjalankan shell (test, linter, package manager), sesi bisa
berjam-jam, tiap edit/command butuh approval developer."*

**1. Isi 6 sumbu pembeda** ([`references/archetypes/README.md`](references/archetypes/README.md)):

| Sumbu | Nilai project ini |
|---|---|
| Blast radius | Mesin user (filesystem lokal + shell) |
| Artefak | Edit ke kode yang sudah ada |
| Horizon | Satu sesi, bisa berjam-jam |
| Kendali manusia | Approve per-edit/command |
| Permukaan domain | General (coding repo apa pun) |
| Antarmuka | CLI |

**2. Klasifikasi arketipe** → cocok dengan
[`references/archetypes/01-workspace-agent.md`](references/archetypes/01-workspace-agent.md)
(**Workspace Agent** — contoh nyata: Claude Code, Cursor, Aider, OpenHands).
Tidak hibrida di sini (bandingkan Cursor = 1+5 kalau ada juga IDE-panel
in-app).

**3. Baca konsekuensi harness arketipe itu** — safety gate di tiap tool call
yang mengubah state, tool surface bash luas (bukan tool sempit banyak),
compaction agresif, checkpoint level-sesi — lalu cek silang
`references/concepts/` (mis. `guardrails.md` §8.4 untuk bentuk gate,
`sandboxing.md` untuk kenapa `LocalShellBackend` di blast radius ini butuh
gate wajib, bukan opsional) dan `references/systems/` untuk sistem
sejenis (Aider, Claude Code, OpenHands).

**4. Susun Harness Blueprint** — salin
[`references/blueprint-template.md`](references/blueprint-template.md),
isi tiap section (7 sumbu, 5 lapis state, 6 titik guardrail, deployment &
resource, isolation & scoping, config `deepagents`) dengan keputusan
project ini. Untuk arketipe 01 ini berarti antara lain: `interrupt_on`
untuk tool `write_file`/`execute`, `backend=LocalShellBackend(root_dir=repo)`
dengan gate wajib (lihat D-09 di `conformance.md` untuk kenapa ini
penyimpangan yang disengaja, bukan default aman), checkpointer per sesi.

**5. Scaffold** — gabungkan
[`references/scaffolds/_base.md`](references/scaffolds/_base.md) (struktur
production-grade arketipe-agnostik) dengan delta arketipe 01
([`references/scaffolds/deltas/01-workspace-agent.md`](references/scaffolds/deltas/01-workspace-agent.md))
dan [`references/scaffolds/serving.md`](references/scaffolds/serving.md)
untuk topologi deployment.

**6. Gerbang wajib** — sebelum scaffold dianggap selesai, penuhi
**Checklist production-readiness** di
[`references/blueprint-template.md`](references/blueprint-template.md#checklist-production-readiness)
(tracing, eval harness, budget guard, retry/idempotency, context overflow
policy, secrets management, human gate + audit log, prompt/policy
versioning, kill switch & sandbox).

Blueprint yang dihasilkan tiap project sebaiknya disimpan — itu jadi bahan
kandidat T2/T3 berikutnya (lihat di bawah).

## Menambah entri tier-3 (`systems/INDEX.md`)

KB membedakan kedalaman riset per sistem lewat 3 tier (spec §10):

- **T1** — bedah dalam (`deepagents` saja).
- **T2** — grid 7 sumbu penuh, satu file `references/systems/<nama>.md`
  per sistem, memakai kerangka
  [`references/systems/_template.md`](references/systems/_template.md).
  Butuh riset dari source, bukan ringkasan.
- **T3** — indeks murah: nama + arketipe + satu baris ciri khas, tanpa
  file terpisah. Ini yang dipakai untuk menambah harness/infra baru yang
  ditemukan nanti, supaya cakupan tumbuh tanpa restrukturisasi grid.

Untuk menambah entri T3, tambahkan satu baris ke tabel **Tier 3** di
[`references/systems/INDEX.md`](references/systems/INDEX.md):

```
| <Nama> | <Arketipe, atau "Infrastruktur — ..."> | T3 | <satu baris ciri khas> | <status desain multilingual, atau "Tidak berlaku"> | `[code]`/`[docs]`/`[inferred]` |
```

Aturan:

- Jujur soal label sumber — kalau belum dibaca dari source, itu
  `[inferred]` atau `[docs]`, bukan `[code]`.
- Kolom Multilingual mencatat *apakah sistem itu punya desain eksplisit*
  pemisahan intent/ekspresi (bukan sekadar i18n string UI) — ketiadaannya
  adalah temuan yang sah untuk dicatat, bukan kolom yang boleh dikosongkan.
- Kalau riset sistem itu berkembang cukup dalam untuk mengisi grid 7 sumbu,
  promosikan ke T2: buat file baru dari `_template.md`, pindahkan barisnya
  dari tabel Tier 3 ke tabel Tier 2.

## Validator

`tools/check_kb.py` adalah gerbang struktural KB — mengecek tiap file
arketipe/concept/system punya section wajib (frame-nya masing-masing) dan
minimal satu label sumber, tidak ada link internal mati, `SKILL.md` tetap
tipis (≤150 baris), dan **tiap `[ours]` terdaftar di roster
`references/deepagents/conformance.md`** — dicek dua arah, sehingga klaim
`[ours]` baru yang belum didaftarkan maupun nomor baris roster yang sudah
basi sama-sama gagal. Jalankan dari root repo:

```bash
python3 tools/check_kb.py
```

Keluaran sukses: `OK: semua cek lulus`, exit code 0. Jalankan ini setelah
menambah atau mengedit file apa pun di `references/`, `SKILL.md`, atau
`README.md`.

## Graph source deepagents (opsional)

KB ini berisi penilaian — mana yang idiomatik, mana anti-pattern. Untuk
**kelengkapan** (apa yang ada, apa memanggil apa, apa yang kena kalau X
berubah), turunkan graph dari source-nya:

```bash
# graphify melewati apa pun di dalam .venv, jadi salin dulu ke path biasa
cp -r references/recipes/.venv/lib/python3.13/site-packages/deepagents /tmp/deepagents-src
graphify /tmp/deepagents-src
```

Korpus code-only → ekstraksi murni AST, nol token LLM, nol API key. Keluaran
di `graphify-out/` (git-ignored: ~3,7 MB, turunan, dan memuat path absolut
mesin). Regenerate setelah `deepagents` naik versi, lalu diff hasilnya untuk
melihat apa yang berubah.

Graph tidak bisa bilang mana yang **benar** — hanya mana yang **ada**.
Verdict idiomatik tetap dari `references/deepagents/conformance.md`.

Untuk mengecek dominasi label `[code]` (mayoritas klaim KB harus dibaca
dari source, bukan ditebak):

```bash
grep -roh '\[\(code\|docs\|inferred\|ours\)\]' references/ | sort | uniq -c
```

Per verifikasi terakhir (fix wave final review, 2026-08-23), dihitung dari
file `.md` yang di-track git di `references/`: `[code]` 594, `[docs]` 115,
`[inferred]` 114, `[ours]` 74 — `[code]` dominan jelas (lebih dari 2,5× label terbanyak
berikutnya). Perintah di atas (tanpa `--include`) bisa menghitung sedikit
lebih tinggi kalau `references/recipes/.venv/` ada secara lokal (dependency
terinstal untuk recipe, di-`.gitignore`, bukan bagian isi KB) — lihat
`.superpowers/sdd/2026-08-23-agent-harness-kb/task-12-report.md` untuk
angka dan perintah persisnya. Semua 5 bidang wajib di `references/concepts/`
(Cognition, Interface, Data, Runtime, Assurance) sudah dicek dan **tidak
ada bidang yang lemah** — tiap file di kelima bidang punya minimal satu
`[code]` reference (dicek per-file, bukan per-bidang, sehingga tidak ada
satu file pun yang murni tebakan).
