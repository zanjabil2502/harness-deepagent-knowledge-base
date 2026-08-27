"""05 - Orchestrator wiring: typed settings, structured logging, optional tracing.

Demonstrates: the four boundary decisions `scaffolds/_base.md` makes around
`create_deep_agent`, each constructed for real rather than described. Typed
settings that fail at boot on a missing field (`pydantic-settings`), frozen
Pydantic models at the API boundary, structured logs with stdlib records
bridged into them (`loguru`), and a tracing handler that stays absent when no
credential is configured (`langfuse`).

Archetypes served: all of them. This is the `_base` wiring every archetype
delta starts from, before its own tools, subagents, or gates are added.

Concepts illustrated: `python-practice.md` (Pydantic at the trust boundary,
frozen models inside, stdlib-first with four justified dependencies) and
`scaffolds/_base.md` (config.py, observability/logging.py,
observability/tracing.py).

Runs with no credentials of any kind and never calls a model. The four claims
it proves are exactly the ones a reader would otherwise have to trust.
"""

import logging
import sys
from typing import Any

from langchain_anthropic import ChatAnthropic
from loguru import logger
from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from deepagents import create_deep_agent


# --------------------------------------------------------------------------
# config.py: typed settings, validated once
# --------------------------------------------------------------------------
class Settings(BaseSettings):
    """Mirrors scaffolds/_base.md §Config & secrets."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_database_url: SecretStr
    checkpointer_database_url: SecretStr
    model_name: str = "claude-sonnet-4-6"
    drain_timeout_s: float = 25.0
    log_level: str = "INFO"
    log_json: bool = False  # False here so the recipe's output stays readable
    langfuse_public_key: SecretStr | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_host: str = "https://cloud.langfuse.com"


# --------------------------------------------------------------------------
# orchestrator/interface.py: frozen models at the boundary
# --------------------------------------------------------------------------
class Scope(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: str


class TurnEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str
    turn_id: str
    type: str
    data: dict[str, Any]
    ts: str


# --------------------------------------------------------------------------
# observability/logging.py: loguru, with stdlib records bridged in
# --------------------------------------------------------------------------
class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging(settings: Settings) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        serialize=settings.log_json,
        backtrace=False,
        diagnose=False,  # never True in production: it dumps locals into tracebacks
    )
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


# --------------------------------------------------------------------------
# observability/tracing.py: tracing is optional, absence is not an error
# --------------------------------------------------------------------------
def build_langfuse_handler(settings: Settings):
    if settings.langfuse_public_key is None:
        return None
    from langfuse.langchain import CallbackHandler

    return CallbackHandler()


def build_agent(settings: Settings, callbacks) -> Any:
    """The _base baseline: an explicit model, no tools, no subagents, no gates.
    Each archetype delta adds its own on top of this."""
    model = ChatAnthropic(model_name=settings.model_name)
    del callbacks  # attached per run in the config below, not at construction
    return create_deep_agent(model=model, tools=[])


def run_config(scope: Scope, thread_id: str, callbacks) -> dict:
    """What _base hands to .astream(). Langfuse reads user and session from
    these metadata keys; there is no constructor argument for them."""
    return {
        "configurable": {"thread_id": thread_id},
        "callbacks": callbacks,
        "metadata": {
            "langfuse_user_id": scope.user_id,
            "langfuse_session_id": thread_id,
            "langfuse_tags": ["turn"],
        },
    }


def main() -> int:
    print("=== 05_orchestrator_wiring ===")

    # 1. A missing required field fails at construction, naming the field.
    try:
        Settings()
        print("1. settings          : UNEXPECTED, missing fields did not raise")
        return 1
    except ValidationError as e:
        missing = sorted(str(err["loc"][0]) for err in e.errors())
        print(f"1. settings fail-fast: missing {missing} rejected at boot")

    # 2. With values supplied, secrets are masked in every repr.
    settings = Settings(
        app_database_url="postgresql://user:pw@localhost/app",
        checkpointer_database_url="postgresql://user:pw@localhost/ckpt",
    )
    assert "pw" not in repr(settings.app_database_url)
    print(f"2. secret masking    : repr is {settings.app_database_url!r}, "
          "get_secret_value() is the only way out")

    setup_logging(settings)

    # 3. Frozen boundary models: mutation is refused, model_construct skips
    #    validation on the hot path while keeping the same type.
    scope = Scope(user_id="demo-user-001")
    try:
        scope.user_id = "someone-else"
        print("3. frozen models     : UNEXPECTED, mutation was allowed")
        return 1
    except ValidationError:
        pass
    validated = TurnEvent(
        event_id="t-1", turn_id="t", type="message.delta",
        data={"text_delta": "hi"}, ts="2026-08-27T00:00:00Z",
    )
    fast = TurnEvent.model_construct(
        event_id="t-2", turn_id="t", type="message.delta",
        data={"text_delta": "hi"}, ts="2026-08-27T00:00:00Z",
    )
    assert type(validated) is type(fast) and fast.model_dump_json()
    print("3. frozen models     : mutation refused; model_construct returns "
          f"the same type ({type(fast).__name__}) without validating")

    # 4. No key configured means no handler, not a failed boot.
    callbacks = [h for h in (build_langfuse_handler(settings),) if h is not None]
    print(f"4. tracing optional  : langfuse_public_key unset -> "
          f"{len(callbacks)} callback(s), boot continues")

    agent = build_agent(settings, callbacks)
    cfg = run_config(scope, thread_id="conv-123", callbacks=callbacks)
    print(f"5. agent constructed : nodes {sorted(agent.get_graph().nodes.keys())}")
    print(f"6. run config keys   : {sorted(cfg)} | metadata "
          f"{sorted(cfg['metadata'])}")

    logger.bind(turn_id="t", user_id=scope.user_id).info("wiring verified")

    print(
        "Construction verified: settings, boundary models, logging and the "
        "optional tracing handler all built. This recipe deliberately never "
        "calls the model: it needs no credentials at all and touches no "
        "network."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
