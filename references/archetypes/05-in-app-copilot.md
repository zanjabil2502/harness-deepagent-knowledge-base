# 5. In-App Copilot

## Definisi

Agent yang hidup **di dalam** satu produk dan hanya boleh bertindak lewat
API produk itu sendiri (tag, resolve, sisipkan blok, ubah cell) — tool
surface-nya sengaja sempit karena dibatasi domain aplikasi tuan rumah.
Horizon-nya pendek (satu percakapan/dokumen/tiket), dan karena aksinya
langsung terlihat di UI produk yang sama, undo/rollback jadi kritis: gagal
mengoreksi lebih mahal di sini daripada di arketipe lain.

Batas terhadap tetangga: beda dari **Workspace Agent** (01) karena tool
surface-nya adalah API produk yang sempit, bukan shell/filesystem
generik; beda dari **Workflow Agent** (06) karena selalu ada manusia yang
sedang aktif memakai aplikasi saat copilot bertindak, bukan berjalan tanpa
pengawasan di latar.

## Posisi di 6 sumbu

| Sumbu | Nilai |
|---|---|
| Blast radius | Data SaaS milik produk tuan rumah (dokumen, tiket, board) |
| Artefak | Aksi di sistem lain (produk itu sendiri) atau edit konten in-place |
| Horizon | Pendek — satu percakapan/dokumen/tiket |
| Kendali manusia | Draft/saran untuk direview, atau undo cepat setelah aksi |
| Permukaan domain | Vertikal — terikat ke satu produk |
| Antarmuka | API tertanam di dalam UI produk (panel, inline suggestion) |

## Konsekuensi harness

1. **Tool = API produk, bukan tool generik** — setiap tool yang diekspos
   ke agent harus dipetakan 1:1 ke endpoint/aksi resmi produk, karena
   blast radius dibatasi domain produk itu sendiri secara sengaja.
2. **Undo/rollback adalah safety gate utama**, bukan approval sebelum
   aksi — banyak in-app copilot memilih UX "draft dulu, kirim belakangan"
   atau "aksi instan tapi gampang di-undo" karena approval per-langkah
   akan mematikan kecepatan yang jadi alasan produk ini ada.
3. **Horizon pendek memaksa context assembly cepat** — tidak ada waktu
   untuk riset panjang; context yang relevan (dokumen aktif, tiket
   terkait) harus sudah tersedia dari state aplikasi tuan rumah, bukan
   dikumpulkan lewat loop pencarian sendiri.
4. **State: sebagian besar milik aplikasi tuan rumah, bukan agent** —
   agent tidak boleh menyimpan salinan state produk sebagai sumber
   kebenaran sendiri; ia membaca dan menulis lewat API produk supaya
   tidak ada dua sumber kebenaran yang bisa divergen.

## Sistem contoh

- **Chatwoot Captain (Copilot)** `[docs]` — menyusun draft balasan
  berdasar context percakapan yang bisa "diperbaiki" (improve/translate)
  sebelum dikirim manusia; juga meringkas percakapan dan menarik data
  historis pelanggan. Fokusnya pada saran untuk agent manusia di dalam
  satu percakapan, bukan aksi otonom di backend tiket. Sumber:
  chatwoot.com/captain.
- **Notion AI** `[inferred]` — dari perilaku produk: menulis/mengedit
  blok in-place di dalam dokumen yang sedang dibuka, undo lewat Ctrl+Z
  standar Notion.
- **Figma AI** `[inferred]` — dari perilaku produk: aksi terbatas ke layer
  dan komponen di file yang sedang dibuka, tidak menyentuh file lain.
- **Salesforce Agentforce** `[inferred]` — dari perilaku produk: aksi
  dijalankan lewat objek/API Salesforce (update record, kirim email),
  bukan tool bebas.

## Jebakan khas

1. **Tool API produk terlalu luas** (mis. "update record apa pun") alih-alih
   discoped ke objek yang sedang aktif — blast radius diam-diam melebar
   dari "dokumen ini" jadi "seluruh workspace" tanpa disadari user.
2. **Tidak ada jalur undo untuk aksi tertentu** — begitu suatu aksi
   dieksekusi (kirim email, hapus baris), tidak ada rollback native produk
   untuk itu, padahal safety gate arketipe ini bertumpu pada undo, bukan
   approval di muka.
3. **Context assembly memakai state basi** — copilot membaca snapshot
   dokumen/tiket dari awal sesi, lalu menulis balik tanpa cek apakah
   sudah berubah karena kolaborator lain — hasilnya overwrite silent.
4. **Draft yang "terlalu percaya diri"** dikirim otomatis tanpa jeda
   review karena UX terlalu mengoptimalkan kecepatan — kegagalan
   arketipe ini paling sering terjadi tepat di titik trade-off
   kecepatan-vs-review ini.

## Bangun ini pakai deepagents

- **Tool surface**: `tools=[...]` custom di `create_deep_agent`, bukan
  `FilesystemMiddleware` bawaan — tiap tool adalah wrapper tipis ke satu
  endpoint API produk tuan rumah, dipetakan manual. Filesystem/bash
  bawaan deepagents tidak relevan di arketipe ini kecuali dimatikan lewat
  `permissions`. `[code]` — sumber: signature `create_deep_agent` (`tools`,
  `permissions`), `graph.py`.
- **Safety gate**: `[ours]` bukan `interrupt_on` per tool call (itu pola
  Workspace Agent), tapi tool `undo_<aksi>` eksplisit yang dipasangkan ke
  tiap tool aksi produk, dipanggil dari UI host, bukan dari loop agent.
  Vanilla `HumanInTheLoopMiddleware` deepagents dirancang untuk
  approve/edit/reject **sebelum** eksekusi; kami menyimpang ke pola
  "aksi dulu, undo tersedia" karena horizon pendek arketipe ini membuat
  jeda approval terasa sebagai regresi UX dibanding produk tuan rumah
  yang sudah cepat.
- **Context**: tidak pakai `memory=[...]` lintas sesi bawaan deepagents;
  context datang dari state aplikasi tuan rumah yang disuntikkan ke
  `system_prompt`/`context_schema` per panggilan, karena horizon pendek
  berarti tidak ada memory lintas dokumen yang perlu dipertahankan agent.
  `[code]` — parameter `context_schema` ada di signature
  `create_deep_agent`.
- **Backend/state**: cukup `StateBackend` default (thread-scoped, tidak
  durable) — tidak butuh `StoreBackend`/filesystem durable karena tidak
  ada artefak file yang perlu bertahan; sumber kebenaran tetap di produk
  tuan rumah. `[code]` — sumber: `ARCHITECTURE.md`.

## Sumber

- Chatwoot Captain — `[docs]` — https://www.chatwoot.com/captain
- deepagents `graph.py`, `ARCHITECTURE.md` — `[code]` — Context7
  `/langchain-ai/deepagents`, https://github.com/langchain-ai/deepagents
- Notion AI, Figma AI, Salesforce Agentforce — `[inferred]` — perilaku
  produk closed-source.
