# Resource profiling

## Masalah

Instinct default untuk men-deploy agent harness adalah instinct web app biasa:
satu container, satu resource request (`cpu: 1, memory: 2Gi`), satu HPA yang
melihat CPU rata-rata. Instinct itu diam-diam mengasumsikan satu hal yang
salah untuk agent: bahwa satu unit kerja (satu turn) itu homogen — dominan
CPU, atau dominan IO, tapi bukan dua-duanya sekaligus.

Satu turn agent bukan itu. Di dalam satu turn yang sama, beberapa fase
berjalan berurutan dengan **profil resource yang berlawanan**: fase yang
menghabiskan detik paling banyak (menunggu LLM) nyaris tidak memakai CPU,
sementara fase yang paling singkat (eksekusi kode) bisa memenuhi 100% satu
core. Kalau kelima fase ini dikolokasi di satu pod dan pod itu diberi satu
resource request/limit, request itu harus dipatok ke **dimensi terburuk**
(puncak CPU eksekusi kode) — padahal dimensi itu cuma aktif sebagian kecil
dari waktu hidup turn. Sisa waktunya, alokasi itu menganggur.

## Pola

### Lima fase, empat bound berbeda

| Fase | Bound | Yang terjadi | CPU | Memory | Network IO | Disk IO | GPU |
|---|---|---|---|---|---|---|---|
| LLM call | **IO** | Kirim prompt, tunggu/stream token dari provider lewat socket | Nyaris 0 — thread/coroutine diam menunggu bit datang dari jaringan | Rendah (buffer streaming) | Tinggi — durasi terpanjang di turn | - | - |
| Context assembly | **Memory** | Susun ulang transcript + hasil tool + memory jadi satu prompt string dari nol tiap call (lihat `session-state.md`) | Burst singkat (formatting/serialize) | Sebanding ukuran context window terpakai — window besar × banyak turn concurrent = RAM besar | Rendah | - | - |
| Code exec (`execute`) | **CPU** + butuh isolasi | Compile/jalankan kode yang ditulis LLM | Bisa 100% satu atau lebih core selama durasi eksekusi | Sedang-tinggi tergantung workload | - | Bisa tinggi (build artifact) | - |
| Embedding (retrieval) | **GPU** (atau CPU kalau model kecil) | Encode query/dokumen jadi vector, biasanya batched | Rendah di host CPU | Sedang (batch buffer) | - | - | Tinggi |
| Checkpoint write | **IO disk** | `checkpointer.aput` tiap step graph ke Postgres | Nyaris 0 | Rendah | Sedang | Tulis ke DB — commit-bound, bukan compute-bound | - |

Empat bound berbeda (IO jaringan, memory, CPU, GPU) plus satu bound IO-disk
terpisah — lima fase yang tidak bisa direduksi jadi satu angka "resource
usage" tunggal per turn.

### Kenapa kolokasi memaksa scaling di dimensi terburuk — dihitung, bukan diasumsikan

Misal satu turn ilustratif berdurasi total ~20 detik: LLM call ~15s (75%),
code exec ~3s (15%), context assembly + embedding + checkpoint sisanya
(~10%). Selama 15 detik LLM call, CPU pod itu praktis menganggur — thread
menunggu socket, bukan menghitung. Selama 3 detik code exec, CPU bisa
tersaturasi penuh di satu atau lebih core.

Kalau satu pod menjalankan kelima fase ini dan resource request pod
dipatok untuk menutupi puncak code exec (misal `cpu: 2`), maka untuk 85%
dari waktu hidup turn itu, 2 CPU yang dialokasikan (dan dibayar) itu
menganggur >80%. Kalikan dengan concurrency: 100 turn paralel di pod yang
sama berarti 200 vCPU dialokasikan untuk menutupi puncak yang cuma aktif
serentak di sebagian kecil dari 100 turn itu di waktu mana pun — sisanya
idle capacity yang tetap harus disediakan (dan dibayar) karena autoscaler
tidak bisa membedakan "pod ini sedang CPU-bound" dari "pod ini sedang
IO-wait" kalau sinyalnya cuma CPU-utilization rata-rata satu pod.

Konsekuensi kedua, lebih halus: kalau HPA pod ini di-scale berdasar
**CPU utilization** (default HPA metric paling umum), fase code exec-lah
yang men-trigger scale-out — bukan karena orchestrator kekurangan kapasitas
menangani lebih banyak turn (mayoritas waktunya IO-wait, satu pod bisa
menahan ratusan turn concurrent secara async tanpa CPU tambahan), tapi
karena tool executor yang numpang di pod yang sama sedang sibuk. Scale-out
menambah **seluruh pod** — termasuk kapasitas LLM-wait yang tidak
dibutuhkan — padahal yang sebenarnya kurang cuma kapasitas eksekusi kode.
Ini argumen inti kenapa `serving-topology.md` memisahkan sinyal HPA per
komponen alih-alih satu sinyal CPU untuk semuanya.

### Mengukur dominasi fase di deployment nyata

Contoh di atas ilustratif — angka sungguhan berbeda per workload
(system prompt besar vs kecil, tool call berat vs ringan), jadi yang
dibutuhkan bukan tabel di atas dipercaya mentah-mentah, tapi cara
mengukurnya sendiri. Instrumentasi termurah: catat **span** (timestamp
mulai + selesai) di tiap batas fase yang sudah ada di kode — bentuknya
sama seperti yang sudah dipakai `tool_calls.started_at`/`completed_at`
di `persistence-schema.md` (Task 4), diperluas ke fase lain yang belum
punya baris tabel sendiri: `context_assembly_start`/`_end` (sebelum vs
sesudah prompt dirakit, sebelum dikirim ke model),
`llm_call_start`/`_end` (kirim request vs response/stream selesai),
`checkpoint_write_start`/`_end` (sebelum vs sesudah `checkpointer.aput`).
Emit tiap span sebagai metric berdurasi (mis. histogram Prometheus
per-fase, label `phase=`), lalu baca hasilnya dengan cara yang sama
seperti membaca breakdown di atas: jumlah durasi tiap `phase` dibagi
total durasi turn memberi **porsi waktu** per fase; disandingkan dengan
CPU-seconds pod yang tersampel selama window span yang sama (metric
container standar, mis. `container_cpu_usage_seconds_total` dari
cAdvisor/kube-state-metrics) memberi porsi **kerja CPU** per fase — dua
angka yang berbeda dan keduanya dibutuhkan, karena fase yang makan waktu
paling lama (LLM call) belum tentu fase yang makan CPU paling banyak
(code exec). Fase dengan porsi waktu besar tapi CPU kecil adalah kandidat
IO/memory-bound (harus di-scale lewat concurrency, `serving-topology.md`);
fase dengan porsi CPU besar meski waktunya singkat adalah kandidat yang
harus dipisah ke komponen tersendiri (Tool executor) supaya tidak
menyeret seluruh pod ikut scale-out.

## Trade-off

- **Kolokasi (satu pod, semua fase) vs pisah per bound** `[ours]` —
  vanilla-nya salah satu dari dua ekstrem: kolokasi penuh (satu
  deployable, tanpa network hop antar fase, latency lebih rendah untuk
  turn ringan, tapi memaksa provisioning ke dimensi terburuk dan
  mencampur fault domain — bug di code exec bisa menghabiskan memory pod
  yang sama dipakai context assembly), atau pisah penuh sejak awal
  (tiap fase scale di sinyalnya sendiri, tapi menambah kerumitan
  operasional — lebih banyak service, network hop antar panggilan). KB
  ini memilih jalan tengah: **modular monolith dengan jahitan dipotong**
  — satu deployable hari ini, interface yang sudah benar supaya pisahnya
  nanti tinggal ganti binding, bukan rewrite (detail di
  `serving-topology.md`).
- **Resource request per-pod ketat vs longgar** — request ketat (dipatok ke
  rata-rata, bukan puncak) menghemat biaya tapi bikin pod di-throttle atau
  OOM-kill saat code exec/context assembly kebetulan menumpuk bareng;
  request longgar (dipatok ke puncak) aman tapi mahal karena idle capacity
  besar sepanjang fase IO-bound. Trade-off ini hilang kalau code exec
  dipisah ke komponen (Tool executor) yang scale sendiri — pod orchestrator
  tidak perlu lagi menutupi puncak CPU yang bukan miliknya.
- **Batching embedding vs sinkron per-turn** — batch beberapa request
  embedding sebelum mengirim ke GPU memperbaiki utilisasi GPU (throughput
  lebih tinggi per watt/detik) tapi menambah latency tunggu batch
  terkumpul; sinkron per-turn (encode segera) latency rendah tapi GPU
  sering idle menunggu request berikutnya. Pilihan ini didorong oleh
  volume trafik retrieval, bukan keputusan arsitektur tetap — dibahas lagi
  di `scaling.md`.

## Di deepagents

`deepagents` tidak menjalankan proses terpisah per fase — kelima fase di
atas semuanya terjadi di dalam satu proses Python yang menjalankan graph
LangGraph, dalam urutan yang sama seperti tabel di atas:

| Fase | Konkret di deepagents | Sumber |
|---|---|---|
| LLM call | `model.invoke`/`.stream` yang dipanggil `langchain.agents.create_agent` di tiap node graph — IO murni, deepagents tidak menambah kerja CPU di jalur ini | `[code]` `../systems/deepagents.md` §1 (Loop shape) |
| Context assembly | `SummarizationMiddleware` (kompaksi berbasis threshold token) menyusun ulang `DeepAgentState.messages` jadi prompt tiap call — kerja memory/string-formatting, bukan CPU-heavy | `[code]` `../systems/deepagents.md` §2 |
| Code exec | `FilesystemMiddleware`'s tool `execute`, jalan lewat backend yang mengimplementasi `SandboxBackendProtocol` — `LocalShellBackend` bawaan menjalankan `subprocess.run(shell=True)` di proses/host yang sama, **CPU dan risiko sepenuhnya milik proses itu**, tidak terisolasi kecuali backend diganti (lihat `sandboxing.md`) | `[code]` `../systems/deepagents.md` §6 (Safety gate, kutipan `THREAT_MODEL.md`) |
| Embedding | Tidak ada di `deepagents` inti — `deepagents` tidak melakukan embedding/vector search sendiri; kalau retrieval dipakai, itu tool aplikasi (mis. dipanggil lewat `StoreBackend`/backend kustom) yang berjalan di luar kendali `deepagents` | `[inferred]` — disimpulkan dari absennya primitive embedding di `## API permukaan`/`## Middleware bawaan` `../systems/deepagents.md` |
| Checkpoint write | `checkpointer` yang disuntik aplikasi, dipanggil tiap step graph — `deepagents` meneruskannya apa adanya ke `create_agent`, tidak membangun sendiri | `[code]` `../systems/deepagents.md` §5 (`deepagents/graph.py` baris 546-553, 922-931) |

Implikasi langsung: karena kelima fase berbagi satu proses Python yang sama
di stack default `deepagents`, memisahkannya menjadi komponen dengan sinyal
scaling sendiri (§8.3) **bukan** sesuatu yang `deepagents` sediakan
otomatis — itu keputusan deployment aplikasi (lihat `serving-topology.md`),
dan satu-satunya seam siap pakai yang `deepagents` sudah beri untuk ini
adalah `SandboxBackendProtocol` (untuk code exec) dan `StoreBackend`/
`CompositeBackend` (untuk state durable/retrieval) — keduanya interface,
bukan proses terpisah bawaan.

## Sumber

- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §1, §2,
  §5, §6 — tier-1 reference yang sudah diverifikasi terhadap source
  `deepagents==0.7.8` di Task 3, dikutip di sini tanpa membaca ulang
  source.
- `[code]` OpenHands `openhands/core/config/sandbox_config.py` dan
  `openhands/runtime/impl/docker/docker_runtime.py`, dibaca lewat diff PR
  `All-Hands-AI/OpenHands#6616` ("Add memory limit option for Docker
  runtime"): field `memory_limit: str | None = Field(default=None, ...
  None means no limit.")` dipetakan ke `mem_limit=self.config.sandbox.memory_limit`
  saat start container — dipakai sebagai bukti bahwa tanpa batas eksplisit,
  fase code exec yang CPU/memory-bound bisa memakai seluruh resource host,
  bukan cuma "porsi wajarnya" — memperkuat argumen kenapa fase ini butuh
  provisioning terpisah dari fase IO-bound. Detail isolasi lengkap di
  `sandboxing.md`.

  > **Catatan repo (2026-08-23):** `All-Hands-AI/OpenHands` sudah
  > di-redirect ke `OpenHands/OpenHands` ("Agent Canvas"); agent coding
  > aslinya pindah ke `OpenHands/software-agent-sdk`. Path
  > `openhands/core/config/sandbox_config.py` dan
  > `openhands/runtime/impl/docker/docker_runtime.py` di atas tidak lagi
  > ada di struktur repo saat ini — klaim ini tetap berlaku untuk commit
  > `db37f350` / PR `#6616` yang disitasi, sebagai snapshot historis.
  > Lihat [`../systems/openhands.md`](../systems/openhands.md).
- `[docs]` KEDA — mekanisme scaling per sinyal kustom yang jadi alasan
  pemisahan komponen berguna secara praktis, dikutip via WebFetch dari
  `keda.sh/docs/latest/concepts/scaling-deployments/`. Detail lengkap di
  `serving-topology.md` dan `scaling.md`.
