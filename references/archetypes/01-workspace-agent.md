# 1. Workspace Agent

## Definisi

Agent yang beroperasi langsung di atas filesystem/repo milik user, dengan
tool bash yang relatif tak-terbatas, untuk mengedit artefak yang **sudah
ada**. Sesi biasanya berjam-jam, terikat ke satu proyek/repo lokal, dan
kendali manusia terjadi lewat approval per-edit atau review per-commit —
bukan lewat sandbox yang bisa dibuang begitu saja.

Batas terhadap tetangga: beda dari **General Task Agent** (03) karena
lingkupnya satu repo/mesin, bukan misi luas lintas sistem; beda dari
**Generative Builder** (02) karena artefaknya adalah kode yang sudah ada
(edit), bukan proyek baru dari nol di sandbox sekali pakai; beda dari
**In-App Copilot** (05) karena tool surface-nya adalah shell/filesystem
generik, bukan API sempit satu produk.

## Posisi di 6 sumbu

| Sumbu | Nilai |
|---|---|
| Blast radius | Mesin user (filesystem lokal, sering shell penuh) |
| Artefak | Edit ke kode/konten yang sudah ada |
| Horizon | Satu sesi (bisa berjam-jam, kadang resumable lintas sesi) |
| Kendali manusia | Approve per-edit/command, atau review per-commit |
| Permukaan domain | General (coding, repo apa pun) |
| Antarmuka | CLI atau IDE |

## Konsekuensi harness

1. **Safety gate wajib di tiap tool call yang mengubah state** (file write,
   shell exec) — blast radius = mesin user berarti kesalahan tidak
   ter-undo lewat UI, beda dengan sandbox yang tinggal dibuang.
2. **Tool surface: bash luas, bukan banyak tool sempit** — tugas coding
   butuh command arbitrer (test runner, package manager, linter) yang
   tidak bisa dienumerasi di muka sebagai tool terpisah-pisah.
3. **Context: compaction/summarization agresif** — sesi berjam-jam
   menyentuh banyak file besar, context window habis lebih cepat daripada
   task selesai kalau tidak dipangkas/diringkas berkelanjutan.
4. **State & resume: checkpoint di level sesi** — sesi coding sering
   terputus (jaringan, laptop tidur, crash), harus bisa lanjut dari state
   terakhir tanpa mengulang eksplorasi repo dari nol.
5. **Delegation minim/flat** — sebagian besar tugas satu repo tidak butuh
   subagent; delegasi baru relevan saat ada subtugas yang butuh context
   window terisolasi (mis. jalankan test suite panjang di latar).

## Sistem contoh

- **Aider** `[code]` — `GitRepo.commit()` mengimplementasikan logika
  atribusi commit yang bercabang berdasar flag `aider_edits`: kalau
  perubahan berasal dari Aider, author/committer commit ditandai beda
  dari commit yang ditulis manusia, bukan cuma "auto-commit" generik.
  Sumber: `aider/repo.py` (github.com/Aider-AI/aider).
- **Cline** `[docs]` — punya dua mode eksplisit: Plan (eksplorasi repo,
  tanya klarifikasi, susun strategi) dan Act (eksekusi). Setiap file edit
  dan command terminal butuh approval user secara default, dengan opsi
  toggle auto-approve untuk jalan otonom. Sumber: github.com/cline/cline.
- **OpenHands** `[docs]` — menyediakan mode sandbox Docker untuk
  penggunaan lokal ("Docker sandbox mode for laptop usage"), dengan opsi
  memberi agent akses penuh ke filesystem user bila sandbox dimatikan.
  Sumber: github.com/All-Hands-AI/OpenHands.
- **Claude Code** `[inferred]` — dari perilaku produk: permission gate per
  tool (edit/bash/lain-lain) dengan mode "auto-accept" opsional, dan
  kemampuan resume sesi dari riwayat lokal.
- **Cursor** `[inferred]` — hibrida dengan In-App Copilot (05), lihat
  `README.md` matriks hibrida.

## Jebakan khas

1. **Auto-approve di mode headless/CI** menghapus atau menimpa file
   penting tanpa jejak undo — tool bash generik yang di-auto-approve punya
   blast radius mesin user penuh, tidak ada sandbox yang menahan kerusakan.
2. **Context penuh karena file besar dibaca utuh** alih-alih lewat
   ringkasan/repo-map — sesi crash atau kena context-limit sebelum task
   selesai, terutama di repo besar.
3. **Shell tool tanpa scoping/allowlist** — command destruktif (`rm -rf`,
   `git push --force`) tereksekusi karena tool bash generik tidak
   membedakan command aman vs berbahaya di titik penegakan.
4. **Sesi terputus tanpa checkpoint** — kerja berjam-jam hilang total,
   user harus menjelaskan ulang context dari nol karena tidak ada state
   sesi yang bisa di-resume.

## Bangun ini pakai deepagents

- **Backend**: `LocalShellBackend` (extends filesystem backend dengan
  `execute` lewat `subprocess.run(shell=True)`) di-root-kan ke direktori
  repo, atau `FilesystemBackend(root_dir=...)` bila `execute` tidak
  dibutuhkan. `[code]` — sumber: `libs/deepagents/deepagents/backends/local_shell.py`,
  dikutip THREAT_MODEL.md (langchain-ai/deepagents).
- **Middleware inti**: `FilesystemMiddleware` (default, meregistrasi `ls`,
  `read_file`, `write_file`, `edit_file`, `delete`, `glob`, `grep`,
  `execute`) + `SummarizationMiddleware` bawaan `create_deep_agent()` untuk
  compaction otomatis. `[code]` — sumber: `graph.py`
  (langchain-ai/deepagents).
- **Safety gate**: `interrupt_on={"execute": True, "write_file": True,
  "edit_file": True}` lewat parameter `interrupt_on` di
  `create_deep_agent`, memakai `HumanInTheLoopMiddleware`. Bentuk
  konfigurasi tool-per-tool (boolean atau dict `allowed_decisions`) sesuai
  pola yang diuji di `test_hitl.py`. `[code]`.
- **State & resume**: `checkpointer=<Postgres checkpointer milik
  aplikasi>` lewat parameter `checkpointer` — deepagents tidak membuat
  checkpointer sendiri, aplikasi yang menyuntikkannya. `[code]` — sumber:
  `ARCHITECTURE.md` (langchain-ai/deepagents).
- **Subagent**: tidak dipakai sebagai default. `[ours]` Vanilla contoh
  deepagents (`content-builder-agent`, `deep_research`) hampir selalu
  menyertakan minimal satu subagent. Kami menyimpang untuk arketipe ini
  karena unit kerjanya (satu repo, satu sesi) jarang butuh isolasi
  context lintas subtugas; tambahkan `SubAgentMiddleware` hanya kalau ada
  subtugas panjang yang perlu context terpisah (mis. jalankan & analisis
  test suite besar di latar).

## Sumber

- Aider `aider/repo.py` — `[code]` — https://github.com/Aider-AI/aider
- Cline README — `[docs]` — https://github.com/cline/cline
- OpenHands README — `[docs]` — https://github.com/All-Hands-AI/OpenHands
- deepagents `graph.py`, `THREAT_MODEL.md`, `ARCHITECTURE.md` — `[code]` —
  Context7 `/langchain-ai/deepagents`, https://github.com/langchain-ai/deepagents
- Claude Code, Cursor — `[inferred]` — perilaku produk closed-source, belum ada
  akses source untuk dikutip sebagai `[code]`.
