# 2. Generative Builder

## Definisi

Agent yang membangun sebuah artefak **baru** (app, website, deck) dari nol
di dalam sandbox yang dimilikinya sendiri, dengan preview langsung sebagai
loop utama iterasi. State-nya adalah satu artefak versi-berseri, bukan
filesystem umum, dan persistence sandbox itu sendiri pendek — begitu sesi
selesai, artefak harus dipublish/di-export atau hilang.

Batas terhadap tetangga: beda dari **Workspace Agent** (01) karena tidak
pernah menyentuh repo/mesin user yang sudah ada — selalu mulai dari kosong
di sandbox miliknya sendiri; beda dari **Computer-Use Agent** (07) karena
ia men-generate kode/asetnya sendiri, bukan mengoperasikan UI pihak ketiga
lewat lihat-klik-verifikasi.

## Posisi di 6 sumbu

| Sumbu | Nilai |
|---|---|
| Blast radius | Sandbox milik sendiri (container/webcontainer, bukan mesin user) |
| Artefak | Bikin baru (app/web/deck dari nol) |
| Horizon | Satu sesi, satu artefak |
| Kendali manusia | Review di akhir/lewat preview interaktif, minim approval per-langkah |
| Permukaan domain | General, tapi sering dibungkus vertikal ("app builder") |
| Antarmuka | Kanvas/preview pane |

## Konsekuensi harness

1. **Sandbox wajib, bukan opsional** — kode yang dihasilkan langsung
   dieksekusi (`npm install`, dev server), dan itu tidak boleh menyentuh
   mesin atau data produksi user; blast radius harus terkurung di
   compute milik sistem sendiri.
2. **State = satu artefak versi-berseri**, bukan filesystem umum — model
   mentalnya "project" tunggal per sesi, sehingga context, undo, dan
   publish semuanya berputar di sekitar satu objek, bukan grafik file
   bebas seperti Workspace Agent.
3. **Loop shape: rewrite-penuh vs patch granular** dipilih eksplisit per
   turn — rewrite-penuh murah untuk perubahan struktural besar tapi boros
   token untuk perubahan kecil; keduanya perlu jalur tool yang berbeda.
4. **Persistence pendek by design** — sandbox ephemeral dan bisa expire;
   artefak baru jadi milik BE lewat langkah publish/export eksplisit,
   bukan hidup selamanya di compute sandbox.

## Sistem contoh

- **bolt.new** `[docs]` — dijalankan di WebContainer berbasis browser milik
  StackBlitz; model AI diberi kendali penuh atas filesystem, node server,
  package manager, terminal, dan browser console dalam satu sandbox
  in-browser. Sumber: dokumentasi bolt.new (github.com/stackblitz/bolt.new).
- **v0 (Vercel)** `[inferred]` — dari perilaku produk: preview React/Next.js
  langsung per iterasi, artefak tunggal per percakapan.
- **Lovable** `[inferred]` — dari perilaku produk: scaffold app penuh dari
  prompt, iterasi lewat chat dengan preview live.
- **Figma Make** `[inferred]` — dari perilaku produk: artefak = satu prototipe
  interaktif per sesi, preview instan.

## Jebakan khas

1. **Sandbox expire sebelum user sempat export** — kerja hilang karena
   tidak ada langkah publish/save-to-storage yang eksplisit dan terpisah
   dari siklus hidup sandbox.
2. **Rewrite-penuh untuk perubahan kecil** — boros token dan me-reset
   state UI runtime (scroll position, isi form) di tiap iterasi karena
   seluruh artefak ditulis ulang alih-alih dipatch.
3. **Preview lag atau build gagal secara diam-diam** — user tidak tahu
   iterasi terakhir rusak sampai me-refresh, karena tidak ada sinyal
   eksplisit "build gagal" yang dikembalikan ke loop percakapan.
4. **Sandbox jadi vektor abuse** (crypto miner, network egress liar) kalau
   resource dan kebijakan jaringan sandbox tidak dibatasi — blast radius
   "sandbox sendiri" tetap punya biaya nyata kalau tidak diisolasi.

## Bangun ini pakai deepagents

- **Backend**: backend keluarga sandbox — mis. `DaytonaSandbox` dari paket
  partner `langchain_daytona` (`backend = DaytonaSandbox(sandbox=..., timeout=300)`),
  atau lewat CLI deepagents dengan `agent.json`:
  `{"backend": {"type": "sandbox", "sandbox_config": {"scope": "thread",
  "policy_ids": [...]}}}`. `[code]` — sumber: `libs/partners/daytona/README.md`
  dan `libs/cli/README.md` (langchain-ai/deepagents).
- **Middleware**: `FilesystemMiddleware` default (tool `write_file`,
  `edit_file`, `execute`) berjalan di atas backend sandbox tersebut, bukan
  disk lokal — semua operasi filesystem otomatis terkurung ke sandbox.
  `[code]` — sumber: `middleware/filesystem.py`.
- **Persistence**: tanpa `checkpointer`/`store` untuk sesi pendek yang
  sengaja dibuang; kalau artefak perlu bertahan lintas thread (mis. user
  kembali besok untuk lanjut project yang sama), tambahkan `StoreBackend`
  sebagai rute durable — pilihan eksplisit, bukan default. `[code]` —
  sumber: `ARCHITECTURE.md`.
- **Safety gate**: `[ours]` interrupt minimal atau tanpa `interrupt_on`
  sama sekali untuk loop build/iterate, gate hanya dipasang di tool
  publish/deploy. Vanilla deepagents tidak memaksa HITL — default
  `interrupt_on=None` — jadi ini bukan penyimpangan dari library, tapi
  pilihan produk yang disengaja: kendali manusia arketipe ini adalah
  "review di akhir lewat preview", bukan approve tiap langkah seperti
  Workspace Agent (01).

## Sumber

- bolt.new — `[docs]` — https://github.com/stackblitz/bolt.new
- deepagents `libs/partners/daytona/README.md`, `libs/cli/README.md`,
  `middleware/filesystem.py`, `ARCHITECTURE.md` — `[code]` — Context7
  `/langchain-ai/deepagents`, https://github.com/langchain-ai/deepagents
- v0, Lovable, Figma Make — `[inferred]` — perilaku produk closed-source.
