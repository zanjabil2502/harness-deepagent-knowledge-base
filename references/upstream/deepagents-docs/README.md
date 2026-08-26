# Snapshot dokumentasi upstream deepagents

Salinan **verbatim** dokumentasi resmi deepagents dari
<https://docs.langchain.com/oss/python/deepagents/>.

## Kenapa ada di sini

KB ini memakai skema label sumber: `[code]` > `[docs]` > `[inferred]` > `[ours]`.
Folder ini adalah **bahan mentah untuk `[docs]`** — supaya klaim berlabel `[docs]`
bisa dilacak ke kalimat aslinya, bukan ke ingatan model. Preseden: satu klaim di KB
ini pernah berlabel `[docs]` padahal README upstream tak pernah menuliskannya —
penyebabnya peringkas LLM di WebFetch. Sejak itu aturannya: **ambil file mentah,
jangan ringkasan.** Folder ini adalah penerapan aturan itu.

Isinya bukan tulisan kita, jadi:

- **Jangan diedit.** Kalau ada yang keliru menurut source, catat di
  `references/deepagents/conformance.md`, bukan dengan menambal file di sini.
- **Bukan otoritas tertinggi.** `[code]` (baca dari source terpasang) tetap menang
  saat dokumentasi dan source bertentangan.
- Tidak ikut cek frame/label `tools/check_kb.py` — folder ini dikecualikan.

## Provenance

| | |
|---|---|
| Sumber | `https://docs.langchain.com/oss/python/deepagents/*.md` (Mintlify raw markdown) |
| Indeks | `https://docs.langchain.com/oss/python/deepagents/llms.txt` |
| Tanggal ambil | 2026-08-26 |
| Jumlah halaman | 40 |
| Versi yang dijelaskan | changelog upstream berhenti di `deepagents` v0.7.0; KB ini pin v0.7.8 — satu jalur minor yang sama |
| Cara ambil | `curl -sfL <url>.md` per halaman, tanpa peringkas |

Dua changelog di indeks (`changelog-py`, `changelog-js`) me-redirect ke halaman
kanonik `/oss/{python,javascript}/releases/changelog.md`; keduanya diambil dari URL
kanonik itu, bukan dari URL indeks yang mengembalikan HTML.

## Cara memperbarui

```bash
python3 tools/fetch_upstream_docs.py    # ambil ulang, timpa isi folder ini
git diff --stat references/upstream/    # lihat apa yang berubah upstream
```

Diff-nya sendiri yang berharga: halaman yang berubah menandai klaim `[docs]` di KB
yang perlu ditinjau ulang.

## Isi

| Berkas | Judul | Baris | Deskripsi upstream |
|---|---|---:|---|
| [`a2a.md`](a2a.md) | A2A endpoint in Agent Server | 447 | Use the A2A protocol to enable agent-to-agent communication with distributed tracing in LangSmith. |
| [`acp.md`](acp.md) | Agent Client Protocol (ACP) | 296 | Expose Deep Agents over the Agent Client Protocol (ACP) to integrate with code editors and IDEs. |
| [`async-subagents.md`](async-subagents.md) | Async subagents | 297 | Launch background subagents that run concurrently while the supervisor continues interacting with the user |
| [`backends.md`](backends.md) | Backends | 1199 | Choose and configure filesystem backends for Deep Agents. You can specify routes to different backends, implement virtual filesystems, and enforce policies. |
| [`changelog-js.md`](changelog-js.md) | Changelog | 190 | Log of updates and improvements to our JavaScript/TypeScript packages |
| [`changelog-py.md`](changelog-py.md) | Changelog | 219 | Log of updates and improvements to our Python packages |
| [`code-link.md`](code-link.md) | Deep Agents Code | 92 | Terminal coding agent built on the Deep Agents SDK |
| [`comparison.md`](comparison.md) | Comparison with Claude Agent SDK | 99 | Compare LangChain Deep Agents with the Claude Agent SDK to choose the right tool for your use case. |
| [`content-builder.md`](content-builder.md) | Build a content builder agent | 863 | Build a content writing agent with brand memory, skills, subagents, and image generation |
| [`context-engineering.md`](context-engineering.md) | Context engineering in Deep Agents | 1241 | Control what context your deep agent has access to and how it is managed across long-running tasks |
| [`customization.md`](customization.md) | Customize Deep Agents | 4150 | Learn how to customize Deep Agents with system prompts, tools, subagents, and more |
| [`data-analysis.md`](data-analysis.md) | Build a data analysis agent | 756 | Build an agent that analyzes data files, generates visualizations, and shares results |
| [`deep-research.md`](deep-research.md) | Build a deep research agent | 513 | Build a multi-step web research agent with subagent delegation |
| [`dynamic-subagents.md`](dynamic-subagents.md) | Dynamic subagents | 1381 | Use interpreters to dispatch and orchestrate Deep Agents subagents from code |
| [`event-streaming.md`](event-streaming.md) | Event streaming | 220 | Stream subagents, messages, tool calls, and final output from Deep Agents. |
| [`fault-tolerance.md`](fault-tolerance.md) | Fault tolerance | 274 | Make your deep agent resilient with rate limiting, retries, fallbacks, and error handling |
| [`frontend/overview.md`](frontend/overview.md) | Overview | 147 | Build UIs that display real-time subagent streams, task progress, and sandbox for Deep Agents |
| [`frontend/sandbox.md`](frontend/sandbox.md) | Sandbox | 1825 | Build an IDE-like UI for a coding agent backed by a sandbox environment |
| [`frontend/subagent-streaming.md`](frontend/subagent-streaming.md) | Subagent streaming | 1299 | Display specialist subagents with streaming content, progress tracking, and collapsible cards |
| [`frontend/todo-list.md`](frontend/todo-list.md) | Todo list | 1372 | Track agent progress with a real-time todo list synced from agent state |
| [`going-to-production.md`](going-to-production.md) | Going to production | 943 | Take your deep agent to production with persistent memory, sandboxes, resilience middleware, and deployment options |
| [`human-in-the-loop.md`](human-in-the-loop.md) | Human-in-the-loop | 960 | Learn how to configure human approval for sensitive tool operations |
| [`interpreters.md`](interpreters.md) | Interpreters | 578 | Run lightweight code inside Deep Agents to compose tools, orchestrate subagents, and transform structured data |
| [`mcp.md`](mcp.md) | Model Context Protocol (MCP) | 982 |  |
| [`memory.md`](memory.md) | Memory | 530 | Add persistent memory to agents built with Deep Agents so they learn and improve across conversations |
| [`models.md`](models.md) | Models | 181 | Configure model providers and parameters for Deep Agents |
| [`multimodal.md`](multimodal.md) | Multimodal inputs and outputs | 124 | Use images, audio, video, and documents with Deep Agents when your model supports multimodal inputs and tool results |
| [`openwiki.md`](openwiki.md) | OpenWiki | 91 | CLI that writes and maintains agent wikis so coding agents work faster |
| [`overview.md`](overview.md) | Deep Agents overview | 566 | Build agents that can plan, use subagents, and leverage file systems for complex tasks |
| [`permissions.md`](permissions.md) | Permissions | 357 | Control filesystem access with declarative permission rules for Deep Agents |
| [`profiles.md`](profiles.md) | Profiles | 231 | Package per-provider and per-model defaults that Deep Agents applies when a model is selected |
| [`quickstart.md`](quickstart.md) | Quickstart | 365 | Build your first deep agent in minutes |
| [`rag.md`](rag.md) | Retrieval Augmented Generation (RAG) with Deep Agents | 1498 | RAG patterns for Deep Agents, including skills-guided retrieval, rubric grading, and a tutorial that indexes LangChain docs, offloads chunks to the filesystem, and delegates analysis to subagents |
| [`retrieval.md`](retrieval.md) | Retrieval | 339 |  |
| [`rubric.md`](rubric.md) | Grading rubrics | 997 | LLM-as-a-judge grading for agents that iterate against a rubric until done |
| [`sandboxes.md`](sandboxes.md) | Sandboxes | 2119 | Execute code in isolated environments with sandbox backends |
| [`skills.md`](skills.md) | Skills | 1856 | Learn how to extend your deep agent's capabilities with skills |
| [`streaming.md`](streaming.md) | Streaming | 1375 | Stream real-time updates from deep agent runs and subagent execution |
| [`subagents.md`](subagents.md) | Subagents | 2855 | Learn how to use subagents to delegate work and keep context clean |
| [`tools.md`](tools.md) | Tools | 580 | Connect Deep Agents to custom functions, APIs, databases, and any MCP server |
