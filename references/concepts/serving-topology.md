# Serving topology

## Masalah

Instinct default untuk men-deploy layanan HTTP baru — satu Deployment, satu
Service, HPA berbasis CPU atau request-per-second (RPS) di depan reverse
proxy dengan timeout default — dirancang untuk request yang selesai dalam
puluhan-ratusan milidetik. Satu turn agent bisa berjalan **menit**, terdiri
dari beberapa LLM call bergantian dengan tool call (lihat
`resource-profiling.md`). Ketiganya — timeout HTTP, rolling deploy, dan HPA
berbasis RPS — diam-diam mengasumsikan "request pendek", dan pecah dengan
cara berbeda begitu asumsi itu salah:

1. **Timeout HTTP default memutus turn di tengah jalan.** Nginx
   `proxy_read_timeout` default 60 detik, AWS ALB idle timeout default 60
   detik `[docs]`. Keduanya adalah gap-timeout (jarak maksimum antar
   pembacaan data), bukan total-duration timeout — respons streaming yang
   mengirim byte tiap beberapa detik tidak memicunya. Tapi begitu ada satu
   hop di jalur (proxy internal, ingress controller, load balancer cloud)
   yang tidak dikonfigurasi ulang atau tidak mendukung streaming/keep-alive
   yang sama, turn menit-panjang mati di tengah dengan 502/504 tanpa
   pemberitahuan ke aplikasi.
2. **Rolling deploy membunuh turn in-flight.** Default Kubernetes rolling
   update mengirim `SIGTERM` ke pod lama begitu pod baru ready, dengan
   `terminationGracePeriodSeconds` default 30 detik `[docs]`. Turn yang
   sedang menunggu LLM call menit-panjang atau di tengah tool call
   panjang mati bersama pod-nya kalau tidak ada drain logic.
3. **HPA berbasis RPS salah baca beban IO-bound berumur-panjang.** RPS
   mengukur laju kedatangan request baru per detik; itu proxy yang bagus
   untuk beban di mana durasi request pendek dan seragam, tapi buta
   terhadap **concurrency** — berapa banyak turn yang sedang aktif di satu
   waktu. Dijabarkan penuh di bawah.

## Pola

### Komponen → bound → sinyal HPA (§8.3)

| Komponen | Bound | Sinyal HPA |
|---|---|---|
| Gateway / SSE | IO | Koneksi aktif (bukan RPS — gateway menahan koneksi lama, bukan memproses cepat lalu lepas) |
| Orchestrator | IO dominan | **In-flight turns**, bukan RPS |
| Tool executor | CPU + memory | Queue depth, CPU |
| Retrieval / embedding | GPU atau CPU | Batch queue, GPU util |
| State store | IO/disk | Bukan pod — scale lewat read replica/connection pooling, bukan HPA |

Detail konfigurasi konkret per baris (trigger KEDA, node pool GPU, dsb) ada
di `scaling.md`; file ini menjelaskan **kenapa** baris orchestrator berbeda
dari default RPS, dan **apa** yang harus disediakan supaya sinyal itu bisa
dipakai.

### Kenapa RPS salah untuk orchestrator — dan apa yang harus dibela

RPS = laju kedatangan request baru per detik. Itu proxy yang valid untuk
beban CRUD singkat karena di sana `concurrency ≈ RPS × durasi request`, dan
durasi request nyaris konstan (puluhan-ratusan ms) — jadi RPS dan
concurrency bergerak searah, RPS aman dipakai sebagai sinyal beban.

Begitu durasi request naik dari milidetik ke menit, hubungan itu berubah
drastis (hukum Little: `concurrency = arrival_rate × durasi`). Dua contoh
dengan RPS sama tapi beban pod yang sama sekali berbeda:

- 10 turn/detik masuk, tiap turn selesai dalam 100ms → concurrency rata-rata
  ~1 turn aktif. Pod nyaris tidak terbebani.
- 10 turn/detik masuk, tiap turn berjalan 5 menit → concurrency rata-rata
  ~3000 turn aktif secara bersamaan. Pod bisa kehabisan memory (tiap turn
  in-flight menahan context yang di-assembly, lihat `resource-profiling.md`)
  jauh sebelum RPS terlihat tinggi di dashboard manapun.

HPA yang mengamati RPS tidak bisa membedakan dua situasi ini — angkanya
sama-sama "10". Ia akan gagal scale-out pada kasus kedua (RPS-nya rendah,
padahal pod sedang sekarat menahan ribuan turn concurrent), dan berpotensi
over-provision pada kasus sejenis pertama (RPS terlihat tinggi walau tiap
pod sanggup menahan concurrency jauh lebih besar, karena orchestrator
IO-bound bisa menahan ratusan turn async per pod tanpa CPU tambahan — lihat
`resource-profiling.md`). Sinyal yang benar bukan laju kedatangan, tapi
**berapa banyak turn yang sedang terbuka sekarang** — in-flight turns.

Preseden nyata untuk pola ini: Ray Serve, sebuah serving framework produksi,
sudah scale berdasar **ongoing/in-flight request per replica**
(`target_ongoing_requests`), bukan RPS, justru karena alasan yang sama —
durasi request yang bervariasi butuh sinyal concurrency, bukan sinyal laju.
`num_replicas="auto"` di Ray Serve default ke `target_ongoing_requests: 2`.
`[docs]` — `docs.ray.io/en/latest/serve/autoscaling-guide.html`, dikutip
via WebFetch. Ini bukan pola eksotis yang KB ini reka sendiri; ini pola yang
sudah dipilih sistem serving produksi lain untuk masalah yang sama persis.

**Yang harus disediakan di Kubernetes supaya in-flight-turn scaling
sungguh bisa dipakai:**

1. Orchestrator harus mengekspos **gauge metric** — bukan counter — jumlah
   turn yang sedang berjalan di proses itu saat ini: naik saat turn mulai,
   turun saat turn selesai/gagal/dibatalkan. Diekspos lewat endpoint
   `/metrics` format Prometheus per pod.
2. Prometheus (atau kompatibel) men-scrape endpoint itu lintas semua pod
   orchestrator dan menyimpan time series-nya.
3. **KEDA `ScaledObject`** dengan trigger `prometheus` menunjuk ke query
   agregat (mis. rata-rata in-flight turn per pod) — KEDA menerjemahkan
   nilai ini jadi objek HPA berbasis custom/external metric yang
   dikendalikan Kubernetes native. `[docs]` — KEDA mendukung trigger
   `prometheus`, `metrics-api`, dan External Scaler untuk metrik kustom;
   ScaledObject men-generate dan mengelola HPA-nya sendiri, dikutip via
   WebFetch dari `keda.sh/docs/latest/concepts/scaling-deployments/`.
4. Ambang (`threshold`) di trigger itu dipatok **di bawah** batas
   concurrency yang aman secara memory per pod (informasi ini datang dari
   `resource-profiling.md`: tiap turn in-flight menahan context assembly-nya
   di memory) — bukan angka sembarang.
5. Lifecycle pod harus selaras dengan sinyal ini, bukan cuma metric-nya:
   scale-down tidak boleh membunuh pod yang masih menahan in-flight turn —
   lihat solusi rolling-deploy di bawah, prinsipnya sama untuk scale-down
   HPA.

### Tiga masalah turn panjang dan mitigasinya

| Masalah | Penyebab | Mitigasi |
|---|---|---|
| Timeout HTTP default | `proxy_read_timeout`/idle timeout 60s adalah default di nyaris tiap hop (nginx, ALB) `[docs]` | Streaming SSE dengan frame keep-alive berkala (reset gap-timeout tiap event, bukan tiap total-duration), naikkan timeout eksplisit di **tiap** hop (bukan cuma satu), atau — lebih tahan-gagal — jangan tahan satu koneksi HTTP sepanjang turn sama sekali: kirim `turn_id` segera, biarkan client reattach (lihat `queueing-and-backpressure.md`) |
| Rolling deploy memutus in-flight turn | `SIGTERM` + grace period 30s default begitu pod baru ready `[docs]` | `preStop` hook yang berhenti menerima turn baru lalu menunggu in-flight selesai (drain) sebelum keluar; `terminationGracePeriodSeconds` dinaikkan melebihi p99 durasi turn; readiness probe dimatikan duluan supaya Service berhenti mengirim turn baru ke pod itu sementara in-flight tetap diselesaikan; kalau drain window habis sebelum turn selesai, checkpointer resumability (`session-state.md`) adalah jaring pengaman — turn bisa dilanjut pod lain dari checkpoint terakhir |
| HPA berbasis RPS salah baca beban | RPS buta terhadap concurrency untuk request berdurasi bervariasi | In-flight-turns sebagai sinyal (lihat di atas), bukan RPS |

Ketiganya berakar dari satu asumsi yang sama yang salah untuk agent: bahwa
satu unit kerja HTTP itu singkat. Solusinya juga satu tema yang sama:
jadikan turn sebagai entitas yang **outlive** koneksi/pod/permintaan HTTP
tunggal yang membawanya — bisa direattach, di-resume, dan diukur
concurrency-nya secara independen dari request HTTP yang memicunya.

### Modular monolith dengan jahitan dipotong

> `_base` = modular monolith dengan jahitan sudah dipotong. Satu
> deployable, tapi orchestrator / executor / retrieval terpisah di balik
> interface, sehingga pecah jadi microservice = ganti binding + manifest,
> bukan rewrite. (§8.3)

Ini bukan slogan — ada syarat konkret supaya klaim "tinggal ganti
binding" itu benar-benar berlaku nanti, bukan janji kosong:

1. **Panggilan lintas komponen lewat interface eksplisit, bukan
   pemanggilan langsung fungsi/objek internal.** Orchestrator memanggil
   tool executor lewat kontrak (mis. `execute(command, cwd) -> Result`),
   bukan mengimpor modul executor dan memanggil fungsi internalnya
   langsung. Tanpa ini, "memisahkan jadi service" berarti menelusuri dan
   menulis ulang tiap titik pemanggilan, bukan mengganti implementasi di
   satu tempat.
2. **Argumen dan hasil di batas interface harus serializable
   (JSON/msgpack), bukan objek Python mentah (file handle, koneksi DB,
   closure).** Interface yang lewat proses masih boleh lolos dengan objek
   in-memory hari ini — begitu dipisah jadi service sungguhan, batas itu
   jadi panggilan jaringan sungguhan, dan objek non-serializable memaksa
   rewrite kontrak, bukan sekadar ganti binding.
3. **Tidak ada shared mutable state yang dijangkau lewat jalan pintas di
   luar interface** (mis. orchestrator membaca langsung file lokal milik
   executor, atau bergantung pada variabel global proses yang sama).
   Jalan pintas semacam ini adalah coupling tak tertulis yang baru
   ketahuan rusak setelah kedua komponen dipisah ke host berbeda.
4. **Interface menerima scope object secara eksplisit sebagai parameter**
   (`(user_id)` atau `(tenant_id, user_id)`, lihat `isolation-and-scoping.md`),
   bukan bergantung pada ambient state (thread-local, variabel proses)
   yang kebetulan benar karena semua komponen masih satu proses. Begitu
   jadi network call sungguhan, otorisasi harus ikut eksplisit di
   payload/token — bukan "aman karena satu mesin".

`deepagents` sudah menyediakan dua dari tiga jahitan ini secara bawaan
lewat interface, dijabarkan di `## Di deepagents` di bawah — KB ini
memilih memakainya alih-alih membangun interface sendiri dari nol.

## Trade-off

- **Monolith vs split sejak awal** `[ours]` — vanilla-nya: split sejak awal
  (orchestrator, executor, retrieval sebagai service terpisah dari hari
  pertama), yang memberi scaling independen dari awal, tapi menambah
  latency network hop dan kerumitan operasional (deployment, discovery,
  observability lintas service) untuk beban yang di awal proyek mungkin
  belum butuh itu. KB ini memilih modular monolith dengan jahitan dipotong
  (§8.3) alih-alih itu, karena menunda biaya split sampai benar-benar
  perlu (traffic salah satu komponen jauh melampaui yang lain), dengan
  biaya disiplin menulis interface yang benar sejak awal (empat syarat di
  atas) — kalau disiplin itu dilanggar, migrasi nanti tetap jadi rewrite,
  jahitan itu jadi janji kosong.
- **Timeout dinaikkan vs turn di-detach dari koneksi HTTP** — menaikkan
  timeout di tiap hop lebih sederhana (tidak mengubah model request-response)
  tapi rapuh: satu hop yang lupa dikonfigurasi ulang, atau infra pihak
  ketiga (CDN, WAF) dengan timeout keras yang tidak bisa diubah, tetap
  memutus turn. Men-detach turn dari koneksi HTTP (turn_id + reattach,
  `queueing-and-backpressure.md`) lebih tahan-gagal tapi mengubah model
  API dari request-response sinkron jadi submit-lalu-poll/subscribe —
  perubahan kontrak klien yang lebih besar.
- **Drain saat rolling deploy vs terima turn putus dan resume dari
  checkpoint** — drain (tunggu in-flight selesai sebelum pod mati) tidak
  pernah memutus turn ditambah tidak butuh app logic resume yang rumit,
  tapi menahan rollout (deploy baru menunggu turn terlama selesai, bisa
  lama untuk turn menit-panjang). Resume dari checkpoint (biarkan pod mati,
  turn lanjut di pod lain dari checkpoint terakhir) membuat rollout tidak
  perlu menunggu, tapi butuh checkpointer yang benar-benar resumable
  (`session-state.md`) dan toleransi user terhadap turn yang terlihat
  "berhenti sejenak". Pola realistis: keduanya sekaligus — drain sebagai
  jalur utama, resume sebagai jaring pengaman kalau drain window habis.

## Di deepagents

Dua dari tiga jahitan "modular monolith" di atas sudah ada sebagai
interface bawaan `deepagents`, bukan perlu dibangun sendiri:

- **Tool executor** — semua eksekusi tool lewat `FilesystemMiddleware`
  memanggil backend yang mengimplementasi `SandboxBackendProtocol`
  (`execute()`). Ini sudah interface: `LocalShellBackend` (in-process,
  tanpa isolasi) dan implementasi custom (mis. pembungkus E2B/Daytona,
  lihat `sandboxing.md`) sama-sama memenuhi kontrak yang sama, dipanggil
  orchestrator lewat cara yang sama. `[code]` —
  [`../systems/deepagents.md`](../systems/deepagents.md) §6, §Backend
  filesystem.
- **Retrieval/state durable** — `StoreBackend(namespace=...)` adalah *hook*
  scoping resmi ke `store` yang disuntik aplikasi; `CompositeBackend`
  merutekan path ke backend berbeda per prefix. Keduanya interface yang
  sudah memisahkan "di mana state durable hidup" dari logic orchestrator.
  `[code]`+`[docs]` — [`../systems/deepagents.md`](../systems/deepagents.md)
  §Backend filesystem (contoh `namespace=lambda rt: (rt.server_info.user.identity,)`
  dari `docs.langchain.com/oss/python/deepagents/backends`).

**Orchestrator itu sendiri** = graph LangGraph yang dirakit
`create_deep_agent`/`create_agent` — `deepagents` tidak memaksa topologi
deployment apa pun untuknya; ke mana pun graph itu di-invoke (satu proses
FastAPI, satu Job Kubernetes, satu worker antrean) adalah keputusan
aplikasi sepenuhnya di luar `deepagents`. Konsekuensinya, sinyal in-flight
turns yang dibahas di atas **tidak** disediakan `deepagents` — gauge
metric-nya harus ditulis aplikasi di titik ia memanggil `.invoke`/`.stream`
pada graph, dengan increment sebelum panggil dan decrement di
`finally`/callback selesai. `[inferred]` — disimpulkan dari tidak
ditemukannya primitive metrics/observability bawaan di
`## API permukaan`/`## Middleware bawaan` `../systems/deepagents.md`.

## Sumber

- `[docs]` KEDA — `ScaledObject`, trigger `prometheus`/`metrics-api`/
  External Scaler, hubungan dengan HPA native Kubernetes, dikutip via
  WebFetch dari `keda.sh/docs/latest/concepts/scaling-deployments/`.
- `[docs]` Ray Serve — model autoscaling berbasis
  `target_ongoing_requests` (in-flight request per replica, bukan RPS),
  `num_replicas="auto"` default `target_ongoing_requests: 2`, dikutip via
  WebFetch dari `docs.ray.io/en/latest/serve/autoscaling-guide.html`.
- `[docs]` Nginx — default `proxy_read_timeout` 60 detik sebagai
  gap-timeout (bukan total-duration), dikutip via WebSearch dari
  dokumentasi konfigurasi timeout Nginx.
- `[docs]` AWS Elastic Load Balancing — default idle timeout 60 detik,
  dikutip via WebSearch dari pengumuman/dokumentasi resmi AWS ELB idle
  timeout configuration.
- `[docs]` Kubernetes — perilaku rolling update (`SIGTERM` ke pod lama
  begitu pod baru ready) dan `terminationGracePeriodSeconds` default 30
  detik — pengetahuan standar Kubernetes, dikonfirmasi silang lewat
  dokumentasi taint/toleration dan lifecycle pod yang sama yang dikutip di
  `scaling.md`.
- `[code]` [`../systems/deepagents.md`](../systems/deepagents.md) §6,
  §Backend filesystem — tier-1 reference terverifikasi Task 3, dikutip
  tanpa membaca ulang source.
- `[code]` `resource-profiling.md` (file ini) — argumen concurrency vs RPS
  dibangun di atas breakdown fase-dalam-turn yang dijelaskan di sana.
