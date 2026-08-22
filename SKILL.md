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

1. Workspace Agent
2. Generative Builder
3. General Task Agent
4. Research/Analyst
5. In-App Copilot
6. Workflow Agent
7. Computer-Use Agent

## 5 bidang `concepts/`

Cakupan ditentukan bidang, bukan topik yang kebetulan terpikirkan.

- **Cognition** — agent-loop, planning, delegation, context-engineering, memory, policy-as-data, skill-composition
- **Interface** — tool-design, mcp, streaming-protocol, human-in-the-loop, structured-output, multilingual
- **Data** — session-state, persistence-schema, artifacts-and-canvas, retention-and-deletion
- **Runtime** — serving-topology, resource-profiling, isolation-and-scoping, sandboxing, queueing-and-backpressure, scaling
- **Assurance** — observability, evaluation, cost-control, guardrails, security, replay-and-forensics

## Keluaran

Keluaran akhir dari skill ini adalah **Harness Blueprint**, lalu **scaffold** —
bukan penjelasan.
