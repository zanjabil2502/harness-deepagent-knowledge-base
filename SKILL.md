---
name: agent-harness-kb
description: Dipakai saat merancang harness agent atau membangun di atas deepagents — bentuk loop, context engineering, tool & delegasi, guardrail, dan konstruksi deepagents yang idiomatik. Fokus pada harness itu sendiri; lapisan serving dan persistensi tersedia tapi bukan jalur utama.
---

# Agent Harness Engineering Knowledge Base

Knowledge base tentang **rekayasa harness agent** dan cara membangun di atas
**deepagents** secara idiomatik. Ambil deskripsi project apa pun, klasifikasikan
arketipe-nya, lalu susun keputusan harness-nya: bentuk loop, pengelolaan konteks,
permukaan tool, delegasi, dan guardrail.

**Batas fokus.** Jalur utama skill ini berhenti di harness dan konstruksi
deepagents. Lapisan **serving dan persistensi** (skema, RLS, topologi, scaling)
ada lengkap di `concepts/` bidang Data & Runtime, tapi **bukan jalur utama** —
buka hanya ketika project sudah sampai ke sana. Mencampurnya di awal membuat
keputusan harness tenggelam oleh keputusan infrastruktur.

## Prosedur diagnostik

```
deskripsi project (bentuk apa pun)
   ↓ isi 6 sumbu pembeda
Arketipe (bisa hibrida)
   ↓ archetypes/NN-*.md → batasan harness yang dipaksa arketipe
   ↓ cek silang concepts/ (Cognition · Interface · Assurance) + systems/INDEX.md
HARNESS BLUEPRINT                      → blueprint-template.md
   ├─ loop shape        — siapa yang memutuskan berhenti?
   ├─ context           — kompaksi vs prompt caching, apa yang masuk konteks
   ├─ tool surface      — banyak tool sempit vs sedikit tool luas
   ├─ delegation        — subagent? kontrak hasil balik? batas kedalaman?
   ├─ capability & policy — manifest deklaratif vs prosa + judgment model
   └─ guardrail         — 6 titik, tiap satu: kebijakan + titik + mode kegagalan
   ↓
KONSTRUKSI DEEPAGENTS                  ← ujung jalur utama
   deepagents/lifecycle.md    — di mana bisa menyisip
   deepagents/middleware.md   — urutan & interaksi berbahaya
   deepagents/extension-points.md — jangan tulis custom di lapisan yang sudah punya hook
   deepagents/per-archetype.md    — konstruksi yang benar per arketipe
   deepagents/conformance.md      — apakah polanya idiomatik vs praktik maintainer

── batas fokus ────────────────────────────────────────────────
Di bawah ini baru relevan setelah harness diputuskan:
   serving & persistensi  → concepts/ bidang Data & Runtime
   scaffold project       → scaffolds/_base.md + deltas/ + serving.md
   gerbang rilis          → checklist production-readiness
```

Setiap tahap di atas mendarat di sini:

| Tahap | Rujukan |
|---|---|
| Klasifikasi arketipe | daftar "7 arketipe" di bawah |
| Cek silang concepts | daftar "5 bidang `concepts/`" di bawah |
| Cek silang systems | [systems/INDEX.md](references/systems/INDEX.md) |
| Blueprint (kontrak, keluaran #1) | [blueprint-template.md](references/blueprint-template.md) |
| **Lifecycle deepagents — alur satu turn** | [deepagents/lifecycle.md](references/deepagents/lifecycle.md) |
| **Middleware — urutan & interaksi berbahaya** | [deepagents/middleware.md](references/deepagents/middleware.md) |
| **Titik ekstensi + anti-pattern** | [deepagents/extension-points.md](references/deepagents/extension-points.md) |
| **Konstruksi per arketipe** | [deepagents/per-archetype.md](references/deepagents/per-archetype.md) |
| **Handler & pola error** | [deepagents/handlers.md](references/deepagents/handlers.md) |
| Config deepagents — API lengkap | [deepagents/api-reference.md](references/deepagents/api-reference.md) |
| Config deepagents — kesesuaian vs vanilla | [deepagents/conformance.md](references/deepagents/conformance.md) |
| Internal deepagents — apa memanggil apa | [graphify-out/GRAPH_REPORT.md](graphify-out/GRAPH_REPORT.md) |
| Dokumentasi upstream verbatim (bahan `[docs]`) | [upstream/deepagents-docs/](references/upstream/deepagents-docs/README.md) |
| Scaffold base (keluaran #2, lapis 1) | [scaffolds/_base.md](references/scaffolds/_base.md) |
| Scaffold delta per arketipe (lapis 2) | [scaffolds/deltas/](references/scaffolds/deltas/) |
| Scaffold serving/deploy (lapis 3) | [scaffolds/serving.md](references/scaffolds/serving.md) |
| Ringkasan proyek, label sumber, instalasi | [README.md](README.md) |

## 6 sumbu pembeda (klasifikasi cepat)

| Sumbu | Pertanyaan |
|---|---|
| Blast radius | Menyentuh apa? mesin user / sandbox / data SaaS / dunia luar |
| Artefak | Output-nya apa? edit yang ada / bikin baru / jawaban / aksi di sistem lain |
| Horizon | Sekali jalan / satu sesi / hidup di background |
| Kendali manusia | Approve tiap langkah / review di akhir / tanpa manusia |
| Permukaan domain | General atau vertikal |
| Antarmuka | CLI / IDE / kanvas / chat / API tertanam |

Potongan utama untuk klasifikasi awal: **artefak × blast radius**.

## 7 arketipe

Hibrida normal dan dicatat eksplisit (mis. Cursor = Workspace Agent + In-App
Copilot, Manus = General Task Agent + Computer-Use Agent).

1. [Workspace Agent](references/archetypes/01-workspace-agent.md)
2. [Generative Builder](references/archetypes/02-generative-builder.md)
3. [General Task Agent](references/archetypes/03-general-task-agent.md)
4. [Research/Analyst](references/archetypes/04-research-agent.md)
5. [In-App Copilot](references/archetypes/05-in-app-copilot.md)
6. [Workflow Agent](references/archetypes/06-workflow-agent.md)
7. [Computer-Use Agent](references/archetypes/07-computer-use-agent.md)

## Bidang `concepts/` — inti harness dulu

Cakupan ditentukan bidang, bukan topik yang kebetulan terpikirkan.

- **Cognition** — [agent-loop](references/concepts/agent-loop.md), [planning](references/concepts/planning.md), [delegation](references/concepts/delegation.md), [code-orchestration](references/concepts/code-orchestration.md), [context-engineering](references/concepts/context-engineering.md), [memory](references/concepts/memory.md), [policy-as-data](references/concepts/policy-as-data.md), [skill-composition](references/concepts/skill-composition.md)
- **Interface** — [tool-design](references/concepts/tool-design.md), [mcp](references/concepts/mcp.md), [streaming-protocol](references/concepts/streaming-protocol.md), [human-in-the-loop](references/concepts/human-in-the-loop.md), [structured-output](references/concepts/structured-output.md), [multilingual](references/concepts/multilingual.md)
- **Assurance** — [guardrails](references/concepts/guardrails.md), [evaluation](references/concepts/evaluation.md), [security](references/concepts/security.md), [observability](references/concepts/observability.md), [cost-control](references/concepts/cost-control.md), [replay-and-forensics](references/concepts/replay-and-forensics.md)

### Lapis kedua — buka saat project sampai ke serving & persistensi

Bukan jalur utama. Keputusan di sini baru relevan setelah bentuk harness-nya
diputuskan; membukanya lebih awal menenggelamkan keputusan harness.

- **Data** — [session-state](references/concepts/session-state.md), [persistence-schema](references/concepts/persistence-schema.md), [artifacts-and-canvas](references/concepts/artifacts-and-canvas.md), [retention-and-deletion](references/concepts/retention-and-deletion.md)
- **Runtime** — [serving-topology](references/concepts/serving-topology.md), [resource-profiling](references/concepts/resource-profiling.md), [isolation-and-scoping](references/concepts/isolation-and-scoping.md), [sandboxing](references/concepts/sandboxing.md), [queueing-and-backpressure](references/concepts/queueing-and-backpressure.md), [scaling](references/concepts/scaling.md)

## Keluaran

Keluaran akhir dari skill ini adalah **Harness Blueprint**, lalu **scaffold** —
bukan penjelasan.
