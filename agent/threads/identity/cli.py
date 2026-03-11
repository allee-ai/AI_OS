"""Identity CLI — /identity"""

DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def _cmd_identity(args: str):
    """Manage identity profiles and facts."""
    tokens = args.strip().split(maxsplit=2)
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""
    extra = tokens[2] if len(tokens) > 2 else ""

    if verb == "new":
        try:
            from agent.threads.identity.schema import create_profile, get_profile_types
            types = get_profile_types()
            type_names = [t["type_name"] for t in types]
            print(f"  {DIM}types: {', '.join(type_names)}{RESET}")
            pid = input(f"  {BOLD}profile_id:{RESET} ").strip()
            if not pid:
                print("  cancelled")
                return
            tname = input(f"  {BOLD}type_name:{RESET} ").strip() or "self"
            dname = input(f"  {BOLD}display_name:{RESET} ").strip() or pid
            create_profile(pid, tname, dname)
            print(f"  {GREEN}created profile: {pid}{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    if verb == "fact":
        fact_tokens = (rest + " " + extra).strip().split(maxsplit=2)
        if len(fact_tokens) < 3:
            print("  usage: /identity fact <profile_id> <key> <value>")
            return
        profile_id, key, value = fact_tokens[0], fact_tokens[1], fact_tokens[2]
        try:
            from agent.threads.identity.schema import push_profile_fact
            push_profile_fact(profile_id, key, fact_type="trait",
                              l1_value=value[:60], l2_value=value)
            print(f"  {GREEN}saved{RESET} {profile_id}/{key}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    if verb == "delete":
        pid = rest.strip()
        if not pid:
            print("  usage: /identity delete <profile_id>")
            return
        try:
            from agent.threads.identity.schema import delete_profile
            ok = delete_profile(pid)
            print(f"  {'deleted' if ok else 'not found'}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    if verb:
        try:
            from agent.threads.identity.schema import pull_profile_facts
            facts = pull_profile_facts(profile_id=verb)
            if not facts:
                print(f"  {DIM}no facts for '{verb}'{RESET}")
                return
            for f in facts:
                val = f.get("l2_value") or f.get("l1_value") or ""
                w = f.get("weight", 0)
                print(f"  {DIM}[{f.get('fact_type', '?')}]{RESET} {BOLD}{f['key']}{RESET}: {val}  {DIM}w={w:.1f}{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # Default: list profiles
    try:
        from agent.threads.identity.schema import get_profiles
        profiles = get_profiles()
        if not profiles:
            print("  no profiles — run /identity new")
            return
        for p in profiles:
            print(f"  {BOLD}{p['profile_id']:20s}{RESET} [{p.get('type_name', '?')}]  {p.get('display_name', '')}")
    except Exception as e:
        print(f"  {RED}error: {e}{RESET}")


COMMANDS = {
    "/identity": _cmd_identity,
}
