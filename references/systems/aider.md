# Aider

> Label tiap klaim: [code] / [docs] / [inferred]

Tier **T2**. `Aider-AI/aider`, CLI Python, single-user, tanpa BE
multi-tenant. Dipilih sebagai eksemplar **context engineering** (repo map
berbasis PageRank) sesuai kandidat T2 di spec §10.

## Arketipe

**Workspace Agent (01)** murni — CLI lokal, blast radius = working directory
repo git, artefak = edit file yang ada (bukan bikin baru dari nol), kendali
manusia granular (`confirm_ask` per aksi berisiko: shell command, file baru,
commit). `[code]` — `aider/coders/base_coder.py` (lihat sumbu 6).

## 1. Loop shape

**Bukan** ReAct tool-calling klasik. Aider historis memakai pola
"**reflection**": satu giliran user menghasilkan `run_one()` yang mengirim
pesan, lalu memeriksa `self.reflected_message` — kalau LLM/harness
menghasilkan feedback otomatis (lint gagal, test gagal, file yang disebut
belum ada di chat), pesan itu **disuntik ulang sebagai giliran baru** tanpa
input user, dibatasi `max_reflections = 3`:

```python
while message:
    self.reflected_message = None
    list(self.send_message(message))
    if not self.reflected_message:
        break
    if self.num_reflections >= self.max_reflections:
        self.io.tool_warning(f"Only {self.max_reflections} reflections allowed, stopping.")
        return
    self.num_reflections += 1
    message = self.reflected_message
```

`[code]` — `aider/coders/base_coder.py` baris 100-101, 924-944. Siapa yang
memutuskan berhenti: **harness**, lewat batas hitung `max_reflections`, bukan
model yang memanggil tool "selesai" — beda filosofi dari `deepagents`/
OpenHands yang menyerahkan momen berhenti ke tool call model dan hanya
memasang limit sebagai jaring pengaman. Sumber reflection: linter (baris
1604-1606), test runner (1620-1622), file yang disebut model tapi belum ada
di chat (1563-1566), dan error saat apply-edit (2315, 2327). `[code]` — baris
yang dikutip di `base_coder.py`.

## 2. Context

Dua mekanisme berbeda, **tidak** default bersamaan:

- **`RepoMap`** (`aider/repomap.py`) — representasi ringkas seluruh repo
  lewat *tags* (fungsi/kelas/simbol, diekstrak via tree-sitter/ctags-style),
  dirangkai jadi graph lalu diberi bobot dengan **PageRank**
  (`networkx.pagerank(G, weight="weight", **pers_args)` — `pers_args` bisa
  personalisasi rank ke arah file yang sedang aktif di chat), lalu dipotong
  ke anggaran token (`map_tokens`) lewat `get_ranked_tags_map`. Ini pola
  "context = peta struktur kode berbobot relevansi", bukan RAG embedding atau
  filesystem-as-memory. `[code]` — `aider/repomap.py` baris 42, 365-388,
  522-530, 576-710 (`get_ranked_tags`, `render_tree`, pemakaian pagerank).
- **`ChatSummary`** (`aider/history.py`) — kompaksi riwayat chat lewat LLM
  ringkas terpisah (`summarize`, `summarize_real` dengan `depth` rekursif
  untuk chunk besar, `summarize_all`). Dipanggil eksplisit saat
  `edit_format` berganti di tengah sesi (lihat sumbu 7,
  `Coder.create(summarize_from_coder=True)`), bukan dipicu otomatis oleh
  ambang token tiap giliran seperti `SummarizationMiddleware` `deepagents`.
  `[code]` — `aider/history.py` baris 7, 27, 33, 98;
  `aider/coders/base_coder.py` baris 125-165 (pemanggilan
  `from_coder.summarizer.summarize_all`).

## 3. Tool surface

**Tanpa tool-calling API model sama sekali** di jalur edit utama — Aider
meminta LLM menulis **blok edit terstruktur dalam teks respons biasa**
(format tergantung `edit_format`: unified diff, whole-file, search/replace
block, atau XML-like patch), lalu Aider **mem-parse** teks itu sendiri di
sisi klien (`aider/coders/search_replace.py`, `patch_coder.py`,
`editblock_coder.py`). Ini kontras total dengan `deepagents`/OpenHands/
LibreChat yang memakai tool-calling API provider. Shell command juga muncul
sebagai blok teks (```bash fenced block, bukan tool call), diproses lewat
`handle_shell_commands` (sumbu 6). `[code]` — nama file
`aider/coders/{search_replace,patch_coder,editblock_coder}.py`,
`aider/coders/base_coder.py` baris 2440-2480 (parsing & eksekusi shell
command dari teks).

## 4. Delegation

Ada delegasi dua-model eksplisit lewat **`ArchitectCoder`**: mode
`--architect` memisahkan model perencana (menjawab prosa, tidak mengedit
langsung) dari model editor. `ArchitectCoder.reply_completed()` — setelah
respons arsitek selesai dan (kecuali `auto_accept_architect=True`)
`confirm_ask("Edit the files?")` disetujui — membuat **instance `Coder`
baru** (`editor_coder = Coder.create(main_model=editor_model,
edit_format=self.main_model.editor_edit_format, ...)`) dan menjalankannya
sinkron: `editor_coder.run(with_message=content, preproc=False)`. Model
editor bisa berbeda dari model arsitek (`main_model.editor_model` — kombinasi
model mahal-untuk-rencana + model murah/cepat-untuk-edit adalah pola
eksplisit yang didukung). `[code]` — `aider/coders/architect_coder.py` baris
1-40.

**Hasil kembali ke pemanggil**: bukan `ToolMessage` — arsitek memanggil
`self.move_back_cur_messages("I made those changes to the files.")` setelah
`editor_coder` selesai, menyuntikkan satu pesan ringkas tetap (bukan
transkrip kerja editor) ke riwayat arsitek, plus menyerap `total_cost` dan
`aider_commit_hashes` editor ke state arsitek. `[code]` —
`aider/coders/architect_coder.py` baris 41-44 (di luar potongan yang dikutip
di atas, dikonfirmasi lewat nama method `move_back_cur_messages`).

## 5. State & resume

`done_messages` (riwayat selesai, sudah di-commit ke chat history) vs
`cur_messages` (giliran berjalan) — pemisahan dua buffer, bukan satu
transkrip flat. Saat `Coder.create()` mewarisi dari `from_coder` (dipakai di
delegasi arsitek→editor maupun switch `edit_format` biasa),
`done_messages`/`cur_messages`/`aider_commit_hashes`/`total_cost` diteruskan
eksplisit. `[code]` — `aider/coders/base_coder.py` baris 125-175 (`create`).

Tidak ada checkpointer/state-store formal (tidak seperti LangGraph di
LibreChat/`deepagents`) — persistensi lintas sesi terminal adalah **riwayat
chat di file `.aider.chat.history.md`** plus **commit git** tiap edit
(`auto_commits=True` default) sebagai catatan tahan-lama yang bisa dibaca
ulang manusia lewat `git log`, bukan lewat resume API. `[code]` —
`aider/coders/base_coder.py` baris 308-309, 409-413 (`auto_commits`,
`dirty_commits` default `True`).

## 6. Safety gate

Filosofi berbeda dari `deepagents`/OpenHands: **file edit diterapkan
otomatis lalu langsung di-commit ke git** (bukan diminta approval sebelum
eksekusi) — reversibilitas datang dari git history, bukan dari jeda
persetujuan. `check_for_dirty_commit`/`dirty_commit` mem-commit perubahan
uncommitted sebelum Aider menimpa file, supaya diff Aider selalu bisa
dipisahkan dari diff manusia sebelumnya. `[code]` —
`aider/coders/base_coder.py` baris 2175-2238, 2291, 2411-2414.

**Shell command** adalah satu-satunya aksi yang minta konfirmasi eksplisit
sebelum eksekusi, dan **fail-closed** secara sengaja:
`self.io.confirm_ask(prompt, subject="\n".join(commands),
explicit_yes_required=True, group=group, allow_never=True)` —
`explicit_yes_required=True` berarti default "Enter" tidak otomatis
menjawab ya (beda dari `confirm_ask` lain di codebase yang menerima Enter
sebagai ya). `allow_never=True` memberi opsi "jangan tanya lagi" per sesi.
`[code]` — `aider/coders/base_coder.py` baris 2449-2461. Membuat file baru
juga digerbang: `confirm_ask("Create new file?", subject=path)`. `[code]` —
baris 2207.

Tidak ada sandbox eksekusi kode — shell command jalan langsung di proses
host lewat `run_cmd()` (subprocess), tanpa isolasi tambahan; satu-satunya
mitigasi adalah gate persetujuan di atas. `[code]` —
`aider/coders/base_coder.py` baris 2465 (pemanggilan `run_cmd`).

## 7. Capability routing & policy

**Config statis, bukan classifier maupun judgment model runtime.** Pemilihan
"kemampuan" utama Aider — `edit_format` mana yang dipakai (menentukan kelas
`Coder` konkret: `EditBlockCoder`, `WholeFileCoder`, `PatchCoder`, dst,
masing-masing dengan prompt & parser sendiri) — diputuskan di
`Coder.create()` lewat urutan prioritas eksplisit: argumen `edit_format`
eksplisit → `from_coder.edit_format` (kalau sedang switch) →
`main_model.edit_format` (default per model, mis. model tertentu default ke
`"diff"` yang lain ke `"whole"`). Ini keputusan yang dibuat **sekali per
sesi/switch**, oleh kode/konfigurasi, bukan oleh model menilai tugas saat
runtime, dan bukan classifier terlatih. `[code]` —
`aider/coders/base_coder.py` baris 125-152 (`Coder.create`).

Satu-satunya delegasi "berbasis peran" (`ArchitectCoder` → editor,
sumbu 4) juga dipilih statis lewat flag `--architect` sebelum sesi mulai,
bukan diputuskan ulang tiap giliran. Ini kontras dengan
`references/concepts/skill-composition.md` dan pola `SkillsMiddleware`
`deepagents`/OpenHands (routing per-giliran berbasis deskripsi) — Aider
tidak punya mekanisme routing dinamis semacam itu di source yang dibaca.
`[inferred]` — dari tidak ditemukannya modul classifier/skill-registry di
`aider/coders/` atau `aider/` root.

## Sumber

Repo `Aider-AI/aider` dikloning shallow (`git clone --depth 1`) 2026-08-23
dan dibaca langsung sebagai file:

- `aider/coders/base_coder.py` — baris 100-175 (`max_reflections`,
  `Coder.create`), 300-415 (`auto_commits`/`dirty_commits` default),
  866-944 (`run`, `run_one`, loop reflection), 976, 1187, 1415, 1563-1622
  (`confirm_ask` untuk lint/test/file-mention), 1772, 2175-2238
  (`check_for_dirty_commit`, `dirty_commit`), 2291, 2315, 2327,
  2376-2414, 2440-2485 (`handle_shell_commands`, `confirm_ask` shell,
  `explicit_yes_required`)
- `aider/coders/architect_coder.py` — utuh (kelas `ArchitectCoder`,
  `reply_completed`, delegasi ke `editor_coder`)
- `aider/repomap.py` — baris 42, 67, 103, 177-260 (`load_tags_cache`,
  `save_tags_cache`, `tags_cache_error`), 365-388, 522-530 (pemakaian
  `networkx.pagerank`), 576-710 (`get_ranked_tags_map`, `render_tree`)
- `aider/history.py` — utuh (kelas `ChatSummary`, method `summarize`,
  `summarize_real`, `summarize_all`)
- `aider/coders/__init__.py`, listing `aider/coders/*.py` — untuk
  mengonfirmasi keluarga kelas `Coder` per `edit_format`
  (`editblock_coder.py`, `patch_coder.py`, `search_replace.py`, dst)

Catatan kejujuran: parser blok edit itu sendiri
(`search_replace.py`/`patch_coder.py`) tidak dibaca isinya secara detail —
klaim di sini terbatas pada "parsing teks, bukan tool-calling API", yang
dikonfirmasi dari struktur file dan docstring `base_coder.py`, bukan dari
membaca algoritma parsing baris-per-baris.
