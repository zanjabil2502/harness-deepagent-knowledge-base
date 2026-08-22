# 3. General Task Agent

## Definisi

Agent yang menerima misi luas dan open-ended ("riset lalu bangun laporan
lalu kirim email"), menyusun plan eksplisit sebelum eksekusi, mendelegasikan
subtugas ke subagent dengan context terisolasi, dan hidup lintas
sesi/hari — filesystem dipakai sebagai memory persisten, bukan cuma
context window.

Batas terhadap tetangga: beda dari **Workspace Agent** (01) karena tidak
terikat ke satu repo/tool bash — tujuannya "selesaikan misi", bukan "edit
kode ini"; beda dari **Research/Analyst** (04) karena artefak keluarannya
bisa campuran (file, aksi, jawaban), bukan cuma jawaban tertulis
bersitasi; beda dari **Computer-Use Agent** (07) karena inti harness-nya
adalah planning eksplisit + delegasi, bukan loop lihat-klik-verifikasi
(meski keduanya sering muncul bersamaan sebagai hibrida, lihat
`README.md`).

## Posisi di 6 sumbu

| Sumbu | Nilai |
|---|---|
| Blast radius | Sandbox lebar, kadang menyentuh dunia luar (browsing, tool eksternal) |
| Artefak | Campuran — jawaban, file, atau aksi, ditentukan misi |
| Horizon | Hidup di background, lintas sesi/hari |
| Kendali manusia | Review di checkpoint/akhir, jarang approve tiap langkah |
| Permukaan domain | General |
| Antarmuka | Chat + tab "activity"/proses |

## Konsekuensi harness

1. **Planning eksplisit sebagai step tersendiri** sebelum eksekusi — misi
   luas tanpa rencana tertulis membuat agent oscillate atau kehilangan
   scope di tengah jalan; plan jadi kontrak yang bisa dicek ulang.
2. **Delegation lewat subagent untuk isolasi context** — tanpa itu,
   context window utama penuh oleh detail subtugas yang tidak relevan
   untuk keputusan berikutnya; subagent membiarkan detail itu mati di
   context-nya sendiri dan hanya laporan ringkas yang naik ke pemanggil.
3. **State: filesystem-as-memory**, bukan cuma pesan di context window —
   horizon lintas sesi butuh state yang bertahan lewat restart
   proses/browser tab, bukan sesuatu yang lenyap begitu context dipangkas.
4. **Loop shape: budget step/waktu besar tapi wajib kill switch dan
   deteksi no-progress** — durasi lama berarti risiko runaway loop atau
   biaya tak terkontrol tanpa mekanisme yang mendeteksi agent berputar di
   tempat.

## Sistem contoh

- **CrewAI** `[code]` — pada `Process.hierarchical`, `Crew` memaksa
  `check_manager_llm()` (menolak jalan tanpa `manager_llm`/`manager_agent`
  terset) lalu `_create_manager_agent()` men-set `allow_delegation = True`
  pada manager dan **melarangnya punya tools sendiri** (`crew.py` melempar
  exception kalau manager diberi tools) — delegasi dipaksa terjadi lewat
  agent lain, bukan lewat manager mengerjakan sendiri. Sumber:
  `lib/crewai/src/crewai/crew.py` (github.com/crewAIInc/crewAI).
- **Manus** `[inferred]` — hibrida dengan Computer-Use Agent (07), lihat
  `README.md` matriks hibrida.
- **Abacus DeepAgent** `[inferred]` — dari perilaku produk: menerima misi
  teks bebas, menampilkan plan/todo eksplisit, dan proses berjalan di
  latar melewati satu sesi chat.

## Jebakan khas

1. **Plan ditulis sekali di awal lalu tidak pernah direvisi** — begitu
   temuan di tengah eksekusi mengubah premis awal, agent tetap mengejar
   plan basi karena tidak ada langkah replanning eksplisit.
2. **Subagent tanpa kontrak hasil yang jelas** — laporan balik dari
   subagent berupa transkrip panjang alih-alih ringkasan terstruktur,
   sehingga context pemanggil ikut membengkak — kehilangan seluruh
   manfaat isolasi context.
3. **Tidak ada deteksi oscillation/no-progress** — agent mengulang
   sekuens tool call yang sama tanpa maju, dan karena horizon-nya memang
   panjang, ini bisa berjalan lama (dan mahal) sebelum manusia sadar.
4. **Filesystem-as-memory dipakai tanpa skema** — file scratch menumpuk
   tak terstruktur lintas sesi, sehingga sesi berikutnya kesulitan
   menemukan state relevan dan agent membaca ulang segalanya dari awal.

## Bangun ini pakai deepagents

- **Planning**: `TodoListMiddleware` — berbeda dari middleware lain,
  middleware ini **tidak** ada di stack default `create_deep_agent()` dan
  harus ditambahkan eksplisit lewat parameter `middleware=[TodoListMiddleware()]`.
  `[code]` — sumber: `graph.py` (langchain-ai/deepagents).
- **Delegation**: `subagents=[{"name": ..., "description": ..., "model":
  ..., "system_prompt": ..., "tools": [...]}, ...]` diteruskan ke
  `create_deep_agent(subagents=...)`, yang membangun `SubAgentMiddleware`
  dan tool `task` untuk memanggilnya. `[code]` — sumber:
  `middleware/subagents.py`, contoh `examples/content-builder-agent/README.md`.
- **State & memory**: `backend` bertipe `store` (`StoreBackend`, durable
  lintas thread) untuk file yang harus hidup lintas sesi, dikombinasikan
  dengan `memory=["./AGENTS.md"]` untuk konteks persisten yang dimuat ke
  system prompt tiap sesi. `[code]` — sumber: `ARCHITECTURE.md`,
  `examples/content-builder-agent/README.md`.
- **Loop budget & kill switch**: `[ours]` deepagents tidak memberi
  "no-progress detector" bawaan — yang tersedia hanya `recursion_limit`
  generik dari LangGraph dan `interrupt_on` per tool. Kami menyimpang
  dengan menambah middleware kustom (deteksi tool-call berulang identik
  N kali berturut-turut → paksa berhenti) karena vanilla stack cukup
  untuk mencegah loop tak berhenti secara sintaksis (recursion limit),
  tapi tidak cukup untuk mendeteksi agent yang secara semantik berputar
  di tempat.

## Sumber

- CrewAI `lib/crewai/src/crewai/crew.py` — `[code]` —
  https://github.com/crewAIInc/crewAI
- deepagents `graph.py`, `middleware/subagents.py`, `ARCHITECTURE.md`,
  `examples/content-builder-agent/README.md` — `[code]` — Context7
  `/langchain-ai/deepagents`, https://github.com/langchain-ai/deepagents
- Manus, Abacus DeepAgent — `[inferred]` — perilaku produk closed-source.
