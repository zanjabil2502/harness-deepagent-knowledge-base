# Indeks sistem

Sembilan entri **T2** (grid 7 sumbu penuh, satu file per sistem — lihat
`_template.md`) plus entri **T3** (indeks murah: nama + arketipe + satu
baris ciri khas, tanpa file terpisah). T3 ada supaya menambah harness baru
yang ditemukan nanti cukup satu baris di sini, bukan restrukturisasi grid —
lihat §10 desain spec.

Kolom **Multilingual** mencatat *apakah sistem punya desain eksplisit*
untuk pemisahan intent/ekspresi dan lokalisasi (lihat
`references/concepts/multilingual.md`), bukan sekadar "mendukung bahasa
lain lewat model dasarnya". Ketiadaan desain itu sendiri adalah temuan —
lihat catatan di bawah tabel.

## Tier 1 — SDK dasar KB ini

Bukan agent produk, jadi di luar hitungan "sembilan T2" dan catatan
multilingual di bawah — tapi diberi grid 7 sumbu penuh (§Sumber-nya lebih
dalam dari T2 mana pun: paket terinstal, bukan repo yang dikloning sekali)
karena inilah SDK yang dipakai membangun tiap arketipe di KB ini.

| Nama | Arketipe | Tier | Ciri khas | Multilingual | Label sumber |
|---|---|---|---|---|---|
| [deepagents](deepagents.md) | Bukan satu arketipe — SDK harness dipakai membangun arketipe apa pun (lihat §Arketipe file-nya) | T1 | Middleware-stack (filesystem, subagent, summarization, prompt-cache) di atas LangChain/LangGraph; default stack paling dekat General Task Agent (03), tiap axis bisa digeser lewat parameter `create_deep_agent(...)` | Tidak berlaku — SDK, bukan agent produk dengan permukaan bahasa sendiri | `[code]` mayoritas |

## Tier 2 — bedah 7 sumbu

| Nama | Arketipe | Tier | Ciri khas | Multilingual | Label sumber |
|---|---|---|---|---|---|
| [OpenHands](openhands.md) | Workspace Agent (01) + Generative Builder (02) | T2 | Nama repo sudah pivot jadi "Agent Canvas" (kontrol multi-backend); agent inti pindah ke `software-agent-sdk`; routing skill deterministik (keyword/path match di kode, bukan judgment murni) | UI i18n saja (`src/i18n`, bukan desain locale-aware agent) | `[code]` mayoritas |
| [LibreChat](librechat.md) | Workspace Agent (01) + In-App Copilot (05) | T2 | Loop agent aktual hidup di paket npm terpisah `@librechat/agents` (LangGraph); transkrip tree via `parentMessageId`; delegasi lewat handoff tool antar-agent | UI i18n (`client/src/locales`, i18next) — bukan pipeline intent/ekspresi | `[code]` mayoritas |
| [Aider](aider.md) | Workspace Agent (01) | T2 | Tidak pakai tool-calling API sama sekali — parsing blok edit dari teks; RepoMap PageRank untuk context; loop "reflection" (`max_reflections=3`), bukan ReAct tool-loop | Tidak ada | `[code]` mayoritas |
| [Vercel `ai-chatbot`](vercel-ai-chatbot.md) | In-App Copilot (05) + Generative Builder (02) | T2 | `stopWhen: isStepCount(5)` — batas 5 langkah keras; artefak berversi lewat composite PK `(id, createdAt)`; reattach stream bersyarat `REDIS_URL`, endpoint GET reattach berisi stub 204 di snapshot yang dibaca | Tidak ada | `[code]` mayoritas |
| [LiteLLM](litellm.md) | Bukan agent — infrastruktur gateway/routing | T2 | Bukan agent-loop; retry+cooldown lintas-deployment; `routing_strategy` algoritmik (5+ strategi); >25 provider guardrail sebagai plugin registry deklaratif | Tidak ada | `[code]` mayoritas |
| [Letta](letta.md) | Workspace Agent (01) | T2 | Repo asli diarsipkan, source pindah ke `letta-code`; memori kini git-backed per-agent (`~/.letta/agents/<id>/memory/`, repo git sungguhan) di atas memory-block API lama; default permission mode `"unrestricted"` | Tidak ada | `[code]` mayoritas |
| [Dify](dify.md) | Platform: In-App Copilot (05) / Workflow Agent (06) tergantung tipe app | T2 | Dua runner loop terpisah (`FunctionCallAgentRunner` tool-calling vs `CotAgentRunner` teks-ReAct), batas 99 iterasi; node `human_input` sebagai primitif HITL di DAG; workflow lain bisa dipublikasikan jadi tool (`workflow_as_tool`) | Ada — i18n UI + email (`web/i18n`, `email_i18n.py`), lebih luas dari sistem lain di grid tapi tetap string-level, bukan pipeline intent/ekspresi | `[code]` mayoritas |
| [browser-use](browser-use.md) | Computer-Use Agent (07) | T2 | 26 tool sempit; loop 3-fase (screenshot+DOM → LLM → aksi); dua batas independen (`max_steps=500`, `max_failures=5` berturut-turut); warning eksplisit prompt-injection→eksfiltrasi `sensitive_data` saat `allowed_domains` tak dikunci | Tidak ada | `[code]` mayoritas |
| [OpenWorker](openworker.md) | General Task Agent (03), hibrida 01/02/05/06 — terbanyak di grid | T2 | Empat kelas risiko sebagai data (`risk.py`); approver ditukar per mode sesi; sesi unattended **suspend tanpa timeout** di Inbox dengan permintaan durable-idempoten `(session_id, tool_call_id)`; kompaksi berbatas `boundary_index` kanonik→outbound | Tidak ada | `[code]` mayoritas |
| [Claude Code](claude-code.md) | Workspace Agent (01) | T2 | Closed-source — seluruh file `[docs]`/`[inferred]`; contoh utama KB untuk sumbu 7 "prosa + judgment model" **termasuk kelemahannya**: cap 1.536 karakter/skill (dilusi terukur), tidak ada kode intent netral (keterikatan bahasa) | Tidak diketahui (closed; tidak ditemukan halaman docs soal pipeline intent/ekspresi terpisah) | `[docs]`/`[inferred]` murni |

## Tier 3 — indeks

| Nama | Arketipe | Tier | Ciri khas | Multilingual | Label sumber |
|---|---|---|---|---|---|
| Open WebUI | In-App Copilot (05) + Workspace Agent (01) | T3 | Chat UI self-hosted multi-user dengan RBAC, model routing, dan dukungan tool/function-calling plugin — alternatif LibreChat dengan penekanan admin/RBAC | Ada (UI i18n) — belum diverifikasi kedalamannya | `[inferred]` |
| Onyx (eks-Danswer) | Research/Analyst (04) + In-App Copilot (05) | T3 | Asisten enterprise search/RAG yang menyambungkan banyak connector sumber data (Slack, Confluence, Google Drive, dst) dengan sitasi wajib per jawaban | Tidak diketahui | `[inferred]` |
| assistant-ui | Infrastruktur — bukan agent, komponen React | T3 | Library komponen chat/artefak yang bisa disambungkan ke berbagai backend agent (termasuk `ai-chatbot`); dipakai untuk membangun antarmuka kanvas, bukan menjalankan agent sendiri | Tidak ada | `[inferred]` |
| Mem0 | Infrastruktur — lapisan memori | T3 | Library memori pluggable (vector + graph) yang bisa dipasang ke agent apa pun; alternatif pola memory-block Letta dengan API lebih generik/framework-agnostic | Tidak diketahui | `[inferred]` |
| Zep | Infrastruktur — lapisan memori | T3 | Layanan memori lintas-sesi berbasis temporal knowledge graph; menekankan "fakta yang berubah seiring waktu" (versioning fakta), bukan cuma ringkasan statis | Tidak diketahui | `[inferred]` |
| E2B | Infrastruktur — sandbox eksekusi kode | T3 | Sandbox cloud (microVM Firecracker) untuk eksekusi kode agent, API "buka sandbox → jalankan kode → ambil hasil" per sesi, isolasi kuat per-run | Tidak berlaku (infra, bukan agent) | `[inferred]` |
| Daytona | Infrastruktur — sandbox/dev environment | T3 | Environment dev terisolasi yang bisa di-provision cepat untuk agent coding (dirujuk juga di `deepagents.md` sebagai `libs/partners/daytona`, belum diverifikasi API persisnya) | Tidak berlaku | `[inferred]` |
| microsandbox | Infrastruktur — sandbox ringan | T3 | MicroVM ringan (self-hosted) untuk isolasi eksekusi kode agent tanpa overhead kontainer penuh, alternatif E2B yang bisa dijalankan sendiri | Tidak berlaku | `[inferred]` |
| Langfuse | Infrastruktur — observability/tracing | T3 | Platform tracing+eval open-source untuk aplikasi LLM: trace per-turn, skor eval, atribusi biaya per user/sesi | Tidak berlaku | `[inferred]` |
| Phoenix (Arize) | Infrastruktur — observability/tracing | T3 | Tracing+eval open-source berbasis OpenTelemetry/OpenInference, penekanan pada eval offline dan drift dataset | Tidak berlaku | `[inferred]` |
| OpenLLMetry | Infrastruktur — instrumentasi tracing | T3 | Library instrumentasi OpenTelemetry khusus panggilan LLM/vector-DB/framework agent — dipakai *di dalam* aplikasi lain (bukan platform berdiri sendiri) untuk mengirim trace ke backend observability manapun | Tidak berlaku | `[inferred]` |
| vLLM | Infrastruktur — serving GPU-bound | T3 | Engine inferensi LLM throughput-tinggi (PagedAttention, continuous batching) — lapisan serving di bawah gateway seperti LiteLLM, bukan gateway itu sendiri | Tidak berlaku | `[inferred]` |
| SGLang | Infrastruktur — serving GPU-bound | T3 | Engine serving LLM dengan penekanan structured generation cepat (constrained decoding) dan RadixAttention untuk cache prefix lintas-request | Tidak berlaku | `[inferred]` |
| Ray Serve | Infrastruktur — serving umum | T3 | Framework model-serving umum (bukan khusus LLM) di atas Ray, autoscaling berbasis beban aktual per deployment — dirujuk §8.3 spec desain sebagai contoh serving berbasis sinyal bukan RPS naif | Tidak berlaku | `[inferred]` |
| KEDA | Infrastruktur — autoscaler K8s | T3 | Kubernetes event-driven autoscaler; menskalakan pod berdasar metrik kustom (mis. queue depth, in-flight turns) — pas dengan aturan §8.3 "sinyal HPA bukan RPS" | Tidak berlaku | `[inferred]` |
| SWE-agent | Workspace Agent (01) | T3 | Agent penyelesai issue GitHub otomatis; memperkenalkan istilah "Agent-Computer Interface" (ACI) — tool didesain ulang supaya cocok kognisi model, bukan sekadar API mentah untuk manusia | Tidak diketahui | `[inferred]` |
| Cline | Workspace Agent (01) | T3 | Extension VS Code untuk coding agent otonom (antarmuka IDE, bukan CLI/terminal seperti Aider/Claude Code); menonjolkan plan/act mode terpisah di UI | Tidak diketahui | `[inferred]` |
| n8n | Workflow Agent (06) | T3 | Platform automasi workflow visual (node-based) dengan node AI-agent tersambung — mirip Dify-workflow tapi berakar dari automasi non-AI (integrasi API luas), bukan dibangun untuk LLM sejak awal | Tidak diketahui | `[inferred]` |
| Stagehand | Computer-Use Agent (07) | T3 | Wrapper AI di atas Playwright — action berbasis natural-language dipetakan ke primitif Playwright deterministik, penekanan pada dapat-di-debug/dapat-diulang dibanding browser-use yang lebih agentic penuh | Tidak diketahui | `[inferred]` |

## Catatan multilingual

Dari sembilan sistem T2 yang dibaca sampai ke source, **hanya Dify** yang
punya i18n melampaui string UI murni (email transaksional ikut
diterjemahkan) — tapi bahkan itu tetap **lokalisasi output**, bukan pipeline
pemisahan intent/ekspresi yang diargumentasikan
`references/concepts/multilingual.md` dan dikunci §8.6 spec desain
(klasifikasi intent → kode netral → lookup policy/skill by kode →
render output di locale user). OpenHands dan LibreChat punya i18n UI
(`i18next`) tapi tidak ditemukan lapisan classifier-intent terpisah dari
routing skill/agent. Lima sistem T2 lain (Aider, `ai-chatbot`, LiteLLM,
Letta, browser-use) **tidak** punya direktori/paket i18n sama sekali di
source yang dikloning — dikonfirmasi lewat `find -iname "*i18n*"` /
`*locale*` per repo, bukan diasumsikan. Claude Code tidak diketahui karena
closed-source dan tidak ditemukan halaman dokumentasi yang membahas
pipeline intent/ekspresi terpisah dari routing skill berbasis deskripsi.

**Temuan**: ketiadaan desain multilingual eksplisit adalah **norma**, bukan
pengecualian, di grid ini — persis argumen pembuka `multilingual.md` bahwa
kebanyakan harness memperlakukan bahasa sebagai fitur UI (terjemahkan
string tombol/label) dan bukan sebagai dimensi arsitektur (locale sebagai
konteks kelas satu yang memengaruhi trigger skill, leksikon guardrail, dan
kalibrasi budget token). Tidak satu pun dari sembilan sistem T2 di grid ini
mengimplementasikan pemisahan intent/kode-netral seperti yang diargumentasikan
`references/concepts/skill-composition.md` §`intents` memakai kode
netral — pola itu ditandai `[ours]` di KB ini justru karena tidak
ditemukan preseden industrinya di sembilan sistem yang diperiksa.
