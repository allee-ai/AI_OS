"""
Fact Extractor
==============

Simple LLM-based fact extraction and storage.

NO regex parsing. LLM generates:
1. Key name (spaces → underscores)
2. L3 value (full detail)
3. L2 value (half summary)
4. L1 value (minimal)
5. Thread destination (identity or philosophy)

Dot notation is STRUCTURAL:
    identity_flat.user.favorite_color = "blue"
    → thread: identity
    → metadata_type: user
    → key: favorite_color
    → value: blue

Usage:
    from Nola.services.fact_extractor import extract_and_store_fact
    
    result = extract_and_store_fact("Sarah mentioned she likes coffee")
    # Returns: {
    #     "stored": True,
    #     "path": "identity.people.sarah_likes_coffee",
    #     "l1": "sarah/coffee",
    #     "l2": "Sarah likes coffee",
    #     "l3": "Sarah mentioned she likes coffee in conversation"
    # }
"""

import os
import json
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone

# Small model for extraction - llama3.2:3b balances speed and quality
EXTRACT_MODEL = os.getenv("NOLA_EXTRACT_MODEL", "llama3.2:3b")


def _call_llm(prompt: str, model: str = None) -> str:
    """Call LLM and return response text."""
    model = model or EXTRACT_MODEL
    try:
        import ollama
        response = ollama.generate(model=model, prompt=prompt)
        return response.get('response', '').strip()
    except Exception as e:
        print(f"LLM call failed: {e}")
        return ""


def extract_key(fact_text: str) -> str:
    """
    Ask LLM: What's the key name for this fact?
    
    Returns simple underscore-separated key.
    """
    prompt = f"""Generate a database key for this fact. Reply with ONLY the key, nothing else.

Rules:
- 2-4 lowercase words
- Separated by underscores
- No explanation

Fact: "{fact_text}"

Examples:
Fact: "User likes Python" → user_likes_python
Fact: "Sarah's favorite color is blue" → sarah_favorite_color
Fact: "Meeting scheduled for Friday" → friday_meeting

Key:"""

    response = _call_llm(prompt)
    
    # Clean: lowercase, replace spaces with _, remove non-alphanumeric except _
    key = response.lower().strip()
    key = key.replace(' ', '_').replace('-', '_')
    key = ''.join(c for c in key if c.isalnum() or c == '_')
    key = key.strip('_')
    
    return key or "unknown_fact"


def extract_value_levels(fact_text: str) -> Tuple[str, str, str]:
    """
    Ask LLM to generate 3 levels of detail.
    
    Returns (l1, l2, l3) where:
    - L3: Full detail (the fact as stated or slightly expanded)
    - L2: Half the length - key info only
    - L1: Minimal - keywords or phrase
    """
    prompt = f"""Summarize this fact at 3 detail levels:

Fact: "{fact_text}"

L3 (full): The complete fact with context
L2 (medium): Key information only, half the length
L1 (minimal): 2-5 words or keywords

Format your response exactly like:
L3: [full version]
L2: [medium version]
L1: [minimal version]"""

    response = _call_llm(prompt)
    
    # Parse response
    l1, l2, l3 = "", "", fact_text
    
    for line in response.split('\n'):
        line = line.strip()
        if line.lower().startswith('l3:'):
            l3 = line[3:].strip()
        elif line.lower().startswith('l2:'):
            l2 = line[3:].strip()
        elif line.lower().startswith('l1:'):
            l1 = line[3:].strip()
    
    # Fallbacks
    if not l3:
        l3 = fact_text
    if not l2:
        l2 = fact_text[:len(fact_text)//2] if len(fact_text) > 20 else fact_text
    if not l1:
        words = fact_text.split()[:3]
        l1 = '/'.join(words) if words else fact_text[:20]
    
    return l1, l2, l3


def classify_thread(fact_text: str) -> Tuple[str, str]:
    """
    Ask LLM: Which thread and metadata_type should this go in?
    
    Returns (thread, metadata_type):
    - thread: "identity" or "philosophy"
    - metadata_type: sub-category like "user", "people", "preferences", "beliefs"
    """
    prompt = f"""Classify this fact. Reply with EXACTLY two words, nothing else.

Fact: "{fact_text}"

First word (thread):
- identity = facts about people, preferences, relationships
- philosophy = beliefs, values, opinions

Second word (type):
- user = about the user
- people = about others
- preferences = likes/dislikes
- work = job/projects
- beliefs = values/opinions

Examples:
"User likes coffee" → identity preferences
"Honesty matters most" → philosophy beliefs
"Alex works at Google" → identity people

Classification:"""

    response = _call_llm(prompt)
    
    parts = response.lower().strip().split()
    
    # Parse thread
    thread = "identity"  # default
    if parts:
        if "philosophy" in parts[0]:
            thread = "philosophy"
    
    # Parse metadata_type
    metadata_type = "general"
    valid_types = ["user", "people", "preferences", "work", "beliefs", "principles", "general"]
    if len(parts) > 1:
        for t in valid_types:
            if t in parts[1]:
                metadata_type = t
                break
    
    return thread, metadata_type


def extract_fact(fact_text: str) -> Dict[str, Any]:
    """
    Extract all components from a fact.
    
    Returns:
        {
            "key": "sarah_favorite_color",
            "l1": "sarah/blue",
            "l2": "Sarah's favorite color is blue",
            "l3": "Sarah mentioned her favorite color is blue during our chat",
            "thread": "identity",
            "metadata_type": "people",
            "full_path": "identity.people.sarah_favorite_color"
        }
    """
    # Extract components (could parallelize these calls)
    key = extract_key(fact_text)
    l1, l2, l3 = extract_value_levels(fact_text)
    thread, metadata_type = classify_thread(fact_text)
    
    full_path = f"{thread}.{metadata_type}.{key}"
    
    return {
        "key": key,
        "l1": l1,
        "l2": l2,
        "l3": l3,
        "thread": thread,
        "metadata_type": metadata_type,
        "full_path": full_path,
        "original": fact_text,
        "extracted_at": datetime.now(timezone.utc).isoformat()
    }


def store_fact(extracted: Dict[str, Any], weight: float = 0.5) -> bool:
    """
    Store an extracted fact in the appropriate thread table.
    
    Uses identity_flat or philosophy_flat based on thread.
    """
    thread = extracted.get("thread", "identity")
    
    try:
        if thread == "identity":
            from Nola.threads.identity.schema import push_profile_fact
            push_profile_fact(
                profile_id="user.primary",  # Default user profile
                key=extracted["key"],
                fact_type=extracted["metadata_type"],
                l1_value=extracted["l1"],
                l2_value=extracted["l2"],
                l3_value=extracted["l3"],
                weight=weight
            )
        elif thread == "philosophy":
            from Nola.threads.philosophy.schema import push_philosophy_profile_fact
            push_philosophy_profile_fact(
                profile_id="nola.core",  # Default philosophy profile
                key=extracted["key"],
                l1_value=extracted["l1"],
                l2_value=extracted["l2"],
                l3_value=extracted["l3"],
                weight=weight
            )
        else:
            print(f"Unknown thread: {thread}")
            return False
        
        return True
        
    except Exception as e:
        print(f"Failed to store fact: {e}")
        return False


def extract_and_store_fact(
    fact_text: str,
    weight: float = 0.5,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Main entry point: Extract a fact and store it.
    
    Args:
        fact_text: The raw fact text
        weight: Initial weight (0.0-1.0)
        dry_run: If True, extract but don't store
    
    Returns:
        {
            "stored": bool,
            "path": "identity.people.key",
            "l1": "...",
            "l2": "...",
            "l3": "...",
            ...
        }
    """
    extracted = extract_fact(fact_text)
    
    if dry_run:
        extracted["stored"] = False
        extracted["dry_run"] = True
        return extracted
    
    stored = store_fact(extracted, weight=weight)
    extracted["stored"] = stored
    
    # Log the extraction
    try:
        from Nola.threads.log import log_event
        log_event(
            "memory",
            f"Stored fact: {extracted['full_path']}",
            {
                "key": extracted["key"],
                "thread": extracted["thread"],
                "l1": extracted["l1"],
                "weight": weight
            },
            source="fact_extractor"
        )
    except Exception:
        pass
    
    return extracted


def extract_facts_from_conversation(
    user_input: str,
    agent_response: str,
    dry_run: bool = False
) -> list:
    """
    Extract multiple facts from a conversation turn.
    
    First asks LLM to identify facts, then extracts each one.
    """
    prompt = f"""What new, permanent facts can be learned from this exchange?
Focus on facts about the USER (preferences, biographical info, relationships, projects).
Do NOT include temporary/trivial info or facts about the AI.

User: {user_input}
Assistant: {agent_response}

List each fact on its own line. If no facts, write "NONE".
Facts:"""

    response = _call_llm(prompt)
    
    if "none" in response.lower() and len(response) < 20:
        return []
    
    # Parse facts (one per line)
    facts = []
    for line in response.strip().split('\n'):
        line = line.strip()
        # Skip empty, numbered prefixes, bullet points
        if not line:
            continue
        line = line.lstrip('0123456789.-•*) ')
        if len(line) > 10:  # Meaningful content
            facts.append(line)
    
    # Extract and store each fact
    results = []
    for fact in facts[:5]:  # Limit to 5 facts per turn
        result = extract_and_store_fact(fact, dry_run=dry_run)
        results.append(result)
    
    return results


# ============================================================================
# CLI Testing
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        fact = " ".join(sys.argv[1:])
    else:
        fact = "Sarah mentioned she loves hiking in the mountains"
    
    print(f"\n📝 Extracting: {fact}\n")
    
    result = extract_and_store_fact(fact, dry_run=True)
    
    print(f"Path: {result['full_path']}")
    print(f"Key:  {result['key']}")
    print(f"L1:   {result['l1']}")
    print(f"L2:   {result['l2']}")
    print(f"L3:   {result['l3']}")
    print(f"Thread: {result['thread']}")
    print(f"Type:   {result['metadata_type']}")
