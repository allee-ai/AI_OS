"""Linking Core CLI — /graph, /mindmap"""

DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def _cmd_graph(query: str):
    if not query.strip():
        print("  usage: /graph <query>")
        return
    from agent.threads.linking_core.schema import spread_activate
    seeds = [w.strip() for w in query.strip().split() if w.strip()]
    results = spread_activate(seeds, max_hops=2)
    if not results:
        print("  no activations found")
        return
    ranked = sorted(results, key=lambda x: x["activation"], reverse=True)[:15]
    for entry in ranked:
        score = entry["activation"]
        concept = entry["concept"]
        bar = "█" * int(score * 20)
        print(f"  {score:.2f} {bar} {concept}")


def _cmd_mindmap(args: str):
    """Show the structural shape of the agent's mind."""
    tokens = args.strip().split()
    verb = tokens[0] if tokens else ""

    try:
        from agent.threads.linking_core.schema import get_structural_graph
        show_cross = (verb == "links")
        data = get_structural_graph(include_cross_links=show_cross)

        nodes = data["nodes"]
        structural = data["structural"]
        associative = data.get("associative", [])

        filter_thread = None
        if verb and verb not in ("links",):
            filter_thread = verb

        children: dict = {}
        for edge in structural:
            children.setdefault(edge["source"], []).append(edge["target"])

        thread_colors = {
            "identity": CYAN, "philosophy": YELLOW, "form": GREEN,
            "reflex": RED, "log": DIM, "linking_core": BOLD,
        }

        def _print_tree(node_id: str, indent: int = 0):
            node = next((n for n in nodes if n["id"] == node_id), None)
            if not node:
                return
            color = thread_colors.get(node["thread"], "")
            label = node["label"]
            value = node.get("data", {}).get("value", "")
            suffix = f"  = {value}" if value else ""
            kind_badge = f"[{node['kind']}]" if node["kind"] not in ("thread",) else ""
            weight = node.get("weight", 0)
            weight_str = f" w={weight:.1f}" if weight and node["kind"] == "fact" else ""
            prefix = "  " * indent
            print(f"{prefix}{color}{label}{RESET} {DIM}{kind_badge}{weight_str}{suffix}{RESET}")

            for child_id in children.get(node_id, []):
                _print_tree(child_id, indent + 1)

        thread_nodes = [n for n in nodes if n["kind"] == "thread"]
        for tn in sorted(thread_nodes, key=lambda n: n["id"]):
            if filter_thread and tn["id"] != filter_thread:
                continue
            _print_tree(tn["id"], indent=1)
            print()

        stats = data["stats"]
        print(f"{DIM}  {stats['node_count']} nodes, "
              f"{stats['structural_count']} structural edges, "
              f"{stats['associative_count']} associative edges{RESET}")

        if associative:
            cross_thread = [l for l in associative if l.get("cross_thread")]
            if cross_thread:
                print(f"\n  {BOLD}Cross-thread links:{RESET}")
                for link in cross_thread[:20]:
                    s = link["strength"]
                    bar = "█" * int(s * 15)
                    print(f"    {s:.2f} {bar}  {link['source']} ↔ {link['target']}")

    except Exception as e:
        print(f"  {RED}error: {e}{RESET}")


COMMANDS = {
    "/graph": _cmd_graph,
    "/mindmap": _cmd_mindmap,
}
