#!/usr/bin/env python3
"""
Simple Demo: Agent that knows you
Shows layered context loading without LLM (pure demonstration)
"""

from agent import get_agent
import json

def demo():
    print("=" * 60)
    print("DEMO: Personal AI with Layered Context")
    print("=" * 60)
    print()
    
    # Get the living agent
    agent = get_agent()
    
    print(f"👋 Agent '{agent.name}' has awakened!")
    print()
    
    # Show initial state (level 1)
    print("📊 Initial State (Level 1 - Basic Context):")
    print("-" * 60)
    context = agent.get_context()
    print(f"Personal sections loaded: {len(context['personal'])}")
    print(f"Work sections loaded: {len(context['work'])}")
    print()
    print("Sample personal context:")
    print(f"  Identity: {context['personal'].get('identity', 'N/A')}")
    print()
    print("Sample work context:")
    print(f"  Role: {context['work'].get('current_role', 'N/A')}")
    print()
    
    # Simulate: User talks about work stress
    print("💬 User: 'I'm stressed about the project deadline'")
    print()
    
    # Agent decides to elevate work context
    print("🤔 Agent detects work-related topic...")
    agent.elevate_context("work", 2)
    print()
    
    # Show elevated context
    print("📊 Work Context Now at Level 2:")
    print("-" * 60)
    work_ctx = agent.get_context("work")
    print(f"Active Projects: {work_ctx.get('active_projects', 'N/A')}")
    print(f"Work Schedule: {work_ctx.get('work_schedule', 'N/A')}")
    print()
    
    # Simulate: User asks detailed question
    print("💬 User: 'What's my manager's name again?'")
    print()
    
    # Agent elevates to level 3 for detailed relationships
    print("🤔 Agent needs detailed work relationships...")
    agent.elevate_context("work", 3)
    print()
    
    print("📊 Work Context Now at Level 3:")
    print("-" * 60)
    work_ctx_3 = agent.get_context("work")
    relationships = work_ctx_3.get('work_relationships', {})
    if isinstance(relationships, dict) and 'key_stakeholders' in relationships:
        stakeholders = relationships['key_stakeholders']
        manager = next((s for s in stakeholders if 'manager' in s.get('role', '').lower()), None)
        if manager:
            print(f"Manager: {manager.get('name')} - {manager.get('role')}")
            print(f"Relationship: {manager.get('relationship')}")
    print()
    
    # Show introspection
    print("🧠 Agent Introspection:")
    print("-" * 60)
    intro = agent.introspect()
    print(json.dumps(intro, indent=2))
    print()
    
    print("=" * 60)
    print("✅ Demo Complete!")
    print()
    print("Key Takeaway:")
    print("  The agent dynamically loads context depth based on need.")
    print("  Level 1: Quick summary (low tokens)")
    print("  Level 2: Operational details (medium tokens)")
    print("  Level 3: Deep context (high tokens, when needed)")
    print("=" * 60)

if __name__ == "__main__":
    demo()
