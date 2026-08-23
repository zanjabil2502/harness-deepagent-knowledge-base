# 7. Computer-Use Agent

## Definisi

Agent yang mengoperasikan antarmuka yang **tidak dirancang untuk agent** —
browser, desktop, aplikasi pihak ketiga — lewat loop lihat (screenshot/DOM)
→ putuskan aksi → klik/ketik → verifikasi hasil. Tool surface-nya sempit
(klik, ketik, scroll, screenshot) tapi dalam, karena satu tool generik
harus menangani UI yang berubah-ubah tanpa kontrak API. Ini arketipe yang
paling rapuh: tidak ada jaminan struktural bahwa elemen yang diklik hari
ini ada di posisi yang sama besok.

Batas terhadap tetangga: beda dari **In-App Copilot** (05) karena
bertindak lewat UI, bukan API resmi produk — tidak ada kontrak yang
dijaga vendor; beda dari **Generative Builder** (02) karena tidak
men-generate artefak sendiri, ia mengoperasikan artefak/aplikasi yang
sudah ada milik pihak lain.

## Posisi di 6 sumbu

| Sumbu | Nilai |
|---|---|
| Blast radius | Dunia luar — aplikasi/situs pihak ketiga di luar kendali sistem |
| Artefak | Aksi di sistem lain, dieksekusi lewat UI (bukan API) |
| Horizon | Satu sesi tugas (urutan klik sampai tugas selesai) |
| Kendali manusia | Approve untuk aksi berisiko (submit, bayar); verifikasi visual tiap langkah |
| Permukaan domain | General (bisa situs apa pun) |
| Antarmuka | Computer-use — screenshot/DOM sebagai input, klik/ketik sebagai output |

## Konsekuensi harness

1. **Loop shape: lihat → putuskan → aksi → verifikasi**, dengan verifikasi
   sebagai step wajib terpisah — tanpa verifikasi eksplisit setelah tiap
   aksi, agent tidak tahu apakah klik tadi benar-benar mengubah state UI
   seperti yang diharapkan atau diam-diam gagal.
2. **Tool surface sempit tapi dalam** (klik-by-coordinate atau
   klik-by-selector, type, scroll, screenshot) — generalisasi ke UI
   arbitrer memaksa tool-nya sesedikit mungkin primitif, beda dari
   Workspace Agent yang punya tool bash luas untuk domain yang lebih
   terprediksi (filesystem, shell).
3. **Safety gate untuk aksi ireversibel** (submit form, bayar, kirim) —
   karena tidak ada kontrak API yang bisa di-dry-run, aksi berisiko harus
   dijeda untuk approval manusia sebelum benar-benar diklik.
4. **Retry/self-correction di level persepsi**, bukan cuma di level
   aksi — UI yang gagal dimuat, popup tak terduga, atau elemen yang
   bergeser posisi butuh agent mengenali "yang saya lihat tidak sesuai
   ekspektasi" dan mengulang observasi, bukan langsung mengulang aksi
   buta ke koordinat yang sama.

## Sistem contoh

- **browser-use** `[code]` — `Agent.run()` menjalankan loop step dengan
  `max_steps` (default 500) dan pelacakan `consecutive_failures` terhadap
  batas `max_failures` (default 5); saat batas kegagalan beruntun
  tercapai, agent dipaksa memanggil tool `done` sebagai satu-satunya tool
  yang tersedia, dan saat step budget hampir habis, sebuah pesan
  "BUDGET WARNING" disuntikkan ke context sebelum step terakhir. Ini
  mekanisme retry/self-correction di level loop yang nyata, bukan
  deskripsi produk. Sumber: `browser_use/agent/service.py`
  (github.com/browser-use/browser-use).
- **OpenAI Operator** `[inferred]` — dari perilaku produk: loop
  screenshot-then-click di browser terisolasi, meminta konfirmasi
  eksplisit sebelum aksi berisiko seperti submit pembayaran.
- **Claude computer use** `[inferred]` — dari perilaku produk: menerima
  screenshot sebagai input, mengeluarkan koordinat klik/ketik sebagai
  aksi, dijalankan di dalam sandbox virtual display.

## Jebakan khas

1. **Verifikasi dilewati demi kecepatan** — agent lanjut ke langkah
   berikutnya begitu aksi "terkirim" tanpa cek hasilnya benar-benar
   tampil di layar, sehingga error menumpuk dan baru terlihat beberapa
   langkah kemudian saat sudah sulit ditelusuri penyebabnya.
2. **UI berubah di antara observasi dan aksi** (race condition visual) —
   koordinat/selector yang valid saat screenshot diambil sudah tidak
   valid saat klik dieksekusi, karena halaman re-render atau popup
   muncul di antara dua langkah itu.
3. **CAPTCHA/anti-bot menghentikan loop tanpa sinyal jelas** — agent
   tidak tahu harus minta bantuan manusia vs terus mencoba, dan tanpa
   penanganan eksplisit, ia bisa retry buta berkali-kali ke halaman yang
   sama.
4. **Aksi ireversibel tereksekusi tanpa approval** — safety gate untuk
   submit/bayar terlewat karena disamakan dengan aksi biasa (klik tombol
   navigasi), padahal blast radius keduanya sangat berbeda.

## Bangun ini pakai deepagents

- **Tool surface**: `tools=[click_tool, type_tool, screenshot_tool, ...]`
  custom yang dipetakan ke backend automasi browser eksternal (mis.
  Playwright/CDP) — deepagents sendiri tidak menyediakan tool
  computer-use bawaan; tool-tool ini diberikan lewat parameter `tools` di
  `create_deep_agent` seperti tool kustom lainnya. `[code]` — sumber:
  signature `create_deep_agent` (`tools`), `graph.py`.
- **Safety gate**: `interrupt_on={"submit_form": True, "click": {"allowed_decisions":
  ["approve", "reject"]}}` — pola konfigurasi per-tool dengan
  `allowed_decisions` yang sama seperti dipakai di test suite deepagents
  untuk membatasi keputusan approval yang tersedia per tool. `[code]` —
  sumber: `test_hitl.py`.
- **Loop verifikasi**: `[ours]` deepagents tidak punya konsep bawaan
  "verify setelah aksi" — kami menambahkan tool `verify_state` yang wajib
  dipanggil setelah tiap tool aksi UI, ditegakkan murni lewat konvensi
  instruksi system prompt (bukan lewat middleware apa pun — deepagents
  tidak punya middleware yang menegakkan urutan pemanggilan tool).
  Vanilla `create_deep_agent` mengasumsikan tool call itu sendiri sudah
  membawa hasilnya (ToolMessage) tanpa fase verifikasi terpisah; kami
  menyimpang karena computer-use tidak punya jaminan bahwa hasil aksi =
  hasil yang terlihat. `PatchToolCallsMiddleware` (dipakai di atas untuk
  hal lain) tidak relevan di sini — perannya hanya menambal
  `ToolMessage` sintetis untuk tool call yang dangling/dibatalkan/rusak
  di riwayat pesan, bukan menegakkan urutan eksekusi tool. `[code]` —
  sumber: `libs/deepagents/deepagents/middleware/patch_tool_calls.py`.
- **Sandbox**: backend eksekusi browser idealnya berada di sandbox
  terisolasi yang sama levelnya dengan Generative Builder (02) — mis.
  di belakang backend keluarga sandbox (`DaytonaSandbox` atau setara) —
  supaya sesi browser yang crash/di-abuse tidak menyentuh compute lain.
  `[code]` — sumber: `libs/partners/daytona/README.md`.

## Sumber

- browser-use `browser_use/agent/service.py` — `[code]` —
  https://github.com/browser-use/browser-use
- deepagents `graph.py`, `test_hitl.py`, `libs/partners/daytona/README.md`,
  `middleware/patch_tool_calls.py` — `[code]` — Context7
  `/langchain-ai/deepagents`, https://github.com/langchain-ai/deepagents
- OpenAI Operator, Claude computer use — `[inferred]` — perilaku produk
  closed-source.
