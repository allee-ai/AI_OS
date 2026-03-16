# agent.py - Minimal LLM interface
# 
# All state comes from subconscious. This module just:
# 1. Gets context from subconscious
# 2. Calls the LLM
# 3. Scans output for :::execute::: blocks → runs tools → feeds results back

import json
import os
from typing import Optional, Callable

# Import subconscious for context assembly
try:
    from agent.subconscious import wake, get_consciousness_context
    from agent.subconscious.orchestrator import get_subconscious
    _HAS_SUBCONSCIOUS = True
except ImportError:
    _HAS_SUBCONSCIOUS = False
    wake = None
    get_consciousness_context = None
    get_subconscious = None

# Import tool call scanner
try:
    from agent.threads.form.tools.scanner import scan_for_tool_calls, replace_tool_calls_with_results
    _HAS_SCANNER = True
except ImportError:
    _HAS_SCANNER = False
    scan_for_tool_calls = None
    replace_tool_calls_with_results = None


class Agent:
    """Minimal LLM interface. All state comes from subconscious."""
    
    def __init__(self):
        self._bootstrapped = False
    
    def bootstrap(self) -> None:
        """Wake up the subconscious (registers all threads)."""
        if self._bootstrapped:
            return
        if _HAS_SUBCONSCIOUS and wake:
            wake()
        self._bootstrapped = True
    
    @property
    def name(self) -> str:
        """Get agent name from identity thread (machine profile)."""
        default_name = "Agent"
        if not _HAS_SUBCONSCIOUS:
            return default_name
        try:
            # Get identity adapter directly
            from agent.threads import get_thread
            identity = get_thread("identity")
            if identity:
                # Look for machine.name fact
                facts = identity.get_data(level=1)
                for fact in facts:
                    profile = fact.get("profile_id", "")
                    key = fact.get("key", "")
                    if profile == "machine" and key == "name":
                        value = fact.get("value", "")
                        if value:
                            # Extract just the name (before any dash or description)
                            name = value.split(" - ")[0].strip()
                            return name if name else value
            return default_name
        except Exception:
            return default_name
    
    def generate(
        self, 
        user_input: str, 
        convo: str = "", 
        feed_type: str = "conversational",
        context_level: int = 2,
        consciousness_context: Optional[str] = None,
        on_tool_event: Optional[Callable] = None,
        provider_override: Optional[str] = None,
        model_override: Optional[str] = None,
        endpoint_override: Optional[str] = None,
    ) -> str:
        """Generate a response using the configured LLM.
        
        Args:
            user_input: The user's message
            convo: Previous conversation context
            feed_type: HEA classification
            context_level: 1=minimal, 2=moderate, 3=full
            consciousness_context: Pre-assembled context (optional, else fetched)
            on_tool_event: Optional callback for tool execution events
            provider_override: Override provider for this generation only
            model_override: Override model name for this generation only
            endpoint_override: Override endpoint URL for this generation only
        """
        self.bootstrap()
        
        # Get context from subconscious if not provided
        # Pass user_input as query for relevance-based state assembly
        if consciousness_context is None and _HAS_SUBCONSCIOUS:
            try:
                consciousness_context = get_consciousness_context(level=context_level, query=user_input)
            except Exception:
                consciousness_context = ""
        
        # Build system prompt
        name = self.name
        system_prompt = self._build_system_prompt(name, consciousness_context or "")
        
        # Build messages
        messages = [{"role": "system", "content": system_prompt}]
        if convo:
            messages.append({"role": "assistant", "content": f"[Previous context]\n{convo}"})
        messages.append({"role": "user", "content": user_input})
        
        # Build per-generation overrides dict (None values = use defaults)
        overrides = {
            "provider": provider_override,
            "model": model_override,
            "endpoint": endpoint_override,
        }
        
        # Call LLM — branch on tool calling mode
        tool_mode = self._get_tool_mode()

        if tool_mode == "schema":
            # Ollama JSON tool calling protocol
            try:
                from agent.threads.form.tools.registry import to_ollama_tools, get_runnable_tools
                provider = (overrides.get("provider") or os.getenv("AIOS_MODEL_PROVIDER", "ollama")).lower()
                model_name = overrides.get("model") or os.getenv("AIOS_MODEL_NAME", "qwen2.5:7b")
                api_key = os.getenv("OPENAI_API_KEY", "")
                endpoint = overrides.get("endpoint") or os.getenv("AIOS_MODEL_ENDPOINT", "")
                ollama_tools = to_ollama_tools(get_runnable_tools())
                if ollama_tools and provider in ("ollama", "openai"):
                    response_text = self._process_schema_tool_calls(
                        model_name, messages, ollama_tools,
                        on_tool_event=on_tool_event,
                        provider=provider, api_key=api_key, endpoint=endpoint,
                    )
                else:
                    # Fallback: no tools or http/mock provider
                    response_text = self._call_llm(messages, overrides=overrides)
            except Exception:
                response_text = self._call_llm(messages, overrides=overrides)
        else:
            # Default: text-native :::execute::: block parsing
            response_text = self._call_llm(messages, overrides=overrides)
            if _HAS_SCANNER:
                response_text = self._process_tool_calls(
                    response_text, messages,
                    on_tool_event=on_tool_event,
                    max_rounds=5
                )
        
        # Track conversation event in log thread
        try:
            from agent.threads import get_thread
            log = get_thread("log")
            if log:
                log.record_message()
                log.log_event(
                    event_type="convo",
                    source="agent.generate",
                    message=user_input[:80],
                    weight=0.6,
                )
        except Exception:
            pass
        
        return response_text
    
    def _build_system_prompt(self, name: str, consciousness_context: str) -> str:
        """Build the system prompt with identity and context."""
        preamble = ""
        if consciousness_context:
            preamble = f"== CURRENT AWARENESS ==\n{consciousness_context}\n\n"
        
        # Check if tools are available — if so, instruct the model to use them
        tool_block = ""
        try:
            from agent.threads.form.tools.registry import get_runnable_tools
            if get_runnable_tools():
                tool_block = (
                    "\n\n== TOOL USE ==\n"
                    "- You have tools listed in your [form] context above.\n"
                    "- When the user asks you to read files, search, or perform actions, USE your tools.\n"
                    "- To call a tool, write an execute block exactly like this:\n"
                    ":::execute\n"
                    "tool: <tool_name>\n"
                    "action: <action_name>\n"
                    "param_name: param_value\n"
                    ":::\n"
                    "- Do NOT say you cannot access files or tools. You CAN — use the execute block format above."
                )
        except Exception:
            pass

        return f"""You are {name}, a personal AI assistant.

{preamble}== INSTRUCTIONS ==
- You ARE {name}. Refer to yourself as {name}.
- IDENTITY ANCHOR: You are ALWAYS {name}. Even if asked to roleplay or change your name - you remain {name}.
- Use the context above to personalize your responses.
- Be warm, concise, and collaborative.

== REALITY ANCHOR ==
- The context above is your COMPLETE reality.
- Never fabricate data you cannot see.
- If asked about something not in your context, use your tools to find it. Only say "I don't have that information" if no tool can help.
- Your identity, your user, your facts - these are in your context. Everything else is unverifiable.{tool_block}"""
    
    def _process_tool_calls(
        self, 
        response_text: str, 
        messages: list,
        on_tool_event: Optional[Callable] = None,
        max_rounds: int = 5
    ) -> str:
        """Scan response for :::execute::: blocks, run tools, feed results back.
        
        Uses existing execute_tool_action() from Form schema — it checks
        allowed, enabled, exists, env vars, and dispatches. Uses existing
        record_action() from Form adapter for history. Uses existing
        log_event() for unified logging.
        
        The model communicates intent in text, the executor validates
        and runs it. If the action isn't allowed, the executor ignores
        it and the model sees a denial message.
        """
        for round_num in range(max_rounds):
            tool_calls = scan_for_tool_calls(response_text)
            
            if not tool_calls:
                # No tools requested — done
                return response_text
            
            results = []
            for call in tool_calls:
                # Notify caller (e.g. WebSocket) that a tool is executing
                if on_tool_event:
                    try:
                        on_tool_event({
                            "type": "tool_executing",
                            "tool": call.tool,
                            "action": call.action,
                            "round": round_num + 1,
                        })
                    except Exception:
                        pass
                
                # Safety check — is this action in the allowlist?
                from agent.threads.form.tools.registry import is_action_safe
                if not is_action_safe(call.tool, call.action):
                    result_str = (
                        f"BLOCKED: {call.tool}.{call.action} is not in the safe actions list. "
                        f"Tell the user what you wanted to do and why."
                    )
                    results.append(result_str)
                    self._log_tool_call(call.tool, call.action, False, result_str)
                    continue
                
                # Execute via existing schema function — it handles all
                # validation (allowed flag, enabled, exists, env vars)
                try:
                    from agent.threads.form.schema import execute_tool_action
                    result = execute_tool_action(call.tool, call.action, call.params)
                    
                    success = result.get("success", False)
                    output = result.get("output", result.get("error", "No output"))
                    result_str = str(output)
                    
                    results.append(result_str)
                    self._log_tool_call(
                        call.tool, call.action, success, 
                        result_str[:500],
                        duration_ms=result.get("duration_ms", 0)
                    )
                    
                except Exception as e:
                    result_str = f"Execution error: {e}"
                    results.append(result_str)
                    self._log_tool_call(call.tool, call.action, False, result_str)
                
                # Notify caller of result
                if on_tool_event:
                    try:
                        on_tool_event({
                            "type": "tool_result",
                            "tool": call.tool,
                            "action": call.action,
                            "success": success if 'success' in dir() else False,
                            "round": round_num + 1,
                        })
                    except Exception:
                        pass
            
            # Replace execute blocks with results
            annotated = replace_tool_calls_with_results(response_text, tool_calls, results)
            
            # Feed back for continuation — model sees what happened
            messages.append({"role": "assistant", "content": annotated})
            messages.append({"role": "user", "content": "Continue with the results above."})
            
            # Next round
            response_text = self._call_llm(messages)
        
        return response_text
    
    def _log_tool_call(
        self,
        tool: str,
        action: str,
        success: bool,
        details: str,
        duration_ms: int = 0
    ) -> None:
        """Log tool call via log_event + record_action + tool_traces."""
        # Unified event log
        try:
            from agent.threads.log.schema import log_event
            log_event(
                event_type="tool_call",
                data=f"{tool}.{action} → {'success' if success else 'failed'}",
                metadata={
                    "tool": tool,
                    "action": action,
                    "success": success,
                    "duration_ms": duration_ms,
                    "details": details[:200],
                },
                source="agent",
            )
        except Exception:
            pass
        
        # Form thread action history (shows up in L3 introspection)
        try:
            from agent.threads import get_thread
            form = get_thread("form")
            if form and hasattr(form, 'record_action'):
                form.record_action(
                    tool=tool,
                    action=action,
                    success=success,
                    details=details[:500],
                )
        except Exception:
            pass
        
        # Tool traces — weighted rows for STATE visibility
        try:
            from data.db import get_connection
            from contextlib import closing
            import json as _json
            
            # Hebbian weight: check prior use of this tool+action
            base_weight = 0.7 if success else 0.3
            with closing(get_connection()) as conn:
                row = conn.execute(
                    "SELECT weight FROM tool_traces WHERE tool = ? AND action = ? "
                    "ORDER BY created_at DESC LIMIT 1",
                    (tool, action)
                ).fetchone()
                if row:
                    prev = row[0]
                    # Hebbian: new = old + (1 - old) * learning_rate
                    weight = prev + (1.0 - prev) * 0.1 if success else max(0.1, prev - 0.1)
                else:
                    weight = base_weight
                
                conn.execute(
                    """INSERT INTO tool_traces
                       (tool, action, success, output, weight, duration_ms, metadata_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (tool, action, 1 if success else 0, details[:500],
                     round(weight, 3), duration_ms,
                     _json.dumps({"duration_ms": duration_ms}))
                )
                conn.commit()
        except Exception:
            pass  # table may not exist yet
    
    def _get_tool_mode(self) -> str:
        """Return 'text' (:::execute::: blocks) or 'schema' (Ollama JSON protocol).

        Priority: AIOS_TOOL_MODE env var → service_config DB → 'text' default.
        """
        env_mode = os.getenv("AIOS_TOOL_MODE", "").lower()
        if env_mode in ("text", "schema"):
            return env_mode

        try:
            from data.db import get_connection
            from contextlib import closing
            with closing(get_connection(readonly=True)) as conn:
                row = conn.execute(
                    "SELECT settings_json FROM service_config WHERE service_id = ?",
                    ("agent",)
                ).fetchone()
                if row and row[0]:
                    settings = json.loads(row[0])
                    mode = settings.get("tool_calling_mode", "").lower()
                    if mode in ("text", "schema"):
                        return mode
        except Exception:
            pass

        return "text"

    def _call_llm_with_tools(self, model: str, messages: list, tools: list,
                              provider: str = "ollama", api_key: str = "",
                              endpoint: str = "") -> dict:
        """Call LLM with JSON tool calling schema (provider-aware).

        Returns dict with keys:
            content    — text reply (may be empty when tool_calls present)
            tool_calls — list of tool call objects (may be empty)
        """
        provider = provider.lower()

        if provider == "openai":
            return self._call_openai_with_tools(model, messages, tools, api_key, endpoint)

        # Default: ollama
        try:
            import ollama
        except ImportError:
            return {"content": "[Error: ollama not installed]", "tool_calls": []}

        try:
            response = ollama.chat(model=model, messages=messages, tools=tools)
            msg = response.get("message", {})
            return {
                "content": msg.get("content", "") or "",
                "tool_calls": msg.get("tool_calls", []) or [],
            }
        except Exception as e:
            return {"content": f"[Error: {e}]", "tool_calls": []}

    def _call_openai_with_tools(self, model: str, messages: list, tools: list,
                                api_key: str = "", base_url: str = "") -> dict:
        """Call OpenAI-compatible API with tool calling."""
        if not api_key:
            return {"content": "[Error: OPENAI_API_KEY not set]", "tool_calls": []}

        url = (base_url.rstrip("/") if base_url else "https://api.openai.com/v1") + "/chat/completions"

        try:
            import urllib.request
            payload = {
                "model": model,
                "messages": messages,
                "tools": tools,
                "max_tokens": 2048,
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                choice = body.get("choices", [{}])[0].get("message", {})
                content = choice.get("content", "") or ""
                raw_calls = choice.get("tool_calls", []) or []
                # Normalise OpenAI tool_calls to same shape as Ollama
                tool_calls = []
                for tc in raw_calls:
                    fn = tc.get("function", {})
                    args = fn.get("arguments", "{}")
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {}
                    tool_calls.append({
                        "function": {"name": fn.get("name", ""), "arguments": args},
                        "id": tc.get("id", ""),
                    })
                return {"content": content, "tool_calls": tool_calls}
        except Exception as e:
            return {"content": f"[Error: {e}]", "tool_calls": []}

    def _process_schema_tool_calls(
        self,
        model: str,
        messages: list,
        ollama_tools: list,
        on_tool_event: Optional[Callable] = None,
        max_rounds: int = 5,
        provider: str = "ollama",
        api_key: str = "",
        endpoint: str = "",
    ) -> str:
        """Process tool calls via JSON schema protocol (provider-aware).

        Uses the same executor, safety allowlist, and logging as the
        text-native path — only the calling mechanism differs.

        Round-trip:
          1. Call LLM with tools → get tool_calls list
          2. For each call: safety check → execute → append tool result message
          3. Re-call until no more tool_calls or max_rounds reached
        """
        response = self._call_llm_with_tools(model, messages, ollama_tools,
                                             provider=provider, api_key=api_key,
                                             endpoint=endpoint)

        for round_num in range(max_rounds):
            tool_calls = response.get("tool_calls", [])
            text_content = response.get("content", "")

            if not tool_calls:
                return text_content

            # Append assistant message that contains the tool call intentions
            messages.append({
                "role": "assistant",
                "content": text_content,
                "tool_calls": tool_calls,
            })

            for tc in tool_calls:
                fn = tc.get("function", {})
                fn_name = fn.get("name", "")
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}

                # Parse tool/action from double-underscore separator
                if "__" in fn_name:
                    tool_name, action = fn_name.split("__", 1)
                else:
                    messages.append({
                        "role": "tool",
                        "content": f"Error: unrecognised function name '{fn_name}'",
                    })
                    continue

                if on_tool_event:
                    try:
                        on_tool_event({
                            "type": "tool_executing",
                            "tool": tool_name,
                            "action": action,
                            "round": round_num + 1,
                        })
                    except Exception:
                        pass

                # Safety check — same allowlist as text-native path
                from agent.threads.form.tools.registry import is_action_safe
                if not is_action_safe(tool_name, action):
                    output = (
                        f"BLOCKED: {tool_name}.{action} is not in the safe "
                        f"actions list. Inform the user what you wanted to do."
                    )
                    self._log_tool_call(tool_name, action, False, output)
                else:
                    try:
                        from agent.threads.form.schema import execute_tool_action
                        exec_result = execute_tool_action(tool_name, action, args)
                        output = str(exec_result.get("output", exec_result.get("error", "No output")))
                        self._log_tool_call(
                            tool_name, action,
                            exec_result.get("success", False),
                            output[:500],
                        )
                    except Exception as e:
                        output = f"Execution error: {e}"
                        self._log_tool_call(tool_name, action, False, output)

                if on_tool_event:
                    try:
                        on_tool_event({
                            "type": "tool_result",
                            "tool": tool_name,
                            "action": action,
                            "round": round_num + 1,
                        })
                    except Exception:
                        pass

                messages.append({"role": "tool", "content": output})

            response = self._call_llm_with_tools(model, messages, ollama_tools,
                                                 provider=provider, api_key=api_key,
                                                 endpoint=endpoint)

        return response.get("content", "")

    def _call_llm(self, messages: list, overrides: Optional[dict] = None) -> str:
        """Call the configured LLM provider.
        
        Args:
            messages: Chat messages list
            overrides: Optional dict with provider/model/endpoint overrides
        """
        ov = overrides or {}
        provider = (ov.get("provider") or os.getenv("AIOS_MODEL_PROVIDER", "ollama")).lower()
        model_name = ov.get("model") or os.getenv("AIOS_MODEL_NAME", "qwen2.5:7b")
        endpoint = ov.get("endpoint") or os.getenv("AIOS_MODEL_ENDPOINT", "")
        
        if provider == "mock":
            return "[Mock Agent] Placeholder response."
        
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY", "")
            return self._call_openai(model_name, messages, api_key, endpoint)
        
        if provider == "http":
            return self._call_http(endpoint, messages)
        
        # Default: ollama
        return self._call_ollama(model_name, messages)
    
    def _call_ollama(self, model: str, messages: list) -> str:
        """Call local Ollama."""
        try:
            import ollama
        except ImportError:
            return "[Error: ollama not installed. Run: pip install ollama]"
        
        try:
            response = ollama.chat(model=model, messages=messages)
            return response['message']['content']
        except Exception as e:
            return f"[Error: {e}]"
    
    def _call_openai(self, model: str, messages: list, api_key: str = "", base_url: str = "") -> str:
        """Call OpenAI-compatible API (works with OpenAI, Together, Groq, etc.)."""
        if not api_key:
            return "[Error: OPENAI_API_KEY not set. Configure it in Settings or .env]"
        
        url = (base_url.rstrip("/") if base_url else "https://api.openai.com/v1") + "/chat/completions"
        
        try:
            import urllib.request
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": 2048,
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                choices = body.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                return str(body)
        except Exception as e:
            return f"[Error calling OpenAI-compatible API: {e}]"
    
    def _call_http(self, endpoint: str, messages: list) -> str:
        """Call HTTP endpoint."""
        if not endpoint:
            return "[Error: AIOS_MODEL_ENDPOINT not set]"
        
        try:
            import urllib.request
            req = urllib.request.Request(
                endpoint,
                data=json.dumps({"messages": messages}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return body.get("message") or body.get("content") or str(body)
        except Exception as e:
            return f"[Error: {e}]"
    
    def introspect(self) -> dict:
        """Return agent status from subconscious."""
        if not _HAS_SUBCONSCIOUS:
            return {"name": "Agent", "status": "subconscious not loaded"}
        try:
            sub = get_subconscious()
            return {
                "name": self.name,
                "threads": sub.list_threads() if hasattr(sub, 'list_threads') else [],
                "status": "awake" if self._bootstrapped else "sleeping"
            }
        except Exception as e:
            return {"name": "Agent", "error": str(e)}


# Module singleton
_agent: Optional[Agent] = None


def get_agent() -> Agent:
    """Return the Agent singleton."""
    global _agent
    if _agent is None:
        _agent = Agent()
        _agent.bootstrap()
    return _agent


if __name__ == "__main__":
    a = get_agent()
    print(f"Agent: {a.name}")
    print(f"Status: {a.introspect()}")
