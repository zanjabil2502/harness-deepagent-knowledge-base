# Agent Harness Engineering KB — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) atau superpowers:executing-plans untuk mengeksekusi plan ini task demi task. Step memakai checkbox (`- [ ]`).

**Goal:** Membangun Claude Code Skill berisi knowledge base yang, diberi deskripsi project apa pun, menghasilkan klasifikasi arketipe → Harness Blueprint → scaffold project production-grade berbasis deepagents.

**Architecture:** `SKILL.md` tipis sebagai router + prosedur diagnostik; `references/` sebagai kedalaman yang dimuat sesuai kebutuhan, dibagi empat kelas file (`archetypes/`, `concepts/`, `systems/`, `scaffolds/`). Setiap kelas punya kerangka section wajib yang divalidasi otomatis oleh `tools/check_kb.py`, sehingga cakupan ditentukan kerangka dan bukan oleh topik yang kebetulan terpikirkan.

**Tech Stack:** Markdown (isi KB), Python 3.11+ (validator + recipes deepagents), `deepagents` (Python), FastAPI + Postgres (target scaffold).

**Spec:** `docs/superpowers/specs/2026-08-23-agent-harness-kb-design.md`

## Global Constraints

Berlaku untuk **semua** task di bawah.

- **Bahasa isi KB:** Indonesia. Istilah teknis dan identifier kode tetap bentuk aslinya.
- **Label sumber wajib.** Setiap klaim faktual tentang sebuah sistem diberi label `[code]` (dibaca dari source), `[docs]` (dokumentasi resmi), atau `[inferred]` (disimpulkan dari perilaku produk closed). File tanpa label sama sekali = gagal validasi.
- **`SKILL.md` maksimum 150 baris.** Kedalaman tinggal di `references/`.
- **Tidak boleh ada link internal mati.** Divalidasi otomatis.
- **Asumsi A1–A5 dari spec §13 berlaku:** cloud + on-prem; API key operator dengan kuota per user (BYOK opsional); Python + FastAPI; multi-user (`user_id`) dengan multi-tenant sebagai jalur migrasi; scope Python saja.

### Kerangka section wajib per kelas file

Dipakai persis, termasuk penomoran dan tanda baca — validator mencocokkan string.

**`references/archetypes/NN-*.md`**
```
## Definisi
## Posisi di 6 sumbu
## Konsekuensi harness
## Sistem contoh
## Jebakan khas
## Bangun ini pakai deepagents
## Sumber
```

**`references/concepts/*.md`**
```
## Masalah
## Pola
## Trade-off
## Di deepagents
## Sumber
```

**`references/systems/*.md`** (kecuali `_template.md`, `INDEX.md`)
```
## Arketipe
## 1. Loop shape
## 2. Context
## 3. Tool surface
## 4. Delegation
## 5. State & resume
## 6. Safety gate
## 7. Capability routing & policy
## Sumber
```

File bernama `README.md`, `_template.md`, dan `INDEX.md` dikecualikan dari cek kerangka.

---

### Task 1: Validator + fondasi skill

Validator ditulis lebih dulu supaya semua task berikutnya punya gerbang objektif.

**Files:**
- Create: `tools/check_kb.py`
- Create: `SKILL.md`
- Create: `references/blueprint-template.md`
- Create: `references/systems/_template.md`

**Interfaces:**
- Consumes: —
- Produces: `python3 tools/check_kb.py` → exit 0 jika lulus, 1 jika ada pelanggaran; dipakai sebagai step verifikasi di Task 2–10.

- [ ] **Step 1: Tulis validator**

Create `tools/check_kb.py`:

```python
#!/usr/bin/env python3
"""Validator struktur KB. Jalankan: python3 tools/check_kb.py"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "references"

FRAMES = {
    "archetypes": [
        "## Definisi", "## Posisi di 6 sumbu", "## Konsekuensi harness",
        "## Sistem contoh", "## Jebakan khas",
        "## Bangun ini pakai deepagents", "## Sumber",
    ],
    "concepts": [
        "## Masalah", "## Pola", "## Trade-off", "## Di deepagents", "## Sumber",
    ],
    "systems": [
        "## Arketipe", "## 1. Loop shape", "## 2. Context", "## 3. Tool surface",
        "## 4. Delegation", "## 5. State & resume", "## 6. Safety gate",
        "## 7. Capability routing & policy", "## Sumber",
    ],
}
EXEMPT = {"README.md", "_template.md", "INDEX.md"}
LABEL = re.compile(r"\[(code|docs|inferred)\]")
LINK = re.compile(r"\]\((?!https?:|mailto:)([^)#]+)")
SKILL_MAX_LINES = 150


def check_frames(errs):
    for group, heads in FRAMES.items():
        folder = REF / group
        if not folder.is_dir():
            errs.append(f"references/{group}/: folder belum ada")
            continue
        for f in sorted(folder.rglob("*.md")):
            if f.name in EXEMPT:
                continue
            txt = f.read_text(encoding="utf-8")
            rel = f.relative_to(ROOT)
            for h in heads:
                if h not in txt:
                    errs.append(f"{rel}: hilang section '{h}'")
            if not LABEL.search(txt):
                errs.append(f"{rel}: tidak ada label sumber [code]/[docs]/[inferred]")


def check_links(errs):
    for f in ROOT.rglob("*.md"):
        if ".git" in f.parts:
            continue
        for m in LINK.finditer(f.read_text(encoding="utf-8")):
            target = (f.parent / m.group(1).strip()).resolve()
            if not target.exists():
                errs.append(f"{f.relative_to(ROOT)}: link mati -> {m.group(1)}")


def check_skill_size(errs):
    skill = ROOT / "SKILL.md"
    if not skill.exists():
        errs.append("SKILL.md: belum ada")
        return
    n = len(skill.read_text(encoding="utf-8").splitlines())
    if n > SKILL_MAX_LINES:
        errs.append(f"SKILL.md: {n} baris, maksimum {SKILL_MAX_LINES}")


def main():
    errs = []
    check_frames(errs)
    check_links(errs)
    check_skill_size(errs)
    for e in errs:
        print("FAIL:", e)
    print(f"\n{len(errs)} masalah" if errs else "\nOK: semua cek lulus")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Jalankan validator, pastikan GAGAL**

Run: `python3 tools/check_kb.py`
Expected: FAIL — `references/archetypes/: folder belum ada`, `references/concepts/: folder belum ada`, `references/systems/: folder belum ada`, `SKILL.md: belum ada`. Exit code 1.

- [ ] **Step 3: Tulis `SKILL.md`**

Maksimum 150 baris. Wajib memuat, berurutan:
1. Frontmatter YAML: `name: agent-harness-kb`, `description` yang menyebut kapan skill ini dipakai (merancang harness agent, memilih arsitektur AI Assistant, scaffolding project agent production-grade)
2. Prosedur diagnostik dari spec §11 sebagai diagram alur teks
3. Tabel 6 sumbu pembeda (spec §6.1) sebagai alat klasifikasi cepat
4. Tabel 7 arketipe — **tulis nama saja tanpa link markdown**. Link ditambahkan di Task 2 Step 3 setelah file arketipe benar-benar ada, karena validator menolak link internal mati.
5. Peta 5 bidang `concepts/` — nama bidang dan daftar file, juga tanpa link markdown untuk alasan yang sama
6. Kalimat penutup: keluaran akhir adalah Harness Blueprint, lalu scaffold — bukan penjelasan

- [ ] **Step 4: Tulis `references/blueprint-template.md`**

Template keluaran, bukan prosa. Section: `## Ringkasan project`, `## Arketipe`, `## 7 sumbu harness`, `## State & data` (5 lapis dari spec §8.1), `## Guardrail` (6 titik dari spec §8.4, tiap baris wajib kolom kebijakan / titik penegakan / mode kegagalan), `## Deployment & resource` (spec §8.3), `## Isolation & scoping` (spec §8.2), `## Config deepagents`, `## Checklist production-readiness` (9 baris dari spec §12).

- [ ] **Step 5: Tulis `references/systems/_template.md`**

Berisi persis kerangka 9 section systems dari Global Constraints, tiap section diisi satu kalimat instruksi tentang apa yang harus dijawab, plus baris `> Label tiap klaim: [code] / [docs] / [inferred]`.

- [ ] **Step 6: Buat folder kosong agar validator bisa lanjut**

```bash
mkdir -p references/archetypes references/concepts references/scaffolds/deltas references/recipes
```

- [ ] **Step 7: Jalankan validator, pastikan LULUS**

Run: `python3 tools/check_kb.py`
Expected: `OK: semua cek lulus`, exit code 0.

- [ ] **Step 8: Commit**

```bash
git add tools/check_kb.py SKILL.md references/
git commit -m "feat: validator KB + fondasi skill (SKILL.md, blueprint & systems template)"
```

---

### Task 2: Tujuh arketipe

**Files:**
- Create: `references/archetypes/README.md`
- Create: `references/archetypes/01-workspace-agent.md`
- Create: `references/archetypes/02-generative-builder.md`
- Create: `references/archetypes/03-general-task-agent.md`
- Create: `references/archetypes/04-research-agent.md`
- Create: `references/archetypes/05-in-app-copilot.md`
- Create: `references/archetypes/06-workflow-agent.md`
- Create: `references/archetypes/07-computer-use-agent.md`

**Interfaces:**
- Consumes: kerangka section arketipe (Global Constraints); `tools/check_kb.py` dari Task 1.
- Produces: tujuh file arketipe yang di-link dari `SKILL.md`; section `## Bangun ini pakai deepagents` di tiap file menjadi rujukan Task 10 saat menyusun delta scaffold.

- [ ] **Step 1: Tulis `references/archetypes/README.md`**

Isi: tabel 6 sumbu pembeda (spec §6.1), tabel 7 arketipe (spec §6.2), matriks hibrida dengan minimal tiga contoh nyata (Cursor = 1+5, Manus = 3+7, dan satu lagi), serta paragraf yang menegaskan dimensi deployment bersifat ortogonal terhadap arketipe (spec §6.3).

- [ ] **Step 2: Tulis ketujuh file arketipe**

Tiap file mengikuti kerangka 7 section. Isi minimum per section:
- `## Definisi` — satu paragraf, plus batas tegas terhadap arketipe tetangga
- `## Posisi di 6 sumbu` — tabel, satu baris per sumbu
- `## Konsekuensi harness` — minimal 4 keputusan yang dipaksa arketipe ini, tiap keputusan menyebut alasannya
- `## Sistem contoh` — minimal 3, tiap entri berlabel sumber
- `## Jebakan khas` — minimal 3 kegagalan nyata yang spesifik untuk arketipe ini
- `## Bangun ini pakai deepagents` — konfigurasi konkret: middleware apa, backend filesystem apa, subagent apa, batas loop apa
- `## Sumber` — daftar repo/dokumen dengan label

- [ ] **Step 3: Pasang link di `SKILL.md`**

Modify `SKILL.md`: ubah tabel 7 arketipe dari nama polos menjadi link markdown ke `references/archetypes/NN-*.md`, dan peta 5 bidang menjadi link ke `references/concepts/`. Sekarang aman karena file tujuannya sudah ada.

- [ ] **Step 4: Jalankan validator**

Run: `python3 tools/check_kb.py`
Expected: `OK: semua cek lulus`. Jika muncul `hilang section`, tambahkan section yang kurang persis seperti tertulis di Global Constraints. Jika muncul `link mati`, berarti nama file di `SKILL.md` tidak cocok dengan nama file sebenarnya.

- [ ] **Step 5: Commit**

```bash
git add references/archetypes/ SKILL.md
git commit -m "docs: taksonomi 7 arketipe AI Assistant"
```

---

### Task 3: deepagents tier T1 + recipes

**Files:**
- Create: `references/systems/deepagents.md`
- Create: `references/recipes/README.md`
- Create: `references/recipes/01_minimal_agent.py`
- Create: `references/recipes/02_custom_middleware.py`
- Create: `references/recipes/03_subagents.py`
- Create: `references/recipes/04_custom_backend.py`
- Create: `references/recipes/pyproject.toml`

**Interfaces:**
- Consumes: kerangka section systems (Global Constraints).
- Produces: `references/systems/deepagents.md` sebagai rujukan T1 untuk semua section `## Di deepagents` di Task 4–8; recipes yang terverifikasi jalan.

- [ ] **Step 1: Baca sumber resmi lebih dulu**

Gunakan Context7 pada `/langchain-ai/deepagents` dan `/websites/langchain_oss_python_deepagents`. Catat versi yang dibaca — versi itu ditulis eksplisit di `## Sumber`. Jangan menulis API dari ingatan.

- [ ] **Step 2: Tulis `references/systems/deepagents.md`**

Mengikuti kerangka 9 section systems, tapi lebih dalam dari file T2: setiap sumbu menyertakan nama API konkret (fungsi, kelas, parameter). Tambahkan section ekstra setelah sumbu 7: `## API permukaan` (tabel entrypoint utama), `## Middleware bawaan` (tabel: nama, titik penegakan, kapan dipakai), `## Backend filesystem` (opsi yang tersedia + implikasi multi-user).

- [ ] **Step 3: Tulis `references/recipes/pyproject.toml`**

```toml
[project]
name = "harness-kb-recipes"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["deepagents"]
```

- [ ] **Step 4: Tulis keempat recipe**

Tiap file adalah skrip Python yang berdiri sendiri, punya blok `if __name__ == "__main__":`, dan diawali docstring yang menyebut: apa yang didemokan, arketipe mana yang terbantu, dan konsep mana yang diilustrasikan.

- [ ] **Step 5: Verifikasi recipe benar-benar jalan**

Run:
```bash
cd references/recipes && uv sync && uv run python 01_minimal_agent.py
```
Expected: keempat skrip berjalan tanpa exception. Jika API berbeda dari yang ditulis, perbaiki `deepagents.md` — sumber adalah kode yang jalan, bukan sebaliknya.

- [ ] **Step 6: Jalankan validator**

Run: `python3 tools/check_kb.py`
Expected: `OK: semua cek lulus`.

- [ ] **Step 7: Commit**

```bash
git add references/systems/deepagents.md references/recipes/
git commit -m "docs: bedah deepagents tier T1 + recipes terverifikasi"
```

---

### Task 4: Bidang Data

Didahulukan sebelum bidang lain karena menjawab langsung kebingungan batas BE↔AI.

**Files:**
- Create: `references/concepts/session-state.md`
- Create: `references/concepts/persistence-schema.md`
- Create: `references/concepts/artifacts-and-canvas.md`
- Create: `references/concepts/retention-and-deletion.md`

**Interfaces:**
- Consumes: spec §8.1; `references/systems/deepagents.md` untuk section `## Di deepagents`.
- Produces: skema tabel yang dipakai ulang oleh `scaffolds/_base.md` di Task 10.

- [ ] **Step 1: Baca sumber**

Repo yang dibaca dan dilabeli `[code]`: LibreChat dan Open WebUI (skema transcript, percabangan), Vercel `ai-chatbot` (implementasi artefak/canvas), LangGraph checkpointer & store `[docs]`.

- [ ] **Step 2: Tulis `session-state.md`**

Wajib memuat: heuristik "kalau hilang, bisa dihitung ulang?"; tabel 5 lapis dari spec §8.1 lengkap dengan store, lifetime, pemilik; dan penjelasan eksplisit kenapa transcript ≠ model context.

- [ ] **Step 3: Tulis `persistence-schema.md`**

Wajib memuat DDL Postgres nyata untuk: transcript sebagai **tree** (kolom `parent_id`), tool call sebagai row kelas satu, compaction event yang menunjuk pesan yang digantikan, idempotency key per turn, dan kolom scope (`user_id`) di setiap tabel plus contoh policy RLS.

- [ ] **Step 4: Tulis `artifacts-and-canvas.md`**

Wajib memuat: aturan by-reference (transcript menyimpan `artifact_id + version`, context menyimpan handle + ringkasan), skema versioning, dan perbandingan model edit canvas rewrite-penuh vs patch beserta kapan masing-masing dipakai.

- [ ] **Step 5: Tulis `retention-and-deletion.md`**

Wajib memuat daftar cascade lengkap: transcript, checkpoint, artefak di object store, memory row, **vector index**, **trace store**. Dua terakhir ditandai sebagai yang paling sering terlewat.

- [ ] **Step 6: Jalankan validator dan commit**

```bash
python3 tools/check_kb.py && git add references/concepts/ && git commit -m "docs: concepts bidang Data (state, schema, artefak, retensi)"
```

---

### Task 5: Bidang Runtime

**Files:**
- Create: `references/concepts/serving-topology.md`
- Create: `references/concepts/resource-profiling.md`
- Create: `references/concepts/isolation-and-scoping.md`
- Create: `references/concepts/sandboxing.md`
- Create: `references/concepts/queueing-and-backpressure.md`
- Create: `references/concepts/scaling.md`

**Interfaces:**
- Consumes: spec §8.2 dan §8.3.
- Produces: keputusan topologi yang dipakai `scaffolds/serving.md` di Task 10.

- [ ] **Step 1: Baca sumber**

OpenHands (server + runtime terisolasi) `[code]`, LiteLLM (kuota & rate limit per key) `[code]`, E2B dan Daytona (isolasi eksekusi) `[code]`, KEDA dan Ray Serve `[docs]`.

- [ ] **Step 2: Tulis `resource-profiling.md`**

Wajib memuat tabel fase-dalam-satu-turn beserta bound-nya (LLM call = IO, context assembly = memory, code exec = CPU, embedding = GPU, checkpoint = IO disk), dan penjelasan kenapa satu pod memaksa scaling di dimensi terburuk.

- [ ] **Step 3: Tulis `serving-topology.md`**

Wajib memuat tabel komponen → bound → sinyal HPA dari spec §8.3, prinsip modular monolith dengan jahitan yang sudah dipotong, dan tiga masalah turn panjang: timeout HTTP default, rolling deploy yang memutus turn in-flight, dan HPA berbasis RPS yang salah untuk beban IO-bound.

- [ ] **Step 4: Tulis `isolation-and-scoping.md`**

Wajib memuat tabel perbandingan multi-user vs multi-tenant, pola scope object `(user_id)` → `(tenant_id, user_id)`, dan alasan RLS dipilih di atas `WHERE` manual: satu query lupa filter = kebocoran antar user.

- [ ] **Step 5: Tulis `sandboxing.md`, `queueing-and-backpressure.md`, `scaling.md`**

Berturut-turut: batas blast radius eksekusi tool beserta opsi isolasi dan biayanya; antrean untuk turn panjang, backpressure, prioritas, dan reattach setelah client putus; sinyal scaling per komponen, cold start sandbox, serta node pool GPU dengan taint.

- [ ] **Step 6: Jalankan validator dan commit**

```bash
python3 tools/check_kb.py && git add references/concepts/ && git commit -m "docs: concepts bidang Runtime (serving, resource, isolasi, sandbox, antrean, scaling)"
```

---

### Task 6: Bidang Assurance

**Files:**
- Create: `references/concepts/guardrails.md`
- Create: `references/concepts/security.md`
- Create: `references/concepts/evaluation.md`
- Create: `references/concepts/observability.md`
- Create: `references/concepts/cost-control.md`
- Create: `references/concepts/replay-and-forensics.md`

**Interfaces:**
- Consumes: spec §8.4; `references/systems/deepagents.md` untuk pemetaan guardrail ke middleware.
- Produces: checklist guardrail yang dipakai `blueprint-template.md` dan gerbang production-readiness di Task 10.

- [ ] **Step 1: Baca sumber**

NeMo Guardrails, Guardrails AI, Llama Guard, Presidio `[docs]`; Langfuse dan OpenLLMetry `[code]`; middleware deepagents `[code]`.

- [ ] **Step 2: Tulis `guardrails.md`**

Wajib memuat tabel 6 titik penegakan dari spec §8.4; aturan **kebijakan + titik penegakan + mode kegagalan** untuk setiap guardrail dengan contoh eksplisit fail-open (moderasi) dan fail-closed (otorisasi); prinsip bertingkat dari cek deterministik murah ke model-based; dan pemetaan 1:1 ke middleware deepagents di section `## Di deepagents`.

- [ ] **Step 3: Tulis `security.md`**

Wajib memuat: prompt injection lewat hasil tool sebagai isu nomor satu, confused deputy dan penyempitan scope token, kebocoran otorisasi di retrieval multi-user, serta scan secret pada kode yang digenerate.

- [ ] **Step 4: Tulis `evaluation.md`**

Wajib memuat: eval berbasis trajektori (bukan hanya jawaban akhir), golden transcript + replay harness, guardrail sebagai objek yang diukur presisi/recall-nya, dan **kewajiban eval multibahasa** — golden test satu bahasa membuat regresi bahasa lain tak terlihat.

- [ ] **Step 5: Tulis `observability.md`, `cost-control.md`, `replay-and-forensics.md`**

Berturut-turut: span per langkah agent dan label `user_id` di setiap trace; budget per run dan per user, deteksi loop liar, atribusi biaya; serta rekam-ulang satu run untuk forensik beserta apa yang harus dicatat agar replay mungkin.

- [ ] **Step 6: Jalankan validator dan commit**

```bash
python3 tools/check_kb.py && git add references/concepts/ && git commit -m "docs: concepts bidang Assurance (guardrail, security, eval, observability, biaya, replay)"
```

---

### Task 7: Bidang Cognition

**Files:**
- Create: `references/concepts/agent-loop.md`
- Create: `references/concepts/planning.md`
- Create: `references/concepts/delegation.md`
- Create: `references/concepts/context-engineering.md`
- Create: `references/concepts/memory.md`
- Create: `references/concepts/policy-as-data.md`
- Create: `references/concepts/skill-composition.md`

**Interfaces:**
- Consumes: spec §8.5; `references/systems/deepagents.md`.
- Produces: model manifest skill yang dipakai sumbu 7 di semua file `systems/` pada Task 9.

- [ ] **Step 1: Baca sumber**

Aider (repo map) `[code]`, SWE-agent (agent-computer interface) `[code]`, Cline `[code]`, Letta dan Mem0 (memory) `[code]`, prompt caching Anthropic `[docs]`.

- [ ] **Step 2: Tulis `context-engineering.md`**

Wajib memuat trade-off yang jarang dibahas: **compaction merusak prefix prompt cache**, sehingga penghematan token dari compaction bisa kalah oleh hilangnya cache hit. Sertakan aturan urutan konteks yang ramah cache (bagian stabil di depan, bagian volatil di belakang).

- [ ] **Step 3: Tulis `policy-as-data.md`**

Wajib memuat: aturan "kalau bisa diverifikasi kode, tidak boleh hidup di prompt"; tiga penyakit prosa-sebagai-aturan (dilusi, presedensi implisit, tidak terlihat saat runtime); dan contoh policy YAML beserta titik penegakannya di middleware.

- [ ] **Step 4: Tulis `skill-composition.md`**

Wajib memuat model dasar → turunan, contoh manifest lengkap dari spec §8.5, aturan resolusi konflik lewat presedensi eksplisit, dan alasan `intents` memakai kode netral alih-alih frasa bahasa.

- [ ] **Step 5: Tulis `agent-loop.md`, `planning.md`, `delegation.md`, `memory.md`**

Berturut-turut: varian bentuk loop dan siapa yang memutuskan berhenti; planning eksplisit vs implisit beserta kapan todo list membantu dan kapan jadi beban; pola subagent, kontrak hasil balik, dan batas kedalaman; serta memory lintas sesi — ekstraksi, konflik, pembaruan, penghapusan.

- [ ] **Step 6: Jalankan validator dan commit**

```bash
python3 tools/check_kb.py && git add references/concepts/ && git commit -m "docs: concepts bidang Cognition (loop, planning, delegasi, konteks, memory, policy, skill)"
```

---

### Task 8: Bidang Interface

**Files:**
- Create: `references/concepts/tool-design.md`
- Create: `references/concepts/mcp.md`
- Create: `references/concepts/streaming-protocol.md`
- Create: `references/concepts/human-in-the-loop.md`
- Create: `references/concepts/structured-output.md`
- Create: `references/concepts/multilingual.md`

**Interfaces:**
- Consumes: spec §8.6.
- Produces: kontrak event streaming yang dipakai `scaffolds/_base.md` di Task 10.

- [ ] **Step 1: Tulis `multilingual.md`**

Wajib memuat alur pemisahan intent dari ekspresi (spec §8.6) dan tabel titik yang terkunci bahasa: trigger skill, regex guardrail (NIK/NPWP ≠ SSN), deteksi injection, golden test eval, dan kalibrasi budget token untuk bahasa non-Latin. Tegaskan locale adalah konteks kelas satu di session, bukan tebakan per turn.

- [ ] **Step 2: Tulis `streaming-protocol.md`**

Wajib memuat: perbandingan SSE vs WebSocket beserta kapan masing-masing; skema event; rendering tool call parsial; dan **reattach setelah client putus** yang mengharuskan event log durable, bukan stream ephemeral.

- [ ] **Step 3: Tulis `tool-design.md`, `mcp.md`, `human-in-the-loop.md`, `structured-output.md`**

Berturut-turut: granularitas tool dan trade-off banyak-sempit vs sedikit-luas; MCP sebagai standar interop, siklus hidup server, konfigurasi per user; gerbang persetujuan, apa yang layak dihentikan, dan bagaimana persetujuan dicatat; serta penegakan schema, strategi retry, dan hubungannya dengan guardrail output.

- [ ] **Step 4: Jalankan validator dan commit**

```bash
python3 tools/check_kb.py && git add references/concepts/ && git commit -m "docs: concepts bidang Interface (tool, MCP, streaming, HITL, output, multilingual)"
```

---

### Task 9: systems tier T2 + INDEX tier T3

**Files:**
- Create: `references/systems/openhands.md`
- Create: `references/systems/librechat.md`
- Create: `references/systems/aider.md`
- Create: `references/systems/vercel-ai-chatbot.md`
- Create: `references/systems/litellm.md`
- Create: `references/systems/letta.md`
- Create: `references/systems/dify.md`
- Create: `references/systems/browser-use.md`
- Create: `references/systems/claude-code.md`
- Create: `references/systems/INDEX.md`

**Interfaces:**
- Consumes: `references/systems/_template.md`; sumbu 7 dari `references/concepts/skill-composition.md`.
- Produces: `INDEX.md` sebagai penampung T3 yang bisa ditambah tanpa mengubah struktur.

- [ ] **Step 1: Isi kesembilan file T2 mengikuti `_template.md`**

Setiap sumbu dijawab dari source, bukan dari README repo. `claude-code.md` adalah satu-satunya yang mayoritas `[inferred]`/`[docs]` — dan justru dijadikan contoh utama pada sumbu 7 untuk pola "prosa + judgment model", termasuk kelemahannya: dilusi instruksi dan keterikatan bahasa.

- [ ] **Step 2: Tulis `INDEX.md`**

Tabel dengan kolom: Nama, Arketipe, Tier, Ciri khas (satu baris), Multilingual (ada desain eksplisit / tidak / tidak diketahui), Label sumber. Memuat kesembilan entri T2 plus minimal 15 entri T3 dari tabel kandidat spec §10.

- [ ] **Step 3: Jalankan validator dan commit**

```bash
python3 tools/check_kb.py && git add references/systems/ && git commit -m "docs: systems tier T2 (9 sistem) + INDEX tier T3"
```

---

### Task 10: Scaffolds

**Files:**
- Create: `references/scaffolds/_base.md`
- Create: `references/scaffolds/serving.md`
- Create: `references/scaffolds/deltas/01-workspace-agent.md`
- Create: `references/scaffolds/deltas/02-generative-builder.md`
- Create: `references/scaffolds/deltas/03-general-task-agent.md`
- Create: `references/scaffolds/deltas/04-research-agent.md`
- Create: `references/scaffolds/deltas/05-in-app-copilot.md`
- Create: `references/scaffolds/deltas/06-workflow-agent.md`
- Create: `references/scaffolds/deltas/07-computer-use-agent.md`

**Interfaces:**
- Consumes: skema dari Task 4, topologi dari Task 5, guardrail dari Task 6, kontrak streaming dari Task 8, section `## Bangun ini pakai deepagents` dari Task 2.
- Produces: keluaran akhir prosedur diagnostik `SKILL.md`.

- [ ] **Step 1: Tulis `_base.md`**

Struktur project production-grade yang arketipe-agnostik, sebagai **spesifikasi + snippet terverifikasi**, bukan template repo. Wajib memuat: pohon direktori; batas modul orchestrator / executor / retrieval di balik interface; async-first FastAPI; checkpointer eksternal; middleware scope `user_id` + RLS; OTel berlabel user; `/healthz` dan `/readyz`; graceful drain yang menunggu turn in-flight; Dockerfile; manifest K8s dasar.

- [ ] **Step 2: Tulis `serving.md`**

Ditulis sekali dan berlaku lintas arketipe, karena topologi ditentukan oleh tool yang dimiliki agent, bukan oleh arketipenya. Wajib memuat jalur migrasi modular monolith → microservice: apa yang berubah (binding + manifest) dan apa yang tidak (logika).

- [ ] **Step 3: Tulis ketujuh delta**

Tiap delta **hanya** menuliskan selisih terhadap `_base.md`: apa yang ditambah, apa yang diganti, apa yang dibuang. Delta yang mengulang isi `_base.md` dianggap gagal.

- [ ] **Step 4: Tambahkan gerbang production-readiness**

Di akhir `_base.md`, tulis checklist 9 syarat dari spec §12 sebagai daftar checkbox, dengan kalimat pembuka bahwa scaffold belum boleh dinyatakan selesai sebelum seluruhnya tercentang.

- [ ] **Step 5: Jalankan validator dan commit**

```bash
python3 tools/check_kb.py && git add references/scaffolds/ && git commit -m "docs: scaffolds base + serving + 7 delta arketipe"
```

---

### Task 11: Verifikasi akhir

**Files:**
- Modify: file mana pun yang gagal cek
- Create: `README.md`

**Interfaces:**
- Consumes: seluruh keluaran Task 1–10.
- Produces: KB yang siap di-symlink ke `~/.claude/skills/`.

- [ ] **Step 1: Cek cakupan spec**

Buka spec, telusuri §6 sampai §12 satu per satu, pastikan tiap keputusan punya file yang memuatnya. Catat yang bolong dan isi.

- [ ] **Step 2: Cek dominasi label `[code]`**

Run:
```bash
grep -roh '\[\(code\|docs\|inferred\)\]' references/ | sort | uniq -c
```
Expected: `[code]` adalah label terbanyak. Jika `[inferred]` mendominasi, KB berdiri di atas tebakan — kembali ke source.

- [ ] **Step 3: Cek tiap bidang punya minimal satu reference `[code]`**

Untuk kelima bidang di spec §7, pastikan minimal satu file di bidang itu memuat label `[code]`. Bidang yang tidak punya ditandai lemah secara eksplisit di `README.md`, bukan didiamkan.

- [ ] **Step 4: Tulis `README.md`**

Isi: apa ini, cara memasang (`ln -s` ke `~/.claude/skills/agent-harness-kb`), cara memakai (satu contoh dari deskripsi project sampai blueprint), cara menambah entri T3, dan cara menjalankan validator.

- [ ] **Step 5: Jalankan validator terakhir dan commit**

```bash
python3 tools/check_kb.py && git add -A && git commit -m "docs: README + verifikasi akhir KB"
```
