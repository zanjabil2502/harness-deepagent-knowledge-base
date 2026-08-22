# LibreChat

> Label tiap klaim: [code] / [docs] / [inferred]

Tier **T2**. LibreChat sendiri (`danny-avila/LibreChat`, Node/Express +
MongoDB + React) adalah lapisan BE multi-user: auth, transcript, endpoint
registry, UI Agent Builder. Loop agent aktualnya **tidak** hidup di repo itu —
`api/package.json` mendeklarasikan dependensi `@librechat/agents": "^3.6.9"`,
paket terpisah dari repo `danny-avila/agents` (dibangun di atas
`@langchain/langgraph`). File ini membaca **keduanya**: `LibreChat` untuk
sumbu 5 (schema transcript/agent) dan `danny-avila/agents` untuk sumbu 1-2-4-6
(loop, kompaksi, delegasi, HITL) — karena itulah kode yang benar-benar
mengeksekusinya. `[code]` — `api/package.json` baris 50-52 (repo
`danny-avila/LibreChat`, `git clone --depth 1`, 2026-08-23).

## Arketipe

**Workspace Agent (01)** dari sisi endpoint "Agents" (tool bash/file lewat
MCP, lihat sumbu 3), berhimpitan dengan **In-App Copilot (05)** karena
LibreChat pada dasarnya chat multi-user multi-provider dengan agent sebagai
salah satu endpoint di antara endpoint chat biasa (OpenAI/Anthropic/dst).
Antarmuka: chat web (React) + REST API; kendali manusia lewat HITL
`askUserQuestion` interrupt (sumbu 6), bukan approval per-tool-call default.
`[code]` — `packages/data-schemas/src/schema/agent.ts` (field `tools`,
`skills`, `provider`, `model` — konfigurasi endpoint agent per dokumen Mongo),
`librechat-agents/src/hitl/`.

## 1. Loop shape

ReAct di atas `@langchain/langgraph` `StateGraph`. `Graph.ts` membangun
workflow: `.addEdge(START, agentNode).addConditionalEdges(agentNode,
routeMessage).addEdge(summarizeNode, agentNode).addEdge(toolNode,
agentContext.toolEnd ? END : agentNode)`. `[code]` —
`danny-avila/agents` `src/graphs/Graph.ts` baris 5062-5066.

`routeMessage(state, config)` — fungsi murni yang menentukan edge berikutnya:
1. Kalau ada *pending preempt return* terdaftar untuk `agentId` ini (giliran
   yang disela lalu dilanjutkan), kembali ke `agentNode` di superstep Pregel
   yang **sama** (bukan restart graph) — supaya model melanjutkan sebagai
   satu pesan asisten, bukan pesan baru.
2. Kalau `state.summarizationRequest != null`, rute ke `summarizeNode`.
3. Selain itu, panggil `toolsCondition(state, toolNode, invokedToolIds)` —
   pola LangGraph standar: ada `tool_calls` → `toolNode`, tidak ada → `END`.

`[code]` — `src/graphs/Graph.ts` baris 4853-4872. Siapa yang memutuskan
berhenti: **model** (tidak lagi memanggil tool), diperiksa lewat kondisi
`toolsCondition`, bukan `deepagents` (limit iterasi eksplisit) atau OpenHands
(`FinishTool` eksplisit) — LibreChat/`@librechat/agents` tidak menonjolkan
tool "finish" khusus di modul yang dibaca. `[inferred]` — dari tidak
ditemukannya tool bernama `finish`/`done` di direktori `src/tools/` yang
dilihat (`local/`, `search/`, `cloudflare/`, `subagent/`).

Kalau `agentContext.toolEnd === true`, `toolNode` langsung ke `END` — mode
"satu tool call lalu berhenti" (dipakai untuk agent single-tool, bukan
default multi-turn ReAct). `[code]` — `src/graphs/Graph.ts` baris 5066.

## 2. Context

`summarizeNode` — node graph terpisah, dipicu lewat field state
`summarizationRequest` (bukan middleware yang menyisip otomatis di tiap
langkah seperti `SummarizationMiddleware` `deepagents`; di sini kompaksi
adalah **edge graph eksplisit**: `agentNode → routeMessage → summarizeNode →
agentNode`). `[code]` — `src/graphs/Graph.ts` baris 4868-4870, 5065;
`src/summarization/node.ts` (1712 baris, tidak dibaca detail penuh — nama
modul & titik pemanggilan dikonfirmasi).

Tidak ditemukan pola filesystem-as-memory (evict hasil tool besar ke path
yang bisa dibaca ulang) di direktori `src/summarization/` atau `src/tools/`
yang dibaca — kompaksi di sini murni ringkas-pesan-lama-jadi-summary di dalam
state graph, bukan pemindahan ke penyimpanan eksternal. `[inferred]`.

## 3. Tool surface

Direktori `src/tools/` berisi kategori tool bawaan yang relatif sedikit dan
luas: `local/` (eksekusi lokal), `search/`, `cloudflare/` (tool provider
pihak ketiga), `subagent/` (tool delegasi, lihat sumbu 4) — bukan katalog
besar tool sempit satu-fungsi. `[code]` — listing
`danny-avila/agents/src/tools/*`. Di sisi LibreChat sendiri, agent Mongo
document punya field `tools: [String]` (daftar nama tool terpilih) dan
`tool_kwargs` — tool surface tiap agent **dikonfigurasi per-agent** lewat UI
Agent Builder, bukan satu tool set global tetap. `[code]` —
`packages/data-schemas/src/schema/agent.ts` baris 43-52.

## 4. Delegation

Ada dua jalur delegasi berbeda, tidak flat:

- **Subagent task-delegation** — `src/tools/subagent/` berisi
  `SubagentExecutor.ts` (4086 baris), `SubagentExecutionRegistry.ts`,
  `SubagentReplay.ts`, `InMemorySubagentTaskStore.ts`, `runtimeLimits.ts`.
  `SubagentExecutionRegistry` melacak eksekusi subagent lewat
  `SubagentExecutionAddress` (`baseChildThreadId`, `branchChildThreadId`,
  `currentChildRunId`) dan `SubagentExecutionIdentity` — tiap panggilan
  subagent punya **thread LangGraph checkpoint tersendiri**
  (`SUBAGENT_THREAD_ID_PREFIX = 'subagent:'`), bukan sekadar pemanggilan
  fungsi sinkron. `[code]` —
  `src/tools/subagent/SubagentExecutionRegistry.ts` baris 1-40.
- **Multi-agent handoff** — `MultiAgentGraph` (`extends StandardGraph`)
  mengklasifikasi edge jadi `handoffEdges` vs edge langsung
  (`handoffSourceIds`). Agent dengan **hanya** edge handoff bisa merutekan
  dinamis ke tujuan mana pun; agent dengan **keduanya** (handoff + direct)
  memakai `Command` LangGraph untuk routing eksklusif — kalau terjadi
  handoff, hanya tujuan handoff yang jalan; kalau tidak, edge langsung jalan
  (berpotensi paralel). Pemilihan tujuan handoff adalah **panggilan tool
  bernama handoff** oleh model (`handoff_instructions` disuntik ke prompt) —
  bukan classifier terpisah. `[code]` — `src/graphs/MultiAgentGraph.ts`
  baris 38, 95, 292-304, 397-428.

**Hasil kembali ke pemanggil**: subagent punya thread/checkpoint sendiri yang
bisa di-*replay* (`SubagentReplay.ts`, `SUBAGENT_RESUME_ATTEMPT_CONFIG_KEY`)
— strukturnya mendukung resume granular per-subagent, tapi isi kontrak
persis "apa yang masuk balik ke `ToolMessage` pemanggil" tidak dibaca sampai
detail implementasi `SubagentExecutor.executeTask`-setara. `[inferred]` —
struktur registry & replay dikonfirmasi `[code]`, isi pemetaan hasil tidak
diverifikasi lebih jauh di task ini.

## 5. State & resume

Transkrip LibreChat adalah **tree**, bukan list: skema Mongo `message.ts`
punya field `parentMessageId` eksplisit — percabangan lewat edit pesan
menghasilkan node anak baru dari parent yang sama, persis pola yang
`references/concepts/persistence-schema.md` argumentasikan sebagai wajib
untuk lapisan transcript. `[code]` —
`packages/data-schemas/src/schema/message.ts` baris 41 (field
`parentMessageId`), `packages/data-schemas/src/schema/convo.ts`.

Dokumen `agent` Mongo (`agent.ts`) menyimpan `recursion_limit` per-agent —
batas resmi mirip `max_iteration_per_run` OpenHands / `recursion_limit`
`deepagents`, tapi di sini **field data**, dikonfigurasi per-agent lewat UI,
bukan default global tunggal. `[code]` —
`packages/data-schemas/src/schema/agent.ts` (field `recursion_limit`).

Resume subagent granular via `SubagentReplay`/`SubagentExecutionRegistry`
(sumbu 4) — checkpoint per-child-thread LangGraph, terpisah dari checkpoint
thread utama. `[code]` — lihat sumbu 4.

## 6. Safety gate

HITL berbasis **interrupt terstruktur bertipe**, bukan approval umum per
tool: modul `src/hitl/` mengimplementasikan `askUserQuestion` (satu
pertanyaan) dan `askUserQuestions`/`askUserQuestionsInterrupt` (batch, maks
**4** pertanyaan per interaksi — konstanta `MAX_ASK_USER_QUESTIONS = 4`).
Payload divalidasi lewat type guard runtime
(`isAskUserQuestionOption`/`isAskUserQuestionOptions`) sebelum interrupt
dikirim ke klien — bukan dipercaya mentah dari output model. Kunci jawaban
divalidasi lewat regex `ASK_USER_QUESTION_ID_PATTERN =
/^[A-Za-z][A-Za-z0-9_-]{0,63}$/`. `[code]` —
`src/hitl/askUserQuestionsInterrupt.ts` (utuh, baris 1-50 dibaca +
konstanta).

Ini pola gate untuk **klarifikasi**, berbeda dari gate **approval-sebelum-
eksekusi-tool** yang jadi pola default `deepagents` (`interrupt_on`) dan
OpenHands (`ConfirmationPolicy`) — tidak ditemukan modul approval-per-tool
setara di `src/hitl/` yang dibaca; kemungkinan approval tool ditangani di
level LibreChat (BE) lewat MCP tool-approval UI, bukan di paket
`@librechat/agents` ini. `[inferred]` — dari cakupan modul `hitl/` yang
hanya berisi tiga file `askUserQuestion*`.

Sandbox: eksekusi tool lokal (`src/tools/local/`) tidak diverifikasi lebih
jauh soal isolasi proses/OS di task ini — nama direktori dikonfirmasi, isi
tidak dibaca. `[code]` (listing) / tidak ada klaim isolasi tanpa verifikasi
lebih lanjut.

## 7. Capability routing & policy

**Manifest deklaratif untuk konfigurasi agent + judgment model untuk
routing/handoff runtime — bukan classifier terpisah.**

- **Level konfigurasi (siapa agent ini, tool apa yang ia punya)**: dokumen
  Mongo `agent` — `name`, `description`, `instructions`, `provider`,
  `model`, `tools: [String]`, `skills: [String]`, `skills_enabled: Boolean`,
  `recursion_limit` — dibuat lewat UI Agent Builder, disimpan sebagai data,
  bukan diputuskan model saat runtime. Ini pola manifest yang sejalan dengan
  argumen `references/concepts/policy-as-data.md`: konfigurasi tool/skill
  per-agent adalah aturan yang bisa diverifikasi, ditaruh sebagai data bukan
  prosa. `[code]` — `packages/data-schemas/src/schema/agent.ts`.
- **Level runtime (agent mana yang menangani giliran berikutnya, dalam
  topologi multi-agent)**: judgment model murni lewat tool call handoff —
  `handoff_instructions` disuntik ke prompt, model memanggil tool handoff
  bernama tujuan; `MultiAgentGraph` hanya menyediakan *edge* yang sudah
  dideklarasikan (`handoffEdges`), tidak ada classifier yang memilihkan
  otomatis. `[code]` — `src/graphs/MultiAgentGraph.ts` baris 38, 95,
  292-304.
- Pemilihan **agent/endpoint** di level percakapan (agent Workspace vs
  endpoint chat biasa) adalah pilihan eksplisit user di UI, bukan
  classifier atau judgment model — di luar cakupan `danny-avila/agents`.
  `[inferred]` — dari struktur skema `agent`/`convo` yang menyimpan
  `endpoint`/`agent_id` per percakapan, bukan hasil klasifikasi.

## Sumber

Dua repo dikloning shallow (`git clone --depth 1`) 2026-08-23 dan dibaca
langsung sebagai file:

- `danny-avila/LibreChat` (`github.com/danny-avila/LibreChat`):
  - `api/package.json` baris 50-52 (dependensi `@librechat/agents`)
  - `packages/data-schemas/src/schema/agent.ts` baris 1-60 (skema field
    `tools`, `skills`, `recursion_limit`, `provider`, `model`)
  - `packages/data-schemas/src/schema/message.ts` baris 41 (`parentMessageId`)
  - `packages/data-schemas/src/schema/convo.ts` (listing, dikutip untuk
    korelasi transcript-tree)
  - `api/app/clients/`, `api/server/services/Agents/`,
    `api/server/controllers/agents/` (listing direktori, isi tidak dibaca
    detail — dipakai untuk mengonfirmasi bahwa loop agent aktual tidak ada
    di repo ini)
- `danny-avila/agents` (`github.com/danny-avila/agents`, npm
  `@librechat/agents@3.6.9`, resolusi repo dikonfirmasi lewat
  `registry.npmjs.org/@librechat/agents`):
  - `src/graphs/Graph.ts` baris 4853-4906, 5030-5066 (`routeMessage`,
    `StateGraph` wiring)
  - `src/graphs/MultiAgentGraph.ts` baris 38-45, 95-100, 292-304, 397-428
    (handoff vs direct edge, docstring pola)
  - `src/hitl/askUserQuestionsInterrupt.ts` baris 1-50 (utuh untuk bagian
    yang dikutip)
  - `src/tools/subagent/SubagentExecutionRegistry.ts` baris 1-40
  - `src/summarization/node.ts`, `src/tools/subagent/SubagentExecutor.ts`,
    `SubagentReplay.ts`, `InMemorySubagentTaskStore.ts`, `runtimeLimits.ts`
    (listing + `wc -l`, isi tidak dibaca detail penuh)

Catatan kejujuran: `SubagentExecutor.ts` (4086 baris) dan `Graph.ts` (5500
baris) adalah file besar yang **tidak** dibaca utuh — klaim di file ini
dibatasi pada baris yang benar-benar dikutip di atas. Mekanisme approval
tool-level di luar `askUserQuestion*` (kalau ada) tidak ditemukan di paket
`@librechat/agents`; kemungkinan berada di kode LibreChat BE yang tidak
dibaca detail di task ini.
