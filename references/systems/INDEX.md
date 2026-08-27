# Systems index

Nine **T2** entries (the full 7-axis grid, one file per system - see
`_template.md`) plus the **T3** entries (a cheap index: name + archetype + one
line of distinguishing character, with no separate file). T3 exists so that
adding a harness discovered later takes one line here rather than
restructuring the grid - see §10 of the design spec.

The **Multilingual** column records *whether a system has an explicit design*
for intent/expression separation and localisation (see
`references/concepts/multilingual.md`), not merely "supports other languages
through its base model". The absence of such a design is itself a finding -
see the note below the tables.

## Tier 1 - this KB's foundational SDK

Not a product agent, so outside the "nine T2" count and the multilingual note
below - but given the full 7-axis grid (its §Sources go deeper than any T2's:
an installed package rather than a repo cloned once) because this is the SDK
used to build every archetype in this KB.

| Name | Archetype | Tier | Distinguishing character | Multilingual | Source label |
|---|---|---|---|---|---|
| [deepagents](deepagents.md) | Not one archetype - a harness SDK used to build any archetype (see its §Archetype) | T1 | A middleware stack (filesystem, subagents, summarisation, prompt caching) on top of LangChain/LangGraph; its default stack is closest to a General Task Agent (03), with every axis shiftable through `create_deep_agent(...)` parameters | Not applicable - an SDK, not a product agent with a language surface of its own | mostly `[code]` |

## Tier 2 - the 7-axis dissection

| Name | Archetype | Tier | Distinguishing character | Multilingual | Source label |
|---|---|---|---|---|---|
| [OpenHands](openhands.md) | Workspace Agent (01) + Generative Builder (02) | T2 | The repo name has pivoted to "Agent Canvas" (multi-backend control); the core agent moved to `software-agent-sdk`; deterministic skill routing (keyword/path matching in code rather than pure judgement) | UI i18n only (`src/i18n`, not a locale-aware agent design) | mostly `[code]` |
| [LibreChat](librechat.md) | Workspace Agent (01) + In-App Copilot (05) | T2 | The actual agent loop lives in a separate npm package, `@librechat/agents` (LangGraph); a tree transcript through `parentMessageId`; delegation through inter-agent handoff tools | UI i18n (`client/src/locales`, i18next) - not an intent/expression pipeline | mostly `[code]` |
| [Aider](aider.md) | Workspace Agent (01) | T2 | Uses no tool-calling API at all - it parses edit blocks from text; a PageRank RepoMap for context; a "reflection" loop (`max_reflections=3`) rather than a ReAct tool loop | None | mostly `[code]` |
| [Vercel `ai-chatbot`](vercel-ai-chatbot.md) | In-App Copilot (05) + Generative Builder (02) | T2 | `stopWhen: isStepCount(5)` - a hard 5-step limit; versioned artifacts through the composite PK `(id, createdAt)`; stream reattach conditional on `REDIS_URL`, with the GET reattach endpoint a 204 stub in the snapshot read | None | mostly `[code]` |
| [LiteLLM](litellm.md) | Not an agent - gateway/routing infrastructure | T2 | Not an agent loop; cross-deployment retry+cooldown; an algorithmic `routing_strategy` (5+ strategies); 25+ guardrail providers as a declarative plugin registry | None | mostly `[code]` |
| [Letta](letta.md) | Workspace Agent (01) | T2 | The original repo is archived, its source moved to `letta-code`; memory is now git-backed per agent (`~/.letta/agents/<id>/memory/`, a real git repo) on top of the older memory-block API; the default permission mode is `"unrestricted"` | None | mostly `[code]` |
| [Dify](dify.md) | A platform: In-App Copilot (05) / Workflow Agent (06) depending on the app type | T2 | Two separate loop runners (`FunctionCallAgentRunner` for tool calling vs `CotAgentRunner` for text ReAct), with a 99-iteration limit; a `human_input` node as the DAG's HITL primitive; other workflows publishable as tools (`workflow_as_tool`) | Present - UI + email i18n (`web/i18n`, `email_i18n.py`), broader than any other system in the grid but still string-level, not an intent/expression pipeline | mostly `[code]` |
| [browser-use](browser-use.md) | Computer-Use Agent (07) | T2 | 26 narrow tools; a 3-phase loop (screenshot+DOM → LLM → action); two independent limits (`max_steps=500`, `max_failures=5` consecutive); an explicit prompt-injection→`sensitive_data` exfiltration warning when `allowed_domains` isn't locked down | None | mostly `[code]` |
| [OpenWorker](openworker.md) | General Task Agent (03), hybrid 01/02/05/06 - the most in the grid | T2 | Four risk classes as data (`risk.py`); the approver swapped per session mode; an unattended session **suspends with no timeout** in the Inbox with a durable, idempotent `(session_id, tool_call_id)` request; bounded compaction with a canonical→outbound `boundary_index` | None | mostly `[code]` |
| [Claude Code](claude-code.md) | Workspace Agent (01) | T2 | Closed source - the entire file is `[docs]`/`[inferred]`; the KB's primary example for axis 7 "prose + model judgement" **including its weaknesses**: a 1,536-character cap per skill (measurable dilution), and no neutral intent codes (language coupling) | Unknown (closed; no documentation page found on a separate intent/expression pipeline) | purely `[docs]`/`[inferred]` |

## Tier 3 - the index

| Name | Archetype | Tier | Distinguishing character | Multilingual | Source label |
|---|---|---|---|---|---|
| OpenClaw | General Task Agent (03) + Workflow Agent (06) | T3 | An open-source personal assistant (387k★, TypeScript, MIT) that is **single-operator** and runs on your own device; one Gateway connects models, tools, and the chat channels you already use (WhatsApp/Telegram/Discord, 50+ integrations). Its ecosystem: ClawHub as a skill registry (the `SKILL.md` format, with per-skill install metadata like `"openclaw": {"requires": {"bins": [...]}}` visible in `browser-use`) and SOUL.md as a persona specification | Not examined | `[docs]` the raw README + the GitHub API |
| Hermes | General Task Agent (03) + Workflow Agent (06) | T3 | An *operator shell* - a Telegram/CLI/TUI front door on top of ECC as a reused workflow substrate (`Telegram/CLI/TUI → Hermes → ECC skills + hooks + MCPs`); it has cron, workspace memory, and a distribution flow. Interesting as a **front door separate from the substrate** pattern rather than as a harness itself | Not examined | `[docs]` - the local document `ecc/docs/HERMES-SETUP.md`, a sanitised public version of a private stack; **not verified against a public repo** |
| Tiny Claw | Too early to classify | T3 | **Pre-release** - its own README asks you to wait for the first official release. It declares itself **not** a small version of OpenClaw but an independent product: a native framework from scratch (not on top of Pi/Claude Code/Codex), a small core + a plugin architecture, self-improving memory, tiered smart routing to cut cost, and a fixed personality that cannot be overridden. Don't build on it yet | Not examined | `[docs]` the raw README + the GitHub API |
| Open WebUI | In-App Copilot (05) + Workspace Agent (01) | T3 | A self-hosted multi-user chat UI with RBAC, model routing, and plugin tool/function-calling support - a LibreChat alternative emphasising admin/RBAC | Present (UI i18n) - its depth not yet verified | `[inferred]` |
| Onyx (formerly Danswer) | Research/Analyst (04) + In-App Copilot (05) | T3 | An enterprise search/RAG assistant connecting many data source connectors (Slack, Confluence, Google Drive, etc.) with mandatory citations per answer | Unknown | `[inferred]` |
| assistant-ui | Infrastructure - not an agent, React components | T3 | A chat/artifact component library connectable to various agent backends (including `ai-chatbot`); used to build canvas interfaces rather than to run an agent itself | None | `[inferred]` |
| Mem0 | Infrastructure - a memory layer | T3 | A pluggable memory library (vector + graph) attachable to any agent; an alternative to Letta's memory-block pattern with a more generic, framework-agnostic API | Unknown | `[inferred]` |
| Zep | Infrastructure - a memory layer | T3 | A cross-session memory service built on a temporal knowledge graph; emphasises "facts that change over time" (fact versioning) rather than static summaries | Unknown | `[inferred]` |
| E2B | Infrastructure - a code execution sandbox | T3 | A cloud sandbox (Firecracker microVMs) for agent code execution, with an "open a sandbox → run code → fetch the result" API per session and strong per-run isolation | Not applicable (infrastructure, not an agent) | `[inferred]` |
| Daytona | Infrastructure - a sandbox/dev environment | T3 | Isolated dev environments provisionable quickly for coding agents (also referenced in `deepagents.md` as `libs/partners/daytona`, its exact API not yet verified) | Not applicable | `[inferred]` |
| microsandbox | Infrastructure - a lightweight sandbox | T3 | Lightweight (self-hosted) microVMs for isolating agent code execution without full container overhead, a self-runnable alternative to E2B | Not applicable | `[inferred]` |
| Langfuse | Infrastructure - observability/tracing | T3 | An open-source tracing+eval platform for LLM applications: per-turn traces, eval scores, per-user/session cost attribution | Not applicable | `[inferred]` |
| Phoenix (Arize) | Infrastructure - observability/tracing | T3 | Open-source tracing+eval built on OpenTelemetry/OpenInference, emphasising offline eval and dataset drift | Not applicable | `[inferred]` |
| OpenLLMetry | Infrastructure - tracing instrumentation | T3 | An OpenTelemetry instrumentation library specific to LLM/vector-DB/agent-framework calls - used *inside* other applications (rather than as a standalone platform) to send traces to any observability backend | Not applicable | `[inferred]` |
| vLLM | Infrastructure - GPU-bound serving | T3 | A high-throughput LLM inference engine (PagedAttention, continuous batching) - the serving layer beneath a gateway like LiteLLM, not the gateway itself | Not applicable | `[inferred]` |
| SGLang | Infrastructure - GPU-bound serving | T3 | An LLM serving engine emphasising fast structured generation (constrained decoding) and RadixAttention for cross-request prefix caching | Not applicable | `[inferred]` |
| Ray Serve | Infrastructure - general serving | T3 | A general model-serving framework (not LLM-specific) on Ray, autoscaling on actual per-deployment load - referenced in design spec §8.3 as an example of signal-based serving rather than naive RPS | Not applicable | `[inferred]` |
| KEDA | Infrastructure - a K8s autoscaler | T3 | A Kubernetes event-driven autoscaler; scales pods on custom metrics (e.g. queue depth, in-flight turns) - fitting §8.3's "the HPA signal isn't RPS" rule | Not applicable | `[inferred]` |
| SWE-agent | Workspace Agent (01) | T3 | An automated GitHub issue-solving agent; introduced the term "Agent-Computer Interface" (ACI) - tools redesigned to suit model cognition rather than being raw human-facing APIs | Unknown | `[inferred]` |
| Cline | Workspace Agent (01) | T3 | A VS Code extension for an autonomous coding agent (an IDE interface rather than the CLI/terminal of Aider/Claude Code); notable for separate plan/act modes in the UI | Unknown | `[inferred]` |
| n8n | Workflow Agent (06) | T3 | A visual (node-based) workflow automation platform with connected AI-agent nodes - similar to Dify's workflows but rooted in non-AI automation (broad API integration) rather than built for LLMs from the start | Unknown | `[inferred]` |
| Stagehand | Computer-Use Agent (07) | T3 | An AI wrapper over Playwright - natural-language actions mapped to deterministic Playwright primitives, emphasising debuggability/repeatability compared with browser-use's fuller agentic approach | Unknown | `[inferred]` |

## The multilingual note

Of the nine T2 systems read down to source, **only Dify** has i18n beyond
pure UI strings (transactional email is translated too) - but even that is
still **output localisation**, not the intent/expression separation pipeline
argued in `references/concepts/multilingual.md` and pinned by design spec
§8.6 (intent classification → a neutral code → policy/skill lookup by code →
output rendered in the user's locale). OpenHands and LibreChat have UI i18n
(`i18next`) but no intent-classifier layer separate from skill/agent routing
was found. The other five T2 systems (Aider, `ai-chatbot`, LiteLLM, Letta,
browser-use) have **no** i18n directory or package at all in the cloned
source - confirmed through `find -iname "*i18n*"` / `*locale*` per repo, not
assumed. Claude Code is unknown because it is closed source and no
documentation page was found discussing an intent/expression pipeline
separate from description-based skill routing.

**The finding**: the absence of an explicit multilingual design is the
**norm**, not the exception, in this grid - exactly `multilingual.md`'s
opening argument that most harnesses treat language as a UI feature
(translate the button/label strings) rather than an architectural dimension
(locale as first-class context affecting skill triggering, guardrail
lexicons, and token budget calibration). Not one of the nine T2 systems in
this grid implements the intent/neutral-code separation argued in
`references/concepts/skill-composition.md` §`intents` uses neutral codes -
that pattern is labelled `[ours]` in this KB precisely because no industry
precedent for it was found in the nine systems examined.
