---
name: agent-harness-kb
description: Dipakai saat merancang harness agent, memilih arsitektur AI Assistant, atau melakukan scaffolding project agent production-grade — dari deskripsi project apa pun sampai Harness Blueprint dan scaffold siap pakai.
---

# Agent Harness Engineering Knowledge Base

Knowledge base tentang rekayasa harness agent. Ambil deskripsi project apa pun,
klasifikasikan arketipe-nya, susun Harness Blueprint, lalu scaffold project
production-grade dari blueprint itu.

## Prosedur diagnostik

```
deskripsi project (bentuk apa pun)
   ↓ isi 6 sumbu pembeda
Arketipe (bisa hibrida)
   ↓ archetypes/NN-*.md
Batasan harness yang dipaksa arketipe
   ↓ cek silang concepts/*.md + systems/INDEX.md
HARNESS BLUEPRINT           → blueprint-template.md
   ├─ loop shape / context / tool surface / delegation
   ├─ state & resume        (§8.1)
   ├─ guardrail             (§8.4)
   ├─ deployment & resource (§8.3)
   ├─ isolation & scoping   (§8.2)
   └─ config deepagents     → deepagents/api-reference.md, conformance.md
   ↓ scaffolds/_base.md + scaffolds/deltas/NN-*.md + scaffolds/serving.md
   ↓ gerbang wajib: checklist production-readiness
PROJECT PRODUCTION-GRADE
```

Setiap tahap di atas mendarat di sini:

| Tahap | Rujukan |
|---|---|
| Klasifikasi arketipe | daftar "7 arketipe" di bawah |
| Cek silang concepts | daftar "5 bidang `concepts/`" di bawah |
| Cek silang systems | [systems/INDEX.md](references/systems/INDEX.md) |
| Blueprint (kontrak, keluaran #1) | [blueprint-template.md](references/blueprint-template.md) |
| Config deepagents — API lengkap | [deepagents/api-reference.md](references/deepagents/api-reference.md) |
| Config deepagents — kesesuaian vs vanilla | [deepagents/conformance.md](references/deepagents/conformance.md) |
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

## 5 bidang `concepts/`

Cakupan ditentukan bidang, bukan topik yang kebetulan terpikirkan.

- **Cognition** — [agent-loop](references/concepts/agent-loop.md), [planning](references/concepts/planning.md), [delegation](references/concepts/delegation.md), [context-engineering](references/concepts/context-engineering.md), [memory](references/concepts/memory.md), [policy-as-data](references/concepts/policy-as-data.md), [skill-composition](references/concepts/skill-composition.md)
- **Interface** — [tool-design](references/concepts/tool-design.md), [mcp](references/concepts/mcp.md), [streaming-protocol](references/concepts/streaming-protocol.md), [human-in-the-loop](references/concepts/human-in-the-loop.md), [structured-output](references/concepts/structured-output.md), [multilingual](references/concepts/multilingual.md)
- **Data** — [session-state](references/concepts/session-state.md), [persistence-schema](references/concepts/persistence-schema.md), [artifacts-and-canvas](references/concepts/artifacts-and-canvas.md), [retention-and-deletion](references/concepts/retention-and-deletion.md)
- **Runtime** — [serving-topology](references/concepts/serving-topology.md), [resource-profiling](references/concepts/resource-profiling.md), [isolation-and-scoping](references/concepts/isolation-and-scoping.md), [sandboxing](references/concepts/sandboxing.md), [queueing-and-backpressure](references/concepts/queueing-and-backpressure.md), [scaling](references/concepts/scaling.md)
- **Assurance** — [observability](references/concepts/observability.md), [evaluation](references/concepts/evaluation.md), [cost-control](references/concepts/cost-control.md), [guardrails](references/concepts/guardrails.md), [security](references/concepts/security.md), [replay-and-forensics](references/concepts/replay-and-forensics.md)

## Keluaran

Keluaran akhir dari skill ini adalah **Harness Blueprint**, lalu **scaffold** —
bukan penjelasan.
