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
   ↓ cek silang concepts/ + systems/
HARNESS BLUEPRINT
   ├─ loop shape / context / tool surface / delegation
   ├─ state & resume        (§8.1)
   ├─ guardrail             (§8.4)
   ├─ deployment & resource (§8.3)
   ├─ isolation & scoping   (§8.2)
   └─ config deepagents
   ↓ scaffolds/_base + delta + serving
   ↓ gerbang wajib: checklist production-readiness
PROJECT PRODUCTION-GRADE
```

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

- **[Cognition](references/concepts/)** — agent-loop, planning, delegation, context-engineering, memory, policy-as-data, skill-composition
- **[Interface](references/concepts/)** — tool-design, mcp, streaming-protocol, human-in-the-loop, structured-output, multilingual
- **[Data](references/concepts/)** — session-state, persistence-schema, artifacts-and-canvas, retention-and-deletion
- **[Runtime](references/concepts/)** — serving-topology, resource-profiling, isolation-and-scoping, sandboxing, queueing-and-backpressure, scaling
- **[Assurance](references/concepts/)** — observability, evaluation, cost-control, guardrails, security, replay-and-forensics

## Keluaran

Keluaran akhir dari skill ini adalah **Harness Blueprint**, lalu **scaffold** —
bukan penjelasan.
