"""Form (Tools) CLI — /tools"""

import json as _json

DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def _cmd_tools(args: str):
    """Manage tools."""
    tokens = args.strip().split(maxsplit=2)
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""
    extra = tokens[2] if len(tokens) > 2 else ""

    if verb == "run":
        run_tokens = rest.strip().split(maxsplit=1) if rest else []
        tool_name = run_tokens[0] if run_tokens else ""
        action_rest = run_tokens[1] if len(run_tokens) > 1 else ""
        action_tokens = action_rest.split(maxsplit=1) if action_rest else []
        action = action_tokens[0] if action_tokens else "default"
        params_str = action_tokens[1] if len(action_tokens) > 1 else ""

        if not tool_name:
            print("  usage: /tools run <name> <action> [json_params]")
            return

        params = {}
        if params_str:
            try:
                params = _json.loads(params_str)
            except _json.JSONDecodeError:
                print(f"  {RED}invalid JSON params{RESET}")
                return

        try:
            from agent.threads.form.schema import execute_tool_action
            result = execute_tool_action(tool_name, action, params or None)
            status = result.get("status", "?")
            scolor = GREEN if result.get("success") else RED
            print(f"  {scolor}[{status}]{RESET} {tool_name}.{action}  ({result.get('duration_ms', '?')}ms)")
            if result.get("output"):
                output = str(result["output"])
                for line in output.splitlines()[:30]:
                    print(f"    {line}")
            if result.get("error"):
                print(f"  {RED}{result['error']}{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    if verb == "new":
        try:
            from agent.threads.form.schema import add_tool, get_categories
            cats = get_categories()
            cat_names = [c["name"] for c in cats]

            name = input(f"  {BOLD}name:{RESET} ").strip()
            if not name:
                print("  cancelled")
                return
            desc = input(f"  {BOLD}description:{RESET} ").strip()
            print(f"  {DIM}categories: {', '.join(cat_names)}{RESET}")
            cat = input(f"  {BOLD}category:{RESET} ").strip() or "automation"
            actions_str = input(f"  {BOLD}actions{RESET} (comma-sep, or Enter for 'default'): ").strip()
            actions = [a.strip() for a in actions_str.split(",")] if actions_str else ["default"]
            run_type = input(f"  {BOLD}run_type{RESET} (python/shell/node) [{GREEN}python{RESET}]: ").strip() or "python"

            ok = add_tool(name=name, description=desc, category=cat,
                          actions=actions, run_type=run_type)
            if ok:
                print(f"  {GREEN}created tool: {name}{RESET}")
                print(f"  {DIM}edit code with: /tools code {name}{RESET}")
            else:
                print(f"  {RED}failed to create tool{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    if verb == "code":
        name = rest.strip()
        if not name:
            print("  usage: /tools code <name>")
            return
        try:
            from agent.threads.form.schema import get_executable_code
            code = get_executable_code(name)
            if code:
                print(f"  {BOLD}{name} code:{RESET}")
                print(f"  {'─' * 60}")
                for line in code.splitlines():
                    print(f"  {line}")
                print(f"  {'─' * 60}")
            else:
                print(f"  {DIM}no code for {name}{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    if verb == "toggle":
        name = rest.strip()
        if not name:
            print("  usage: /tools toggle <name>")
            return
        try:
            from agent.threads.form.schema import get_tool, update_tool
            tool = get_tool(name)
            if not tool:
                print(f"  {RED}tool not found: {name}{RESET}")
                return
            new_state = not tool.get("enabled", True)
            update_tool(name, enabled=new_state)
            print(f"  {name} → {'enabled' if new_state else 'disabled'}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    if verb == "delete":
        name = rest.strip()
        if not name:
            print("  usage: /tools delete <name>")
            return
        try:
            from agent.threads.form.schema import remove_tool_definition
            ok = remove_tool_definition(name)
            print(f"  {'deleted' if ok else 'not found'}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    if verb == "categories":
        try:
            from agent.threads.form.schema import get_categories
            for c in get_categories():
                print(f"  {BOLD}{c['name']}{RESET}  {DIM}{c.get('description', '')}{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    if verb and verb not in ("list",):
        try:
            from agent.threads.form.schema import get_tool
            tool = get_tool(verb)
            if not tool:
                print(f"  {RED}tool not found: {verb}{RESET}")
                return
            enabled = GREEN + "on" + RESET if tool.get("enabled") else RED + "off" + RESET
            allowed = GREEN + "yes" + RESET if tool.get("allowed") else RED + "no" + RESET
            print(f"  {BOLD}{tool['name']}{RESET}  [{tool.get('category', '?')}]  {enabled}")
            print(f"  {DIM}{tool.get('description', '')}{RESET}")
            print(f"  run_type: {tool.get('run_type', '?')}  allowed: {allowed}  weight: {tool.get('weight', '?')}")
            actions = tool.get("actions", [])
            if actions:
                print(f"  actions: {', '.join(actions)}")
            env = tool.get("requires_env", [])
            if env:
                print(f"  requires_env: {', '.join(env)}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # Default: list all tools
    try:
        from agent.threads.form.schema import get_tools
        tools = get_tools()
        if not tools:
            print("  no tools — run /tools new to create one")
            return
        for t in tools:
            enabled = GREEN + "●" + RESET if t.get("enabled") else DIM + "○" + RESET
            actions = t.get("actions", [])
            act_str = f"  [{', '.join(actions)}]" if actions else ""
            print(f"  {enabled} {BOLD}{t['name']:20s}{RESET} {t.get('category', ''):14s} {t.get('run_type', ''):8s}{act_str}")
    except Exception as e:
        print(f"  {RED}error: {e}{RESET}")


COMMANDS = {
    "/tools": _cmd_tools,
}
