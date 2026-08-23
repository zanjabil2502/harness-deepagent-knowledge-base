# Arketipe AI Assistant

Peta klasifikasi. Ambil deskripsi project, jawab 6 pertanyaan di bawah, lalu
cocokkan ke salah satu (atau kombinasi) dari 7 arketipe. Tiap file arketipe
memuat konsekuensi harness yang dipaksa oleh posisi itu.

## 6 sumbu pembeda

| Sumbu | Pertanyaan |
|---|---|
| Blast radius | Menyentuh apa? mesin user / sandbox / data SaaS / dunia luar |
| Artefak | Output-nya apa? edit yang ada / bikin baru / jawaban / aksi di sistem lain |
| Horizon | Sekali jalan / satu sesi / hidup di background |
| Kendali manusia | Approve tiap langkah / review di akhir / tanpa manusia |
| Permukaan domain | General atau vertikal |
| Antarmuka | CLI / IDE / kanvas / chat / API tertanam |

Potongan utama untuk klasifikasi awal: **artefak × blast radius** — dua sumbu
ini saja sudah memisahkan 6 dari 7 arketipe.

## 7 arketipe

| # | Arketipe | Contoh | Konsekuensi harness |
|---|---|---|---|
| 1 | [Workspace Agent](01-workspace-agent.md) | Claude Code, Cursor, Aider, OpenHands | Permission gate, tool bash luas, compaction agresif, resume |
| 2 | [Generative Builder](02-generative-builder.md) | Figma Make, v0, Lovable, bolt.new | Sandbox, state = 1 artefak, iterasi cepat, persistence pendek |
| 3 | [General Task Agent](03-general-task-agent.md) | Abacus DeepAgent, Manus | Planning eksplisit, subagent, filesystem-as-memory, horizon panjang |
| 4 | [Research/Analyst](04-research-agent.md) | Deep Research, Perplexity, Elicit | Loop search→read→synthesize, budget token, wajib provenance |
| 5 | [In-App Copilot](05-in-app-copilot.md) | Notion AI, Figma AI, Agentforce | Tool = API produk, horizon pendek, undo/rollback kritis |
| 6 | [Workflow Agent](06-workflow-agent.md) | Zapier/n8n agents, cron agent | Tanpa human-in-loop → retry, idempotency, observability, kill switch |
| 7 | [Computer-Use Agent](07-computer-use-agent.md) | Operator, browser agent | Loop lihat→klik→verifikasi, tool sempit tapi dalam, paling rapuh |

## Matriks hibrida

Hibrida normal — kebanyakan produk nyata adalah gabungan dua arketipe, bukan
satu murni. Catat kombinasinya eksplisit, jangan paksa satu label.

| Sistem | Kombinasi | Kenapa |
|---|---|---|
| Cursor | 1 (Workspace) + 5 (In-App Copilot) | Edit repo lokal lewat tool bash/file (1), sekaligus chat panel yang menjawab dari index codebase tanpa mengedit apa pun (5) — dua mode kendali manusia berbeda dalam satu produk. `[inferred]` |
| Manus | 3 (General Task) + 7 (Computer-Use) | Menerima misi luas dan mendelegasikan lewat planning eksplisit (3), tapi eksekusinya lewat sandbox browser — lihat halaman, klik, verifikasi (7). `[inferred]` |
| Replit Agent | 2 (Generative Builder) + 1 (Workspace Agent) | Mulai dari kosong seperti Generative Builder (bikin app baru di sandbox), tapi begitu app berdiri, workspace-nya persisten — shell, git, dan file dari sesi ke sesi seperti Workspace Agent. `[inferred]` |

## Dimensi deployment itu ortogonal

Ketujuh arketipe di atas menjawab **"ini asisten macam apa"**. Pertanyaan
**"dilayani bagaimana"** — CLI lokal single-user vs layanan multi-user di K8s,
satu proses vs terdistribusi, sinkron vs streaming — adalah sumbu yang
berbeda dan independen. Workspace Agent bisa berupa CLI lokal (Aider) atau
layanan multi-user (Claude Code sebagai bagian dari produk terkelola);
klasifikasinya tetap arketipe 1 di kedua kasus.

`[ours]` Kami sengaja memisahkan dimensi deployment dari taksonomi arketipe
dan menaruhnya di `references/concepts/` bidang Runtime
(`serving-topology.md`, `scaling.md`). Cara vanilla yang umum dipakai
taksonomi produk AI adalah mencampur keduanya (mis. "CLI agent" vs "hosted
agent" jadi kategori sendiri) — kami menyimpang karena itu meledakkan 7
arketipe jadi puluhan varian yang sebenarnya cuma beda cara serving, bukan
beda kontrak harness.
