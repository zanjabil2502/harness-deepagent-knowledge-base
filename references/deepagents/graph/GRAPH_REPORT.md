> **Provenance**: derived from the `deepagents 0.7.8` source - the same
> version documented in `references/systems/deepagents.md` and pinned in
> `references/recipes/uv.lock`. Pure AST extraction (zero LLM tokens).
> Regenerate when the version bumps; see README §The deepagents source graph.

# Graph Report - deepagents-src  (2026-08-23)

## Corpus Check
- 53 files · ~108,654 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1788 nodes · 3619 edges · 106 communities (98 shown, 8 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 347 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Rubric Grading
- Context Hub Backend
- Profile Plugin Bootstrap
- Message Eviction & Formatting
- Filesystem Backend
- Composite Backend
- Model Call Wrapping & Retry
- Video Frame Extraction
- Store Backend
- Summarization Middleware
- Grep & Glob Utilities
- File Read Paths
- Entity Resolution Guard
- Summarization Factory
- Composite Routing Init
- Memory Middleware
- Filesystem Middleware Tools
- State
- Nemotron Harness Profile
- Langsmith
- Filesystem
- Graph
- Sandbox
- Summarization
- Sandbox
- Harness Profiles
- Protocol
- Version
- Nvidia Nemotron 3 Ultra
- Filesystem
- Nvidia Nemotron 3 Ultra
- Composite
- Nvidia Nemotron 3 Ultra
- Models
- Async Subagents
- Tool Exclusion
- Filesystem
- Filesystem
- Summarization
- Filesystem
- Skills
- Anthropic Haiku 4 5
- Sandbox
- Filesystem
- Local Shell
- Async Subagents
- Filesystem
- Subagents
- Harness Profiles
- Skills
- Async Subagents
- Subagents
- Nvidia Nemotron 3 Ultra
- Protocol
- Protocol
- Protocol
- Sandbox
- Filesystem
- Excluded Middleware
- Fs Interrupt
- Skills
- Skills
- Async Subagents
- Patch Tool Calls
- Summarization
- Sandbox
- Store
- Async Subagents
- Prompt Caching
- Subagents
- Harness Profiles
- Harness Profiles
- Async Subagents
- Skills
- Nvidia Nemotron 3 Ultra
- Deprecation
- Graph
- Skills
- Summarization
- Openai Codex
- Tools
- Utils
- Async Subagents
- Filesystem
- Harness Profiles
- Sandbox
- Sandbox
- Filesystem
- Filesystem
- Summarization
- Messages Reducer
- State
- Protocol
- Store
- Filesystem
- Filesystem
- Filesystem
- Async Subagents
- Init
- Init
- Init
- Permissions
- Init
- Init
- Init

## God Nodes (most connected - your core abstractions)
1. `BackendProtocol` - 72 edges
2. `create_deep_agent()` - 50 edges
3. `FilesystemMiddleware` - 48 edges
4. `ContextHubBackend` - 46 edges
5. `CompositeBackend` - 43 edges
6. `BaseSandbox` - 43 edges
7. `FilesystemBackend` - 40 edges
8. `_DeepAgentsSummarizationMiddleware` - 35 edges
9. `StoreBackend` - 34 edges
10. `StateBackend` - 32 edges

## Surprising Connections (you probably didn't know these)
- `create_deep_agent()` --calls--> `warn_deprecated()`  [INFERRED]
  graph.py → _api/deprecation.py
- `_validate_excluded_middleware_config()` --calls--> `_format_scaffolding_rejection()`  [INFERRED]
  _excluded_middleware.py → profiles/harness/harness_profiles.py
- `create_deep_agent()` --calls--> `_validate_excluded_middleware_config()`  [INFERRED]
  graph.py → _excluded_middleware.py
- `create_deep_agent()` --calls--> `_apply_excluded_middleware()`  [INFERRED]
  graph.py → _excluded_middleware.py
- `create_deep_agent()` --calls--> `_verify_excluded_middleware_coverage()`  [INFERRED]
  graph.py → _excluded_middleware.py

## Import Cycles
- None detected.

## Communities (106 total, 8 thin omitted)

### Community 0 - "Rubric Grading"
Cohesion: 0.05
Nodes (61): beta, _build_grader_transcript(), _calls_grader_response(), _coerce_text(), _configured_model_label(), CriterionFail, CriterionPass, _fallback_structured_output_model_patterns() (+53 more)

### Community 1 - "Context Hub Backend"
Cohesion: 0.07
Nodes (28): ContextHubBackend, _DeleteIntent, _EditIntent, _Mutation, _MutationQueue, BaseException, `ContextHubBackend`: Store files in a LangSmith Hub agent repo (persistent)., Initialize ContextHubBackend. Args: identifier: Hub agent repo, as… (+20 more)

### Community 2 - "Profile Plugin Bootstrap"
Cohesion: 0.05
Nodes (45): EntryPoint, _ensure_builtin_profiles_loaded(), _format_plugin_label(), _invoke_profile_plugins(), Bootstrap for built-in and third-party profile plugins. Built-in provider and…, Register built-in profiles and discover third-party plugins. Runs two phases,…, Invoke every entry-point callable in `group`, isolating failures. Failure…, Return a human-readable identifier for a plugin entry point. Includes the… (+37 more)

### Community 3 - "Message Eviction & Formatting"
Cohesion: 0.08
Nodes (44): format_content_with_line_numbers(), r"""Sanitize tool_call_id to prevent path traversal and separator issues.…, Format file content with line numbers. Chunks lines longer than…, sanitize_tool_call_id(), BaseMessage, _aoffload_tool_message_content(), _build_evicted_content(), _build_evicted_tool_message() (+36 more)

### Community 4 - "Filesystem Backend"
Cohesion: 0.07
Nodes (27): FilesystemBackend, Path, Parse one ripgrep `--json` line into `(virtual_path, line_no, text)`. Returns…, Drain ripgrep stderr while retaining bounded error diagnostics., Close stdout and reap ripgrep after EOF, termination, or timeout., Fallback search using Python when ripgrep is unavailable. Recursively searches…, Find files matching a glob pattern. Pattern matching uses the shared backend…, Upload multiple files to the filesystem. Args: files: List of `(path, content)`… (+19 more)

### Community 5 - "Composite Backend"
Cohesion: 0.10
Nodes (31): CompositeBackend, _glob_truncated(), _merge_glob_results(), Composite backend that routes file operations by path prefix. Routes operations…, Merge the default backend's glob result with routed backends' results. A…, Route a path to a backend and normalize it for that backend. Returns the…, Routes file operations to different backends by path prefix. Matches paths…, Normalize legacy `list[FileInfo]` returns to `LsResult`. (+23 more)

### Community 6 - "Model Call Wrapping & Retry"
Cohesion: 0.13
Nodes (21): ModelCallResult, _ai_message_count(), _is_rate_limit_exception(), _messages_since_last_user(), NemotronProgressBudgetMiddleware, Any, BaseException, ModelRequest (+13 more)

### Community 7 - "Video Frame Extraction"
Cohesion: 0.10
Nodes (38): _check_decode_deadline(), _encode_jpeg(), extract_video_frames(), _find_video_stream(), _format_timestamp(), _frame_dimensions(), _frame_seconds(), _import_av() (+30 more)

### Community 8 - "Store Backend"
Cohesion: 0.11
Nodes (22): Return the store instance. Uses the store passed at init if available,…, Get the namespace for store operations. Resolves the `Runtime` from the graph…, Convert current and legacy persisted store content to `FileData`. Args:…, Convert `FileData` to a dict suitable for `store.put()`. Args: file_data: The…, List files and directories in the specified directory (non-recursive). Args:…, Async version of read using native store async methods. This avoids sync calls…, Write content to a file, creating it or overwriting it if it already exists.…, Async version of write using native store async methods. This avoids sync calls… (+14 more)

### Community 9 - "Summarization Middleware"
Cohesion: 0.10
Nodes (21): _DeepAgentsSummarizationMiddleware, AnyMessage, ExtendedModelResponse, Persist messages to backend before summarization. Appends evicted messages to a…, Persist messages to backend before summarization (async). Appends evicted…, Process messages before model invocation, with history offloading and arg…, Process messages before model invocation, with history offloading and arg…, Summarization middleware with backend for conversation history offloading. (+13 more)

### Community 10 - "Grep & Glob Utilities"
Cohesion: 0.09
Nodes (34): build_grep_results_dict(), compile_grep_include_glob(), compile_recursive_glob(), _filter_files_by_path(), format_grep_matches(), _format_grep_results(), _format_grep_with_context(), _glob_search_files() (+26 more)

### Community 11 - "File Read Paths"
Cohesion: 0.08
Nodes (26): Read file content for the requested line range. Args: file_path: Absolute file…, Read file content for the requested line range. Args: file_path: Absolute or…, _binary_read_result(), r"""Read file content using the LangSmith SDK. `BaseSandbox.read()` pipes file…, Build the binary `ReadResult` shape used by `LangSmithSandbox.read()`. Mirrors…, FileData, Data structure for storing file contents with metadata., Result from backend read operations. (+18 more)

### Community 12 - "Entity Resolution Guard"
Cohesion: 0.11
Nodes (22): EntityResolutionGuardState, FinalAnswerGuardState, FollowupDisciplineState, _is_final_answer(), _last_external_human_text(), _message_text(), AgentState, hook_config (+14 more)

### Community 13 - "Summarization Factory"
Cohesion: 0.09
Nodes (30): CompactConversationSchema, compute_summarization_defaults(), create_summarization_middleware(), create_summarization_tool_middleware(), AgentState, BaseChatModel, BaseModel, ContextSize (+22 more)

### Community 14 - "Composite Routing Init"
Cohesion: 0.07
Nodes (20): Initialize composite backend. Args: default: Backend for paths that don't match…, BackendProtocol, r"""Protocol for pluggable memory backends (single, unified). Backends can…, List all files in a directory with metadata. Args: path: Absolute path to the…, Async version of `ls`., Search for a literal text pattern in files. Args: pattern: Literal string to…, Find files matching a glob pattern. Pattern matching follows the shared backend…, Async version of `glob`. (+12 more)

### Community 15 - "Memory Middleware"
Cohesion: 0.10
Nodes (22): MemoryMiddleware, MemoryState, MemoryStateUpdate, AgentState, ContextT, ModelRequest, ModelResponse, ResponseT (+14 more)

### Community 16 - "Filesystem Middleware Tools"
Cohesion: 0.11
Nodes (16): FilesystemMiddleware, BaseTool, Middleware for providing filesystem and optional execution tools to an agent.…, Create the ls (list files) tool., Create the read_file tool., Create the write_file tool., Create the edit_file tool., Create the delete tool. (+8 more)

### Community 17 - "State"
Cohesion: 0.11
Nodes (16): Any, RunnableConfig, `StateBackend`: Store files in LangGraph agent state (ephemeral)., Convert FileData to the format used for state storage., Write content to a file, creating it or overwriting it if it already exists.…, Edit a file by replacing string occurrences. The update is queued directly via…, Delete a file or directory from state. Deleting a path removes the exact file…, Search state files for a literal text pattern. (+8 more)

### Community 18 - "Nemotron Harness Profile"
Cohesion: 0.15
Nodes (25): _alternate_function_args(), _alternate_function_name(), _budget_fallback_text(), _budget_result_is_informative(), FinalAnswerGuardMiddleware, _first_json_object(), _format_budget_value(), _last_domain_mutation_result() (+17 more)

### Community 19 - "Langsmith"
Cohesion: 0.08
Nodes (17): AsyncSandbox, _execute_response(), LangSmithSandbox, LangSmith sandbox backend implementation., Execute a shell command inside the sandbox. Overrides the protocol default,…, Close the cached async client's connection pool, if one was created., Write content using the LangSmith SDK to avoid ARG_MAX. `BaseSandbox.write()`…, Download multiple files from the LangSmith sandbox. Supports partial success.… (+9 more)

### Community 20 - "Filesystem"
Cohesion: 0.08
Nodes (25): Future, _all_paths_scoped_to_routes(), _clamped_offset_notice(), _discard_task_result(), _file_data_delta_reducer(), _file_data_reducer(), FilesystemState, _get_read_file_type() (+17 more)

### Community 21 - "Graph"
Cohesion: 0.09
Nodes (25): BaseCache, Checkpointer, CompiledStateGraph, _apply_custom_middleware(), create_deep_agent(), DeepAgentState, _merge_fs_interrupt_on(), AgentMiddleware (+17 more)

### Community 22 - "Sandbox"
Cohesion: 0.12
Nodes (15): Result from backend `write` operations. Attributes: error: Error message on…, Write content to a file, creating it or overwriting it if it already exists.…, Async version of write., WriteResult, BaseSandbox, _build_write_preflight_cmd(), _check_preflight_result(), Base sandbox implementation with `execute()` as the core abstract method. This… (+7 more)

### Community 23 - "Summarization"
Cohesion: 0.14
Nodes (15): AgentMiddleware, BaseException, Command, ToolRuntime, Middleware that provides a `compact_conversation` tool for manual compaction.…, Build the `Command` result for a successful compact operation. Shared by both…, Return a "nothing to compact" result for the compact tool. Args: tool_call_id:…, Return an error result for the compact tool. Args: tool_call_id: The… (+7 more)

### Community 24 - "Sandbox"
Cohesion: 0.13
Nodes (15): EditResult, Result from backend `edit` operations. Attributes: error: Error message on…, Perform exact string replacements in an existing file. Args: file_path:…, Async version of edit., _build_edit_inline_cmd(), _build_edit_tmpfile_cmd(), _map_edit_error(), _parse_edit_output() (+7 more)

### Community 25 - "Harness Profiles"
Cohesion: 0.14
Nodes (22): _apply_profile_prompt(), _ensure_harness_profiles_loaded(), _get_harness_profile(), _harness_profile_for_model(), HarnessProfile, _has_any_harness_profile(), _merge_general_purpose_subagent_profiles(), _merge_middleware() (+14 more)

### Community 26 - "Protocol"
Cohesion: 0.15
Nodes (16): Normalize legacy `list[GrepMatch] | str` returns to `GrepResult`., Call `grep` while supporting backends with the previous signature., Call `agrep` while supporting backends with the previous signature., Async version of `grep`, with optional surrounding context lines. As in the…, _apply_grep_max_count(), GrepResult, _method_accepts_max_count(), Protocol definition for pluggable memory backends. This module defines the… (+8 more)

### Community 27 - "Version"
Cohesion: 0.15
Nodes (21): Distribution, _distribution_name(), _editable_source_root(), _file_url_to_path(), _is_editable_install(), _is_under(), _lc_version(), Path (+13 more)

### Community 28 - "Nvidia Nemotron 3 Ultra"
Cohesion: 0.13
Nodes (16): _build_extra_middleware(), FollowupDisciplineMiddleware, ModelRateLimitRetryMiddleware, NemotronReasoningTagCleanupMiddleware, NemotronTextToolCallParser, AgentMiddleware, AIMessage, ModelResponse (+8 more)

### Community 29 - "Filesystem"
Cohesion: 0.15
Nodes (14): _handle_video_read(), Command, ToolCallRequest, ToolMessage, Build a `ToolMessage` carrying a plain text error., Slice a video byte payload into a sampled frame window for the model. `offset`…, Process a large ToolMessage by evicting its content to filesystem. Args:…, Async version of _process_large_message. Uses async backend methods to avoid… (+6 more)

### Community 30 - "Nvidia Nemotron 3 Ultra"
Cohesion: 0.19
Nodes (13): NemotronToolCallShim, Command, ToolCallRequest, ToolMessage, Repair the request, run the tool, and normalize empty results., Async variant of `wrap_tool_call`., Append a continuation notice to exactly-at-limit `read_file` results., Return whether `row` looks like a formatted `read_file` source line. Matches a… (+5 more)

### Community 31 - "Composite"
Cohesion: 0.11
Nodes (10): Read file content, routing to appropriate backend. Args: file_path: Absolute…, Async version of read., Create a new file, routing to appropriate backend. Args: file_path: Absolute…, Async version of write., Edit a file, routing to appropriate backend. Args: file_path: Absolute file…, Async version of edit., Upload multiple files, batching by backend for efficiency. Groups files by…, Async version of upload_files. (+2 more)

### Community 32 - "Nvidia Nemotron 3 Ultra"
Cohesion: 0.22
Nodes (11): Report the public `SummarizationMiddleware` alias for string-form exclusion.…, _external_human_messages(), _iter_tool_calls(), NemotronPolicyNudgeMiddleware, NemotronPolicyNudgeState, _nudge_update(), HumanMessage, State schema for one-shot Nemotron policy nudges. (+3 more)

### Community 33 - "Models"
Cohesion: 0.17
Nodes (18): get_model_identifier(), get_model_provider(), is_bedrock_model(), _is_bedrock_nova_model_id(), model_matches_spec(), _normalize_provider(), BaseChatModel, Shared helpers for resolving and inspecting chat models. (+10 more)

### Community 34 - "Async Subagents"
Cohesion: 0.15
Nodes (17): _afetch_live_status(), AsyncTask, _fetch_live_status(), _filter_tasks(), _format_task_entry(), ToolRuntime, TypedDict, Middleware for async subagents running on remote Agent Protocol servers. Async… (+9 more)

### Community 35 - "Tool Exclusion"
Cohesion: 0.14
Nodes (14): AIMessage, Any, BaseTool, ExtendedModelResponse, ModelRequest, ModelResponse, ResponseT, Middleware for filtering excluded tools from model requests. (+6 more)

### Community 36 - "Filesystem"
Cohesion: 0.21
Nodes (11): ContextT, ExtendedModelResponse, ModelRequest, ModelResponse, ResponseT, Drop capability-gated tools the backend can't serve, then apply the system…, Update the system prompt, filter tools, and evict oversized HumanMessages. In…, (async) Update the system prompt and filter tools based on backend… (+3 more)

### Community 37 - "Filesystem"
Cohesion: 0.15
Nodes (16): _is_read_file_media_result(), _move_media_results_after_tool_results(), _multimodal_block_supported(), Any, AnyMessage, ContentBlock, Return whether `message` carries media emitted by a `read_file` tool result., Keep synthetic media messages after the tool-result batch they describe. Tool-… (+8 more)

### Community 38 - "Summarization"
Cohesion: 0.16
Nodes (15): _decode_data_url(), _extract_data_url(), _is_data_url(), _media_reference_block(), Any, Decode inline `data:` media blocks to files and replace them with path…, Async twin of `_offload_inline_media` using `aupload_files`. See…, Return whether `url` is an inline `data:` URL. Any `data:` URL is treated as… (+7 more)

### Community 39 - "Filesystem"
Cohesion: 0.19
Nodes (15): _apply_permissions_to_glob_results(), _apply_permissions_to_ls_results(), _check_fs_permission(), FilesystemPermission, _filter_file_infos_by_permission(), _filter_grep_matches_by_permission(), _filter_paths_by_permission(), FilesystemOperation (+7 more)

### Community 40 - "Skills"
Cohesion: 0.21
Nodes (11): ContextT, ModelRequest, ModelResponse, ResponseT, Inject skills documentation into the system prompt. Args: request: Model…, Inject skills documentation into the system prompt (async version). Args:…, Middleware for loading and exposing agent skills to the system prompt. Loads…, Format skills locations for display in system prompt. (+3 more)

### Community 41 - "Anthropic Haiku 4 5"
Cohesion: 0.12
Nodes (13): Built-in Claude Haiku 4.5 harness profile. Layers Anthropic's universal Claude…, Register the built-in Claude Haiku 4.5 harness profile., register(), Built-in Claude Opus 4.7 harness profile. Layers a system-prompt suffix onto…, Register the built-in Claude Opus 4.7 harness profile., register(), Built-in Claude Sonnet 4.6 harness profile. Layers Anthropic's universal Claude…, Register the built-in Claude Sonnet 4.6 harness profile. (+5 more)

### Community 42 - "Sandbox"
Cohesion: 0.17
Nodes (12): ABC, _absolutize_glob_path(), _build_glob_cmd(), _classify_glob_line(), _parse_glob_output(), Any, Base sandbox implementation.…, Classify one line of remote glob output. Args: line: A single non-blank stdout… (+4 more)

### Community 43 - "Filesystem"
Cohesion: 0.17
Nodes (14): _is_eloop_oserror(), _is_symlink_loop_error(), _map_exception_to_standard_error(), BaseException, Exception, _raise_if_symlink_loop(), `FilesystemBackend`: Read and write files directly from the filesystem., Map a caught exception to a standardized `FileOperationError` code.… (+6 more)

### Community 44 - "Local Shell"
Cohesion: 0.14
Nodes (10): LocalShellBackend, Path, `LocalShellBackend`: Filesystem backend with unrestricted local shell…, Initialize local shell backend with filesystem access. Args: root_dir: Working…, Unique identifier for this backend instance. Returns: String identifier in…, r"""Execute a shell command directly on the host system. !!! danger…, Filesystem backend with unrestricted local shell command execution. This…, ExecuteResponse (+2 more)

### Community 45 - "Async Subagents"
Cohesion: 0.23
Nodes (15): _build_async_subagent_tools(), _build_cancel_tool(), _build_check_tool(), _build_list_tasks_tool(), _build_start_tool(), _build_update_tool(), _ClientCache, Lazily-created, cached Agent Protocol clients keyed by (url, headers). (+7 more)

### Community 46 - "Filesystem"
Cohesion: 0.13
Nodes (15): DeleteSchema, EditFileSchema, ExecuteSchema, GlobSchema, GrepSchema, LsSchema, BaseModel, Input schema for the `ls` tool. (+7 more)

### Community 47 - "Subagents"
Cohesion: 0.15
Nodes (14): create_sub_agent(), _get_subagent_response_format(), Any, BaseModel, ResponseFormat, ToolRuntime, Middleware for providing subagents to an agent via a `task` tool., Input schema for the `task` tool. (+6 more)

### Community 48 - "Harness Profiles"
Cohesion: 0.16
Nodes (12): _coerce_frozen_strset(), _coerce_general_purpose_subagent(), _coerce_str_or_none(), GeneralPurposeSubagentProfile, Any, Dump this sub-profile to a plain dict. Only fields with non-`None` values are…, Construct a sub-profile from a plain dict. Args: data: Mapping with any subset…, Construct a config object from a plain dict. Args: data: A mapping with any… (+4 more)

### Community 49 - "Skills"
Cohesion: 0.18
Nodes (14): r"""Normalize backslash separators to forward slashes for `PurePosixPath` use.…, r"""Validate and normalize file path for security. Ensures paths are safe to…, to_posix_path(), validate_path(), _alist_skills(), _alist_skills_with_errors(), _format_skills_source_error(), _list_skills_with_errors() (+6 more)

### Community 50 - "Async Subagents"
Cohesion: 0.21
Nodes (10): ContextT, ModelRequest, ModelResponse, ResponseT, Update the system message to include async subagent instructions., (async) Update the system message to include async subagent instructions., append_to_system_message(), SystemMessage (+2 more)

### Community 51 - "Subagents"
Cohesion: 0.19
Nodes (11): _build_task_tool(), CompiledSubAgent, BaseTool, TypedDict, A pre-compiled agent spec. !!! note The `runnable`'s state schema must include…, Specification for an agent. When using `create_deep_agent`, subagents…, Create a task tool from subagent specs. Args: subagents: List of raw or…, Initialize the `SubAgentMiddleware`. (+3 more)

### Community 52 - "Nvidia Nemotron 3 Ultra"
Cohesion: 0.31
Nodes (4): _coerce_int(), EntityResolutionGuardMiddleware, Send Ultra3 back once when it finalizes with unresolved or mis-bound IDs., Inject entity-branch guidance before the model finalizes.

### Community 53 - "Protocol"
Cohesion: 0.17
Nodes (7): Delete a file, routing to the appropriate backend. `CompositeBackend` always…, Async version of delete., Delete a file or directory from the filesystem. Files are unlinked. Directories…, DeleteResult, Result from backend delete operations. Attributes: error: Error message on…, Delete a path, recursively removing anything nested under it. This method is…, Async version of `delete`.

### Community 54 - "Protocol"
Cohesion: 0.17
Nodes (7): Download multiple files, batching by backend for efficiency. Groups paths by…, Async version of download_files., Download multiple files from the filesystem. Args: paths: List of file paths to…, FileDownloadResponse, Result of a single file download operation. The response is designed to allow…, Download multiple files from the sandbox. This API is designed to allow…, Async version of download_files.

### Community 55 - "Protocol"
Cohesion: 0.18
Nodes (8): Execute a shell command via the default backend. Unlike file operations,…, Async version of execute. See `execute()` for detailed documentation on…, execute_accepts_timeout(), Extension of `BackendProtocol` that adds shell command execution. Designed for…, Unique identifier for the sandbox backend instance., Async version of execute., Check whether a backend class's `execute` accepts a `timeout` kwarg. Older…, SandboxBackendProtocol

### Community 56 - "Sandbox"
Cohesion: 0.21
Nodes (10): ExecuteOffloadResult, Result of…, _build_capture_execute_cmd(), _new_heredoc_delim(), _parse_capture_execute_output(), Return a random heredoc delimiter, e.g. `__DEEPAGENTS_CMD_<80 random bits>__`., Build the capture-at-source wrapper command for `execute`. `inline_budget` is…, r"""Parse capture-wrapper stdout into an `ExecuteOffloadResult`. The wrapper… (+2 more)

### Community 57 - "Filesystem"
Cohesion: 0.18
Nodes (12): _glob_anchor(), _paths_overlap(), Return the longest leading directory of `pattern` with no wildcards. For…, Return True if the subtree at `call_path` intersects the subtree at…, _find_delete_deny_patterns(), _find_delete_deny_patterns_for_leaf(), Check whether a wildcard deny pattern overlaps a recursive delete target. Args:…, Resolve delete permission for a confirmed plain file: first matching rule wins.… (+4 more)

### Community 58 - "Excluded Middleware"
Cohesion: 0.27
Nodes (11): _apply_excluded_middleware(), AgentMiddleware, Any, _raise_on_name_collisions(), Filtering helpers for `HarnessProfile.excluded_middleware`. These functions…, Raise `ValueError` if any `profile.excluded_middleware` entry matched nothing.…, Validate stack-independent guards on `profile.excluded_middleware`. Rejects…, Raise `ValueError` if any string exclusion matched multiple distinct classes. A… (+3 more)

### Community 59 - "Fs Interrupt"
Cohesion: 0.27
Nodes (11): _build_interrupt_on_from_permissions(), _make_bulk_when_predicate(), _make_exact_when_predicate(), _make_fs_when_predicate(), FilesystemOperation, InterruptOnConfig, ToolCallRequest, Glue between `FilesystemPermission` rules and `HumanInTheLoopMiddleware`.… (+3 more)

### Community 60 - "Skills"
Cohesion: 0.21
Nodes (11): _parse_allowed_tools(), _parse_skill_metadata(), Skills middleware for loading and exposing agent skills to the system prompt.…, Cap a skill loading warning before placing it in the model prompt., Validate skill name per Agent Skills specification. Constraints per Agent…, Parse the `allowed-tools` frontmatter value into a list of tool names. Accepts…, Parse YAML frontmatter from `SKILL.md` content. Extracts metadata per Agent…, Validate and normalize the metadata field from YAML frontmatter. YAML… (+3 more)

### Community 61 - "Skills"
Cohesion: 0.21
Nodes (10): AgentState, RunnableConfig, Runtime, TypedDict, State for the skills middleware., State update for the skills middleware., Load skills metadata before agent execution (synchronous). Loads skills once…, Load skills metadata before agent execution (async). Loads skills once per… (+2 more)

### Community 62 - "Async Subagents"
Cohesion: 0.18
Nodes (11): CancelAsyncTaskSchema, CheckAsyncTaskSchema, ListAsyncTasksSchema, BaseModel, Input schema for the `start_async_task` tool., Input schema for the `check_async_task` tool., Input schema for the `update_async_task` tool., Input schema for the `cancel_async_task` tool. (+3 more)

### Community 63 - "Patch Tool Calls"
Cohesion: 0.18
Nodes (9): PatchToolCallsMiddleware, AgentMiddleware, AgentState, Any, Runtime, Middleware to patch dangling tool calls in the messages history., Middleware to patch dangling tool calls in the messages history., Before the agent runs, handle dangling tool calls from any AIMessage. (+1 more)

### Community 64 - "Summarization"
Cohesion: 0.20
Nodes (6): ToolCall, Retrieve max input token limit from the model profile., Check if argument truncation should be triggered. Args: messages: Current…, Determine the cutoff index for argument truncation based on keep policy.…, Truncate large arguments in a single tool call. Args: tool_call: The tool call…, Truncate large tool call arguments in old messages. Args: messages: Messages to…

### Community 65 - "Sandbox"
Cohesion: 0.22
Nodes (6): _build_ls_cmd(), _parse_ls_output(), Execute a command in the sandbox and return `ExecuteResponse`. Args: command:…, Structured listing with file metadata using os.scandir., Async version of `ls`, delegating to `aexecute`., Delete a file or directory from the sandbox via a server-side `rm`. Runs `test…

### Community 66 - "Store"
Cohesion: 0.24
Nodes (7): Any, BaseStore, r"""Initialize `StoreBackend`. Args: namespace: Callable that receives a…, Search store with automatic pagination to retrieve all results. Args: store:…, Async version of `_search_store_paginated`., Item, NamespaceFactory

### Community 67 - "Async Subagents"
Cohesion: 0.24
Nodes (7): LangGraphClient, Build headers for a remote Agent Protocol server. Adds `x-auth-scheme:…, Build a cache key from the agent spec's url and resolved headers., Get or create a sync client for the named agent., Get or create an async client for the named agent., _resolve_headers(), SyncLangGraphClient

### Community 68 - "Prompt Caching"
Cohesion: 0.33
Nodes (9): append_prompt_caching_middleware(), _create_bedrock_prompt_caching_middleware(), _create_fireworks_prompt_caching_middleware(), AgentMiddleware, Any, Provider-specific prompt-caching middleware helpers., Create Bedrock prompt caching middleware when `langchain-aws` is installed., Create Fireworks prompt caching middleware when `langchain-fireworks` is… (+1 more)

### Community 69 - "Subagents"
Cohesion: 0.29
Nodes (8): ContextT, ModelRequest, ModelResponse, ResponseT, Middleware for providing subagents to an agent via a `task` tool. This…, Update the system message to include instructions on using subagents., (async) Update the system message to include instructions on using subagents., SubAgentMiddleware

### Community 70 - "Harness Profiles"
Cohesion: 0.22
Nodes (7): _coerce_str_mapping(), HarnessProfileConfig, Declarative harness-profile config for YAML/JSON-backed profiles. !!! beta…, Dump this config to plain dict/list/scalar values. Suitable for `json.dumps` or…, Convert this declarative config into a runtime `HarnessProfile`.…, Export a runtime `HarnessProfile` back to declarative config. String-form…, Validate that `value` is a `str -> str` mapping (or `None`) and return a plain…

### Community 71 - "Harness Profiles"
Cohesion: 0.24
Nodes (8): _format_scaffolding_rejection(), Freeze mutable mappings and validate grammar of string entries., Return a violation label for `entry` when it names required scaffolding. Class…, Format the construction-time scaffolding-rejection error message. Mirrors the…, Freeze mutable container fields to prevent post-construction mutation.…, Validate grammar of a string `excluded_middleware` entry. Runs at…, _scaffolding_violation_label(), _validate_config_middleware_string()

### Community 72 - "Async Subagents"
Cohesion: 0.22
Nodes (7): AsyncSubAgent, AsyncSubAgentMiddleware, Return an error message if `agent_type` is not in `agent_map`, or `None` if…, Specification for an async subagent running on a remote [Agent…, Middleware for async subagents running on remote Agent Protocol servers. This…, Initialize the `AsyncSubAgentMiddleware`., _validate_agent_type()

### Community 73 - "Skills"
Cohesion: 0.31
Nodes (8): _derive_source_label(), Raise `TypeError` if a tuple source is not a `(str, str)` pair. Catches the…, Return just the path component of a source., Derive the display label for a skill source. Tuples carry an explicit label,…, Initialize the skills middleware. Args: backend: Backend instance (e.g.…, _source_path(), _validate_tuple_source(), SkillSource

### Community 74 - "Nvidia Nemotron 3 Ultra"
Cohesion: 0.33
Nodes (4): ChatNVIDIAMessageCompatibilityMiddleware, Mirror standard LangChain tool-call fields into ChatNVIDIA payload metadata., Patch request messages before ChatNVIDIA serializes them., Async variant of `wrap_model_call`.

### Community 75 - "Deprecation"
Cohesion: 0.25
Nodes (7): Adapter for `langchain_core`'s private deprecation helpers. Centralizes the…, Reset the `@deprecated` decorator's dedupe flag for testing. The langchain_core…, Emit a deprecation warning with caller-controlled stack attribution.…, reset_deprecation_dedupe(), warn_deprecated(), __getattr__(), Provide deprecated compatibility access to legacy module attributes.

### Community 76 - "Graph"
Cohesion: 0.32
Nodes (7): ChatAnthropic, deprecated, _build_default_model(), get_default_model(), Primary graph assembly module for Deep Agents. Provides…, Construct the default model without emitting a deprecation warning. Internal…, Get the default model for Deep Agents. !!! deprecated Deprecated since `0.5.3`;…

### Community 77 - "Skills"
Cohesion: 0.29
Nodes (7): _format_skill_annotations(), _list_skills(), Metadata for a skill per Agent Skills specification…, Build a parenthetical annotation string from optional skill fields. Combines…, List all skills from a backend source., Format skills metadata for display in system prompt., SkillMetadata

### Community 78 - "Summarization"
Cohesion: 0.25
Nodes (5): BaseTool, SystemMessage, Initialize with a reference to the summarization middleware. Args:…, Create the `compact_conversation` structured tool. Returns: A `StructuredTool`…, Count tokens for messages plus optional system message and tools. Args:…

### Community 79 - "Openai Codex"
Cohesion: 0.29
Nodes (7): _build_extra_middleware(), AgentMiddleware, Any, Built-in OpenAI Codex harness profile. Registers a `HarnessProfile` for each…, Build fresh Codex behavioral middleware for each assembled agent stack.…, Register the built-in Codex harness profile for each Codex spec., register()

### Community 80 - "Tools"
Cohesion: 0.36
Nodes (7): _apply_tool_description_overrides(), Any, BaseTool, Helpers for inspecting and rewriting `create_deep_agent` tool inputs., Extract the tool name from any supported tool type. Args: tool: A tool in any…, Apply description overrides without mutating caller-owned tools. Only dict…, _tool_name()

### Community 81 - "Utils"
Cohesion: 0.33
Nodes (6): Read file content for the requested line range. Args: file_path: Absolute file…, _get_backend_read_file_type(), _get_file_type(), FileType, Classify a file by its extension. Args: path: File path to classify. Returns:…, Classify a file for backend reads, forcing known video containers to binary.…

### Community 82 - "Async Subagents"
Cohesion: 0.29
Nodes (7): _build_check_command(), _build_check_result(), Any, Command, Build the result dict from a run's current status and its thread values., Build the `Command` update for a check result., Run

### Community 83 - "Filesystem"
Cohesion: 0.33
Nodes (6): _build_evicted_human_content(), _build_truncated_human_message(), HumanMessage, Build replacement content for an evicted HumanMessage, preserving non-text…, Build a truncated HumanMessage for the model request. Computes a preview from…, Tag a newly evicted message and truncate all tagged messages. When a new…

### Community 84 - "Harness Profiles"
Cohesion: 0.33
Nodes (6): AgentMiddleware, Resolve middleware to a concrete sequence, calling the factory if needed., Return a fresh list of `extra_middleware`, invoking factory if supplied. Each…, Serialize a runtime `excluded_middleware` entry back to config form. Class…, _resolve_middleware_seq(), _serialize_runtime_excluded_middleware_entry()

### Community 85 - "Sandbox"
Cohesion: 0.40
Nodes (4): _build_grep_cmd(), _parse_grep_output(), Search file contents for a literal string using `grep -F`. Args: pattern:…, Async version of `grep`, delegating to `aexecute` with timeout guard.

### Community 86 - "Sandbox"
Cohesion: 0.40
Nodes (4): _build_read_cmd(), _parse_read_output(), Read file content with server-side line-based pagination. Runs a Python script…, Async version of `read`, delegating to `aexecute`.

### Community 87 - "Filesystem"
Cohesion: 0.33
Nodes (6): Truncate list or string result if it exceeds token limit (rough estimate: 4…, truncate_if_too_long(), _format_file_paths(), _format_glob_tool_result(), Format filesystem path lists for tool output., Render glob paths for the tool boundary, appending the truncation note when…

### Community 88 - "Filesystem"
Cohesion: 0.33
Nodes (6): _adelete_target_may_have_descendants(), _delete_target_may_have_descendants(), _leaf_from_parent_listing(), Resolve the ambiguous "empty `ls(target)`, no error" case. On flat/virtual…, Whether `delete` should use the conservative recursive permission check. Falls…, Async counterpart to `_delete_target_may_have_descendants`.

### Community 89 - "Summarization"
Cohesion: 0.40
Nodes (4): ModelRequest, ModelResponse, Inject a compact-tool usage nudge into the system prompt. This only updates…, Inject a compact-tool usage nudge into the system prompt (async). This only…

### Community 90 - "Messages Reducer"
Cohesion: 0.40
Nodes (4): _messages_delta_reducer(), AnyMessage, Local `DeltaChannel` reducer for the messages key. Adapted from langgraph's…, Batch reducer for use with `DeltaChannel` on the messages key. Dedups by ID,…

### Community 91 - "State"
Cohesion: 0.50
Nodes (4): _has_marker(), private_state_field_names(), Helpers for working with Deep Agents state schemas., Return fields annotated with `PrivateStateAttr` across state schemas.…

### Community 92 - "Protocol"
Cohesion: 0.50
Nodes (3): ExecuteArtifact, Machine-readable metadata attached to an `execute` tool result. Carried on…, Build the `ExecuteArtifact` for an execute result. See `ExecuteArtifact` for…

### Community 93 - "Store"
Cohesion: 0.50
Nodes (3): `StoreBackend`: Adapter for LangGraph's BaseStore (persistent, cross-thread)., Validate a namespace tuple returned by a NamespaceFactory. Each component must…, _validate_namespace()

### Community 95 - "Filesystem"
Cohesion: 0.50
Nodes (4): Input schema for the `read_file` tool., Input schema for `read_file` when the optional video frame extraction is…, ReadFileSchema, ReadVideoFileSchema

### Community 96 - "Filesystem"
Cohesion: 0.50
Nodes (4): Render the read pagination notice when the backend returned a partial window.…, Truncate a paginated read without skipping undisplayed source lines. The…, _remaining_lines_notice(), _truncate_paginated_read()

### Community 97 - "Async Subagents"
Cohesion: 0.67
Nodes (3): AsyncSubAgentState, AgentState, State extension for async subagent task tracking.

## Knowledge Gaps
- **8 thin communities (<3 nodes) omitted from report** - run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BackendProtocol` connect `Composite Routing Init` to `Context Hub Backend`, `Message Eviction & Formatting`, `Filesystem Backend`, `Composite Backend`, `Store Backend`, `Summarization Middleware`, `File Read Paths`, `Summarization Factory`, `Memory Middleware`, `Filesystem Middleware Tools`, `State`, `Filesystem`, `Graph`, `Sandbox`, `Sandbox`, `Protocol`, `Filesystem`, `Composite`, `Summarization`, `Skills`, `Skills`, `Subagents`, `Protocol`, `Protocol`, `Protocol`, `Subagents`, `Skills`, `Skills`, `Filesystem`?**
  _High betweenness centrality (0.365) - this node is a cross-community bridge._
- **Why does `create_deep_agent()` connect `Graph` to `Summarization Factory`, `Composite Routing Init`, `Memory Middleware`, `Filesystem Middleware Tools`, `State`, `Harness Profiles`, `Version`, `Models`, `Tool Exclusion`, `Filesystem`, `Skills`, `Harness Profiles`, `Subagents`, `Excluded Middleware`, `Fs Interrupt`, `Patch Tool Calls`, `Prompt Caching`, `Subagents`, `Async Subagents`, `Deprecation`, `Graph`, `Tools`, `State`?**
  _High betweenness centrality (0.351) - this node is a cross-community bridge._
- **Why does `_DeepAgentsSummarizationMiddleware` connect `Summarization Middleware` to `Summarization`, `Nvidia Nemotron 3 Ultra`, `Message Eviction & Formatting`, `Summarization`, `Summarization Factory`, `Summarization`, `Composite Routing Init`, `Summarization`?**
  _High betweenness centrality (0.130) - this node is a cross-community bridge._
- **Are the 27 inferred relationships involving `BackendProtocol` (e.g. with `_route_for_path()` and `create_deep_agent()`) actually correct?**
  _`BackendProtocol` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 26 inferred relationships involving `create_deep_agent()` (e.g. with `warn_deprecated()` and `BackendProtocol`) actually correct?**
  _`create_deep_agent()` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `FilesystemMiddleware` (e.g. with `create_deep_agent()` and `BackendProtocol`) actually correct?**
  _`FilesystemMiddleware` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `ContextHubBackend` (e.g. with `DeleteResult` and `EditResult`) actually correct?**
  _`ContextHubBackend` has 11 INFERRED edges - model-reasoned connections that need verification._