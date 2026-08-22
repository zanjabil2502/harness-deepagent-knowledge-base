# Scaling

## Masalah

`serving-topology.md` menetapkan **sinyal apa** yang benar per komponen
(in-flight turns, bukan RPS, untuk orchestrator; queue depth untuk tool
executor; batch queue/GPU util untuk retrieval). File ini menjawab
pertanyaan operasional berikutnya: **bagaimana sinyal itu benar-benar
dikonfigurasi di Kubernetes**, dan dua masalah tambahan yang khas beban
agent dan tidak muncul di HPA CPU biasa — cold start sandbox eksekusi, dan
node yang punya GPU tapi node pool-nya campur dengan CPU-only.

Instinct default "semua komponen pakai HPA CPU yang sama" gagal dua kali:
gagal secara sinyal (sudah dibahas `serving-topology.md`), dan gagal secara
penempatan node — pod CPU-only yang kebetulan terjadwal ke node ber-GPU
membuang alokasi paling mahal di cluster untuk kerja yang tidak
membutuhkannya, dan pod ber-GPU yang terjadwal ke node tanpa GPU sama
sekali tidak bisa jalan.

## Pola

### Konfigurasi konkret per komponen

| Komponen | Sinyal (dari `serving-topology.md`) | Mekanisme K8s konkret |
|---|---|---|
| Gateway / SSE | Koneksi aktif | KEDA `ScaledObject` trigger `prometheus` atas gauge koneksi-aktif per pod (metrik ini biasanya sudah diekspos ingress controller/gateway itu sendiri) |
| Orchestrator | In-flight turns | KEDA `ScaledObject` trigger `prometheus` atas gauge in-flight-turns aplikasi (lihat `serving-topology.md` untuk cara mengeksposnya) — KEDA men-generate HPA object dari sini `[docs]` |
| Tool executor | Queue depth, CPU | Kalau antrean turn (`queueing-and-backpressure.md`) memang dibackend queue nyata (Redis list, RabbitMQ), KEDA punya scaler native untuk itu; kalau cuma gauge queue-depth kustom, trigger `prometheus` yang sama. KEDA **Scaling Modifiers** memungkinkan menggabung dua trigger (queue depth + CPU) jadi satu formula scaling, bukan cuma OR sederhana `[docs]` |
| Retrieval / embedding | Batch queue, GPU util | Pool kecil terdedikasi, bukan HPA-per-request — concurrency-based (lihat pola Ray Serve `target_ongoing_requests` di `serving-topology.md`), skala minimal/nol lewat KEDA scale-to-zero karena node GPU adalah baris biaya termahal |
| State store | Bukan pod | Scale lewat read replica + connection pooling (mis. PgBouncer), bukan HPA — Postgres tidak "menambah pod" untuk menyerap beban |

### Cold start sandbox: warm pool vs on-demand

Eksekusi kode terisolasi (`sandboxing.md`) punya cold-start yang tidak
nol — microVM (E2B, Daytona) butuh waktu boot sebelum siap menerima
command. Kedua provider menyediakan primitive **pause/resume** justru
untuk memotong biaya ini: E2B `lifecycle.on_timeout: "pause"` (resume dari
memory snapshot kalau `keep_memory=True`, jauh lebih cepat dari create
baru) dan Daytona `auto_pause_interval` (default 60 menit untuk sandbox
class yang mendukung pause) `[code]` — sudah dikutip penuh di
`sandboxing.md` dari source SDK masing-masing.

Implikasi scaling: alih-alih membuat sandbox baru dari nol tiap tool call
(cold start penuh di jalur kritis interaktif), operator bisa menahan
**warm pool** — sejumlah kecil sandbox yang sudah dibuat dan di-pause,
di-resume begitu ada tool call masuk, diisi ulang di background begitu
pool menipis. Ukuran pool digerakkan sinyal yang sama dengan Tool
executor di tabel atas (queue depth tool exec yang trending naik →
tambah warm pool sebelum permintaan sungguh datang), bukan angka statis.

### Node pool GPU dengan taint

Retrieval/embedding butuh GPU; komponen lain (gateway, orchestrator, tool
executor) tidak. Tanpa penanda eksplisit, scheduler Kubernetes bisa
menempatkan pod CPU-only ke node ber-GPU (membuang alokasi GPU node itu
untuk kerja yang tidak memakainya) atau sebaliknya gagal menempatkan pod
ber-GPU sama sekali kalau node ber-GPU penuh dipakai pod lain. Mekanisme
standarnya **taint + toleration**: taint di-pasang ke node, membuatnya
menolak pod apa pun kecuali yang punya toleration yang cocok `[docs]`.

```bash
# Tandai node GPU supaya menolak pod tanpa toleration yang cocok
kubectl taint nodes gpu-node1 nvidia.com/gpu=true:NoSchedule
```

```yaml
# Pod embedding/retrieval: toleration yang cocok + permintaan resource GPU
tolerations:
  - key: "nvidia.com/gpu"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"
resources:
  limits:
    nvidia.com/gpu: 1
```

Taint mencegah pod CPU-only (yang tidak punya toleration itu) terjadwal
ke node GPU sama sekali; `nodeSelector`/`nodeAffinity` di sisi pod
embedding memastikan arah sebaliknya — pod GPU cuma mau ditempatkan ke
node yang memang punya GPU. Dua mekanisme ini saling melengkapi, bukan
saling menggantikan: taint melindungi node dari pod yang salah, affinity
mengarahkan pod ke node yang benar `[docs]` — dikutip via WebFetch dari
`kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/`.

## Trade-off

- **Warm pool sandbox vs on-demand murni** — warm pool memotong latency
  tool-call pertama (langsung resume, bukan cold-boot), relevan kalau
  eksekusi kode ada di jalur kritis interaktif (user menunggu). Biayanya:
  membayar kapasitas sandbox yang idle menunggu dipakai, dan kompleksitas
  operasional menjaga pool tetap terisi. On-demand murni tidak membayar
  idle capacity sama sekali, tapi tiap tool call pertama kena cold-start
  penuh — dapat diterima kalau tool exec bukan di jalur interaktif (mis.
  job background) atau volumenya cukup rendah sehingga cold-start jarang
  terjadi berturut-turut.
- **Taint GPU vs tanpa taint (biarkan scheduler bebas menempatkan)** —
  tanpa taint lebih sederhana (satu node pool homogen, tidak ada
  toleration untuk dikonfigurasi), tapi berisiko: pod CPU-only yang
  kebetulan terjadwal ke node GPU membuang alokasi node paling mahal di
  cluster, dan node itu juga berbagi resource non-GPU (CPU/memory) dengan
  pod yang tidak seharusnya ada di sana, mengurangi kapasitas untuk beban
  GPU yang sungguh butuh node itu. Taint membayar sedikit risiko stranded
  capacity (kalau pool GPU dibuat lebih besar dari demand, node itu cuma
  bisa dipakai pod yang tolerate — kalau tidak ada yang butuh, node itu
  idle dan tidak bisa "dipinjam" beban lain) — untuk beban yang secara
  eksplisit memisahkan komponen GPU-bound (§8.3), taint tetap pilihan
  default yang lebih aman.
- **HPA generik (satu metric, satu formula) vs KEDA Scaling Modifiers
  (gabungan beberapa trigger)** — HPA generik sederhana untuk dipahami
  dan didebug (satu angka, satu ambang), tapi tidak bisa menangkap
  komponen yang sungguh dibatasi dua dimensi sekaligus (Tool executor:
  queue depth **dan** CPU, keduanya bisa jadi bottleneck tergantung
  workload). Scaling Modifiers menangkap itu lewat formula, dengan biaya
  konfigurasi yang lebih rumit untuk dipahami dan didebug saat scaling
  berperilaku tak terduga.

## Di deepagents

`deepagents` tidak berjalan di dalam Kubernetes dan tidak tahu apa itu
HPA/KEDA/node pool/taint sama sekali — semua mekanisme di file ini
beroperasi di lapisan deployment **di atas** `deepagents`, murni tanggung
jawab aplikasi yang membungkusnya. Satu titik yang relevan langsung:
sinyal queue-depth/latency tool exec yang menggerakkan warm-pool sandbox
di atas **bisa dihitung dari data yang sudah ada** tanpa menciptakan
sumber metrik baru — kolom `started_at`/`completed_at` di tabel
`tool_calls` (`persistence-schema.md`, Task 4) sudah cukup untuk menghitung
durasi tunggu dan tren volume tool call, karena tiap panggilan `execute`
lewat `SandboxBackendProtocol` (`sandboxing.md`) tercatat sebagai baris
tool call yang sama seperti tool lain. `[code]` —
[`persistence-schema.md`](persistence-schema.md), tabel `tool_calls`.

## Sumber

- `[docs]` KEDA — `ScaledObject`, trigger `prometheus`, Scaling
  Modifiers (formula gabungan beberapa trigger), scale-to-zero, dikutip
  via WebFetch dari `keda.sh/docs/latest/concepts/scaling-deployments/`.
- `[docs]` Ray Serve — model concurrency-based (`target_ongoing_requests`)
  yang jadi dasar pola pool retrieval/embedding di sini, dikutip via
  WebFetch dari `docs.ray.io/en/latest/serve/autoscaling-guide.html`
  (detail lengkap sudah dikutip di `serving-topology.md`).
- `[docs]` Kubernetes — taints/tolerations (`kubectl taint`, `NoSchedule`,
  pola dedicated-node dengan `nvidia.com/gpu`), dikutip via WebFetch dari
  `kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/`.
- `[code]` E2B (`e2b/sandbox/main.py`, `e2b/sandbox_sync/main.py`) dan
  Daytona (`daytona/common/daytona.py`) — parameter lifecycle
  pause/resume yang jadi dasar pola warm pool, dibaca langsung dari paket
  PyPI `e2b==2.45.1` dan `daytona==0.205.1`, sudah dikutip penuh di
  `sandboxing.md`.
- `[code]` [`persistence-schema.md`](persistence-schema.md) — tabel
  `tool_calls` (`started_at`, `completed_at`) sebagai sumber sinyal
  cold-start/queue-depth tanpa metrik baru, Task 4.
- `[code]` [`serving-topology.md`](serving-topology.md),
  [`sandboxing.md`](sandboxing.md) — tabel komponen→bound→sinyal HPA dan
  spektrum isolasi sandbox yang jadi dasar konfigurasi konkret di file
  ini.
