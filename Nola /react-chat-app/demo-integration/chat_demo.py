#!/usr/bin/env python3
"""
Interactive Chat Demo with Ollama
Shows the agent using layered context with actual LLM responses
"""

from agent import get_agent
import json

def manage_context_depth(user_input, agent, turn_history):
    """
    Dynamically adjust context depth based on conversation.
    Escalates for relevant topics, de-escalates after topic shift.
    """
    work_keywords = ["project", "deadline", "manager", "team", "meeting", "sprint", "work", "colleague"]
    personal_keywords = ["therapy", "jordan", "anxiety", "climbing", "home", "partner", "relationship", "feel"]
    
    user_lower = user_input.lower()
    
    # Track what's relevant this turn
    work_relevant = any(kw in user_lower for kw in work_keywords)
    personal_relevant = any(kw in user_lower for kw in personal_keywords)
    
    # Work context management
    if work_relevant:
        # Deep detail needed?
        if any(word in user_lower for word in ["manager", "team member", "who", "name", "stakeholder"]):
            agent.set_context_depth('work', 3)
        else:
            agent.set_context_depth('work', 2)
    else:
        # De-escalate if not talked about work for 2+ turns
        if not any('work' in str(t).lower() for t in turn_history[-2:]):
            agent.set_context_depth('work', 1)
    
    # Personal context management
    if personal_relevant:
        # Deep detail needed?
        if any(word in user_lower for word in ["therapy", "anxiety", "relationship", "jordan", "mental health"]):
            agent.set_context_depth('personal', 3)
        else:
            agent.set_context_depth('personal', 2)
    else:
        # De-escalate if not talked about personal for 2+ turns
        if not any('personal' in str(t).lower() or any(kw in str(t).lower() for kw in personal_keywords) for t in turn_history[-2:]):
            agent.set_context_depth('personal', 1)

def chat():
    print("=" * 60)
    print("🤖 Interactive Chat with Layered Memory Agent")
    print("   Model: gpt-oss:20b-cloud")
    print("=" * 60)
    print()
    
    agent = get_agent()
    print(f"👋 Agent '{agent.name}' is ready!")
    print("   (Type 'quit' to exit, 'status' for agent info)")
    print()
    
    turn_history = []  # Track conversation for de-escalation
    
    while True:
        user_input = input("You: ").strip()
        
        if not user_input:
            continue
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Goodbye!")
            break
        
        if user_input.lower() == 'status':
            print("\n🧠 Agent Status:")
            print(json.dumps(agent.introspect(), indent=2))
            print()
            continue
        
        # Manage context depth (escalate OR de-escalate)
        manage_context_depth(user_input, agent, turn_history)
        
        # Generate response using agent's built-in method
        print(f"\n{agent.name}: ", end="", flush=True)
        response = agent.generate(user_input)
        print(response)
        print()
        
        # Track turn for de-escalation logic
        turn_history.append(user_input)
        if len(turn_history) > 5:  # Keep last 5 turns
            turn_history.pop(0)

if __name__ == "__main__":
    chat()
