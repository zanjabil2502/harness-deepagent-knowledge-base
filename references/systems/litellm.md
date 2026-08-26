# LiteLLM (Proxy)

> Label every claim: [code] / [docs] / [inferred]

Tier **T2**. `BerriAI/litellm`, a Python (FastAPI) gateway/proxy sitting in
front of 100+ LLM providers, chosen as the **per-user quota & rate limiting**
exemplar per the T2 candidates in spec §10. **An important note**: the LiteLLM
Proxy isn't an agent harness — it has no tool-calling loop and no subagent
delegation. The seven axes below are answered as they genuinely are for this
system: some axes (loop shape, delegation) are mapped to the nearest concept
that actually exists (a retry/fallback loop, multi-deployment routing) rather
than forced into an agent-loop shape it doesn't have — honesty over artificial
completeness.

## Archetype

Not one of the seven agent archetypes — LiteLLM is **serving infrastructure**
(the Runtime/gateway layer) used *by* any archetype as its route to an LLM.
Functionally closest to the "Gateway / SSE" and "State store" rows in the
serving table of design spec §8.3: IO-bound, HPA-signalled through active
connections rather than RPS. `[code]` — the directory structure of
`litellm/proxy/` (dozens of endpoint sub-routers: `auth/`, `guardrails/`,
`hooks/`, `management_endpoints/`, `db/`).

## 1. Loop shape

Not ReAct — **retry-with-cooldown** inside
`Router.completion()`/`Router.acompletion()`. The `num_retries` parameter
(default: `litellm.num_retries` if set, otherwise falling back to
`openai.DEFAULT_MAX_RETRIES`) repeats the call to another deployment in the
same model group when one deployment fails. A repeatedly failing deployment
(`allowed_fails`) enters a **cooldown** (`cooldown_time`, default
`DEFAULT_COOLDOWN_TIME_SECONDS`) through
`CooldownCache`/`_set_cooldown_deployments`, temporarily removed from the
routing candidates — not deleted permanently. `enable_weighted_failover=True`
(only for the `"simple-shuffle"` strategy, only on the async path) makes a
retryable failure trigger a weighted re-selection among other deployments
**before** cross-group fallback is attempted, bounded by `max_fallbacks`. Who
"decides to stop": not a model — purely a retry counter plus the provider's
HTTP status/exception. `[code]` — `litellm/router.py` lines 416, 437-440,
479-498, 665-682.

## 2. Context

Not message compaction (LiteLLM stores no server-side conversation history by
default — that is the client's responsibility). What exists: **prompt caching**
across requests through the `cache_control_check.py` hook (honouring/injecting
provider-level `cache_control`, e.g. Anthropic prompt caching) and response
caching (`DualCache` — in-memory + Redis) used extensively for rate-limit
counters rather than conversation content. `[code]` — the listing of
`litellm/proxy/hooks/cache_control_check.py`;
`litellm/proxy/hooks/parallel_request_limiter.py` line 10 (the `DualCache`
import).

## 3. Tool surface

One **broad and uniform** API surface (OpenAI-compatible:
`/chat/completions`, `/embeddings`, `/responses`, etc. — visible from the
`openai_files_endpoints`, `realtime_endpoints`, `fine_tuning_endpoints`,
`batches_endpoints` sub-routers) translating to 100+ different providers behind
it — the inverse of the "tool" pattern in the agent sense: here "tool surface"
means **one API contract mapped to many backends**, not many tools called by
one model. `[code]` — the listing of `litellm/proxy/*_endpoints/` (>15
sub-routers).

## 4. Delegation

No subagents in the agent-harness sense. The structurally closest thing is
**cross-deployment routing**: `routing_strategy` (a Literal of
`"simple-shuffle"`, `"least-busy"`, `"usage-based-routing"`,
`"latency-based-routing"`, `"cost-based-routing"`, plus `"lar1"` — a custom
strategy through `apply_lar1_routing_strategy`) chooses **which deployment**
handles a request from a set of deployments claiming the same `model_name`.
`RoutingGroup` (`routing_groups: Optional[List[RoutingGroup]]`) allows a
**different routing strategy per named model group**, with the rest falling to
an implicit `"default"` group. This isn't result-returning delegation like a
subagent — the chosen deployment's result directly becomes the request's
response, with no aggregation across several parallel calls on the normal path.
`[code]` — `litellm/router.py` lines 441-449, 491-493, 700, 754-761.

## 5. State & resume

"Resume" doesn't apply (the proxy is stateless per request). "State" here is a
**durable quota/spend ledger**, stored through a Prisma/Postgres schema:
`LiteLLM_BudgetTable`, `LiteLLM_UserTable`, `LiteLLM_TeamTable`,
`LiteLLM_VerificationToken` (an API key + scope), `LiteLLM_SpendLogs` (a
per-call transaction log). This is exactly the "per-user quota & rate limiting"
layer that made LiteLLM a T2 candidate — quota state lives in a durable DB
rather than process memory, so it survives restarts and stays consistent across
horizontally scaled proxy instances. `[code]` — `litellm/proxy/schema.prisma`
lines 12, 118, 234, 416, 611 (the model names, confirmed through grep; not all
field details were read).

The short-term rate-limit counters (RPM/TPM per key/user/team/end-user/model)
use `DualCache` (in-memory + Redis) — fast but resettable and horizontally
scalable through Redis; not durable like the spend tables. `[code]` —
`litellm/proxy/hooks/parallel_request_limiter.py` lines 43-49 (`CacheObject`
with the fields `request_count_api_key`, `request_count_user_id`,
`request_count_team_id`, `request_count_end_user_id`).

## 6. Safety gate

Six or more separate `CustomLogger.async_pre_call_hook`/`async_post_call_*`
hooks, each one a specific policy, run in sequence before a request is passed
to the provider — exactly the "tiered: cheap checks first" pattern from design
spec §8.4:

- `max_budget_limiter.py` — `_PROXY_MaxBudgetLimiter.async_pre_call_hook`
  reads `user_api_key_dict.user_max_budget`; if `None`, it **passes with no
  check** (fail-open by absence of config, not fail-open by explicit design —
  no budget set means no gate). `[code]` —
  `litellm/proxy/hooks/max_budget_limiter.py` lines 19-33.
- `parallel_request_limiter.py`/`_v3.py` — RPM/TPM per
  key/user/team/end-user/model, raising `HTTPException` (fail-closed, the
  request refused) when a limit is exceeded. `[code]` — the filename plus the
  `ProxyRateLimitError` import.
- `dynamic_rate_limiter.py`/`_v3.py`, `batch_rate_limiter.py`,
  `model_max_budget_limiter.py`, `max_budget_per_session_limiter.py`,
  `max_iterations_limiter.py` — other limit variants (per-model budget, per
  session, per iteration — that last name being relevant to agents running
  through this proxy, limiting the number of agent *steps* rather than only
  tokens/requests). `[code]` — the listing of `litellm/proxy/hooks/*.py`.
- `prompt_injection_detection.py`, `sensitive_data_routing.py`,
  `responses_id_security.py` — detection/mitigation at the input and routing
  points. `[code]` — the listing.

Content guardrails (as opposed to quota) live in `litellm/proxy/guardrails/`,
registered through `guardrail_registry.py` — a **declarative plugin registry**:
each guardrail provider (Bedrock, GraySwan, Lakera AI v1/v2, Presidio PII
masking, `ToolPermissionGuardrail`, and dozens more — `aim`, `akto`,
`aporia_ai`, `azure`, `cisco_ai_defense`, `crowdstrike_aidr`, `javelin`,
`microsoft_purview`, etc., >25 directories) is imported and registered as a
`CustomGuardrail` class activated through configuration rather than hardcoded
into the request path. `[code]` —
`litellm/proxy/guardrails/guardrail_registry.py` lines 1-38; the listing of
`litellm/proxy/guardrails/guardrail_hooks/` (>25 entries).

## 7. Capability routing & policy

**A declarative manifest (YAML config/DB) driving deterministic strategies in
code — not model judgement, not an ML classifier.** Two layers:

1. **Model routing** — the `routing_strategy` per `RoutingGroup` (axis 4) is an
   explicit algorithmic choice (round-robin/simple-shuffle, least-busy from
   in-flight counters, usage-based, latency-based from observed history,
   cost-based, or a custom `lar1`) — selected through proxy configuration
   (`litellm_config.yaml` / the DB), re-evaluated per request by router code,
   never handed to an LLM to decide. `[code]` — `litellm/router.py` lines
   441-449, 700-761.
2. **Guardrail routing** — `guardrail_registry.py` loads which guardrails are
   active from configuration (a dynamic import per provider name), then each
   concrete guardrail runs its own check (a regex/PII detector/guardrail-specific
   classification model — not the main agent model). This is the *policy as
   data* pattern: the rules (which guardrail is active for which
   endpoint/key/team) are configuration that can be verified and audited, in
   line with the argument in `references/concepts/policy-as-data.md`. `[code]`
   — `litellm/proxy/guardrails/guardrail_registry.py`.

There is no "capability routing" in the sense of a model selecting a
skill/persona — LiteLLM runs no agent model at all, only forwarding and
deciding **where** a model call is routed and **which policies** apply before
and after it.

## Sources

The `BerriAI/litellm` repo was shallow-cloned (`git clone --depth 1`) on
2026-08-23 and read directly as files:

- `litellm/router.py` (12,489 lines total — **not** read in full) — the lines
  cited: 131-147 (the cooldown/retry util imports), 416-500 (the
  `Router.__init__` parameter docstrings: `routing_strategy`,
  `routing_strategy_args`, `routing_groups`, `enable_weighted_failover`,
  `num_retries`, `allowed_fails`, `cooldown_time`, `disable_cooldowns`),
  665-682 (the `num_retries`/`cooldown_time` defaults), 700-761
  (`_normalize_strategy`, the `"lar1"` branch), 1912-2130
  (`completion`/`acompletion` — name and signature only)
- `litellm/proxy/schema.prisma` lines 12, 118, 234, 416, 611 (the model names
  `LiteLLM_BudgetTable`, `LiteLLM_TeamTable`, `LiteLLM_UserTable`,
  `LiteLLM_VerificationToken`, `LiteLLM_SpendLogs`)
- `litellm/proxy/hooks/max_budget_limiter.py` — in full for the
  `async_pre_call_hook` part (lines 1-40)
- `litellm/proxy/hooks/parallel_request_limiter.py` — lines 1-50 (the imports,
  `_response_total_tokens`, `CacheObject`)
- `litellm/proxy/guardrails/guardrail_registry.py` — lines 1-38 (the concrete
  guardrail imports)
- Directory listings (file/folder names through `find`/`ls`, contents unread):
  `litellm/proxy/hooks/*.py` (23 files — `dynamic_rate_limiter*.py`,
  `batch_rate_limiter.py`, `max_iterations_limiter.py`,
  `model_max_budget_limiter.py`, `max_budget_per_session_limiter.py`,
  `prompt_injection_detection.py`, `sensitive_data_routing.py`,
  `responses_id_security.py`, `cache_control_check.py`),
  `litellm/proxy/guardrails/guardrail_hooks/*` (>25 provider subdirectories),
  `litellm/proxy/*_endpoints/` (>15 sub-routers)

An honesty note: `router.py` is a 12K+ line file, of which only ~150 lines are
genuinely cited above — the claims about `completion()`/`acompletion()` are
limited to what is visible from the signature and the `__init__` parameter
docstrings, not from tracing the whole execution path line by line. The
contents of each file under `guardrail_hooks/*` (each provider's specific
regex/model) weren't read — only their existence and names are cited as
evidence of a "plugin registry", not how each guardrail works internally.
