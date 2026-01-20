#!/usr/bin/env python3
"""
Populate Nola's personal database from Allee.json profile.
Extracts identity, philosophy, and personal data into L1/L2/L3 fact structure.
"""

import json
import sys
from pathlib import Path

# Add project paths
sys.path.insert(0, str(Path(__file__).parent / "Nola" / "threads"))
sys.path.insert(0, str(Path(__file__).parent))

# Force personal mode
import os
os.environ["NOLA_MODE"] = "personal"

from Nola.threads.schema import (
    create_profile_type, create_profile, push_profile_fact,
    create_fact_type, get_profiles
)

def load_allee_json(path: str) -> dict:
    """Load Allee.json profile."""
    with open(path, 'r') as f:
        return json.load(f)

def seed_identity_profile_types():
    """Create identity profile types."""
    types = [
        ("core", 1, 1, False, "Core identity facts - name, pronouns, roles"),
        ("cognitive", 2, 2, False, "Thinking style and cognitive patterns"),
        ("personal", 2, 3, False, "Personal life and relationships"),
        ("technical", 3, 2, False, "Technical skills and tools"),
        ("superpowers", 2, 1, False, "Key strengths and unique abilities"),
        ("origin", 3, 3, False, "Background and origin story"),
    ]
    for name, trust, priority, can_edit, desc in types:
        create_profile_type(name, trust, priority, can_edit, desc)
    print(f"✅ Created {len(types)} identity profile types")

def seed_philosophy_profile_types():
    """Create philosophy profile types."""
    types = [
        ("mission", 1, 1, False, "Personal and public mission statements"),
        ("design", 2, 2, False, "Design principles and working style"),
        ("ethics", 1, 1, False, "Ethical guidelines and boundaries"),
        ("business", 3, 3, False, "Business identity and positioning"),
    ]
    for name, trust, priority, can_edit, desc in types:
        create_profile_type(name, trust, priority, can_edit, desc)
    print(f"✅ Created {len(types)} philosophy profile types")

def seed_fact_types():
    """Create fact types."""
    types = [
        ("trait", "A characteristic or attribute", 0.7),
        ("value", "A core value or belief", 0.8),
        ("skill", "A technical or soft skill", 0.6),
        ("relationship", "A relationship or connection", 0.9),
        ("preference", "A preference or style", 0.5),
        ("goal", "A goal or aspiration", 0.7),
        ("principle", "A guiding principle", 0.8),
        ("tool", "A tool or technology", 0.5),
    ]
    for name, desc, weight in types:
        create_fact_type(name, desc, weight)
    print(f"✅ Created {len(types)} fact types")

def seed_identity_profiles(data: dict):
    """Create identity profiles from Allee.json."""
    
    # Core identity profile
    create_profile("allee.core", "core", "Core Identity")
    identity = data.get("identity", {})
    
    push_profile_fact("allee.core", "name", "trait",
        l1_value=identity.get("public_name", "Allee"),
        l2_value=f"Legal name: {identity.get('legal_name', '')}",
        l3_value=identity.get("tagline", ""),
        weight=1.0
    )
    
    pronouns = identity.get("pronouns", [])
    push_profile_fact("allee.core", "pronouns", "trait",
        l1_value="/".join(pronouns) if pronouns else "they/she",
        l2_value="Primary pronouns for all contexts",
        weight=0.9
    )
    
    roles = identity.get("core_roles", [])
    for i, role in enumerate(roles):
        push_profile_fact("allee.core", f"role.{i+1}", "trait",
            l1_value=role,
            weight=0.8
        )
    
    # Cognitive profile
    create_profile("allee.cognitive", "cognitive", "Cognitive Style")
    cognitive = data.get("cognitive_profile", {})
    
    thinking = cognitive.get("thinking_style", [])
    push_profile_fact("allee.cognitive", "thinking_style", "trait",
        l1_value=thinking[0] if thinking else "",
        l2_value="; ".join(thinking[1:3]) if len(thinking) > 1 else "",
        l3_value="; ".join(thinking[3:]) if len(thinking) > 3 else "",
        weight=0.85
    )
    
    strengths = cognitive.get("strength_edge", [])
    push_profile_fact("allee.cognitive", "strength_edge", "trait",
        l1_value=strengths[0] if strengths else "",
        l2_value=strengths[1] if len(strengths) > 1 else "",
        l3_value=strengths[2] if len(strengths) > 2 else "",
        weight=0.8
    )
    
    weaknesses = cognitive.get("weakness_honesty", [])
    push_profile_fact("allee.cognitive", "growth_areas", "trait",
        l1_value=weaknesses[0] if weaknesses else "",
        l2_value=weaknesses[1] if len(weaknesses) > 1 else "",
        l3_value=weaknesses[2] if len(weaknesses) > 2 else "",
        weight=0.7
    )
    
    # Personal profile
    create_profile("allee.personal", "personal", "Personal Life")
    personal = data.get("personal_profile", {})
    relationships = personal.get("relationships", {})
    
    partner = relationships.get("partner", {})
    if partner:
        push_profile_fact("allee.personal", "partner", "relationship",
            l1_value=partner.get("name", ""),
            l2_value=partner.get("role", ""),
            l3_value=partner.get("importance", ""),
            weight=1.0
        )
    
    children = relationships.get("children", {})
    if children:
        names = children.get("names", [])
        push_profile_fact("allee.personal", "children", "relationship",
            l1_value=", ".join(names[:3]) if names else "",
            l2_value=", ".join(names[3:]) if len(names) > 3 else "",
            l3_value=children.get("importance", ""),
            weight=0.95
        )
    
    identity_core = personal.get("identity_core", {})
    push_profile_fact("allee.personal", "gender_identity", "trait",
        l1_value=identity_core.get("gender", ""),
        l2_value=identity_core.get("expression", ""),
        l3_value=identity_core.get("experience", ""),
        weight=0.9
    )
    
    # Superpowers profile
    create_profile("allee.superpowers", "superpowers", "Superpowers")
    superpowers = data.get("superpowers", {})
    
    for category, items in superpowers.items():
        if items:
            push_profile_fact("allee.superpowers", category, "skill",
                l1_value=items[0] if items else "",
                l2_value=items[1] if len(items) > 1 else "",
                l3_value="; ".join(items[2:]) if len(items) > 2 else "",
                weight=0.85
            )
    
    # Technical profile
    create_profile("allee.technical", "technical", "Technical Skills")
    technical = data.get("technical_profile", {})
    
    languages = technical.get("primary_languages", [])
    push_profile_fact("allee.technical", "languages", "tool",
        l1_value=languages[0] if languages else "",
        l2_value="; ".join(languages[1:]) if len(languages) > 1 else "",
        weight=0.8
    )
    
    frameworks = technical.get("frameworks_tools", [])
    push_profile_fact("allee.technical", "frameworks", "tool",
        l1_value="; ".join(frameworks[:3]) if frameworks else "",
        l2_value="; ".join(frameworks[3:6]) if len(frameworks) > 3 else "",
        l3_value="; ".join(frameworks[6:]) if len(frameworks) > 6 else "",
        weight=0.75
    )
    
    ai_focus = technical.get("ai_focus_areas", [])
    push_profile_fact("allee.technical", "ai_focus", "skill",
        l1_value=ai_focus[0] if ai_focus else "",
        l2_value="; ".join(ai_focus[1:3]) if len(ai_focus) > 1 else "",
        l3_value="; ".join(ai_focus[3:]) if len(ai_focus) > 3 else "",
        weight=0.85
    )
    
    # Origin profile
    create_profile("allee.origin", "origin", "Origin Story")
    origin = data.get("origin_story", {})
    
    push_profile_fact("allee.origin", "background", "trait",
        l1_value=origin.get("background", "")[:100],
        l2_value=origin.get("transition", "")[:150],
        l3_value=origin.get("motivation", ""),
        weight=0.7
    )
    
    print(f"✅ Created identity profiles with facts")

def seed_philosophy_profiles(data: dict):
    """Create philosophy profiles from Allee.json."""
    
    # Mission profile
    create_profile("allee.mission", "mission", "Mission")
    mission = data.get("mission", {})
    
    personal_mission = mission.get("personal_mission", [])
    push_profile_fact("allee.mission", "personal", "goal",
        l1_value=personal_mission[0] if personal_mission else "",
        l2_value=personal_mission[1] if len(personal_mission) > 1 else "",
        l3_value="; ".join(personal_mission[2:]) if len(personal_mission) > 2 else "",
        weight=1.0
    )
    
    public_mission = mission.get("public_mission", [])
    push_profile_fact("allee.mission", "public", "goal",
        l1_value=public_mission[0] if public_mission else "",
        l2_value=public_mission[1] if len(public_mission) > 1 else "",
        l3_value=public_mission[2] if len(public_mission) > 2 else "",
        weight=0.95
    )
    
    # Design principles profile
    create_profile("allee.design", "design", "Design Principles")
    principles = data.get("working_principles", {})
    
    design_principles = principles.get("design", [])
    push_profile_fact("allee.design", "core_principles", "principle",
        l1_value=design_principles[0] if design_principles else "",
        l2_value=design_principles[1] if len(design_principles) > 1 else "",
        l3_value="; ".join(design_principles[2:]) if len(design_principles) > 2 else "",
        weight=0.9
    )
    
    # Ethics profile  
    create_profile("allee.ethics", "ethics", "Ethics")
    ethics = principles.get("ethics", [])
    
    push_profile_fact("allee.ethics", "boundaries", "principle",
        l1_value=ethics[0] if ethics else "",
        l2_value=ethics[1] if len(ethics) > 1 else "",
        l3_value=ethics[2] if len(ethics) > 2 else "",
        weight=1.0
    )
    
    # Business profile
    create_profile("allee.business", "business", "Business Identity")
    business = data.get("business_identity", {})
    
    push_profile_fact("allee.business", "offer", "value",
        l1_value=business.get("offer", "")[:100],
        l2_value=business.get("current_work", "")[:150],
        weight=0.8
    )
    
    value_prop = business.get("value_proposition", [])
    push_profile_fact("allee.business", "value_proposition", "value",
        l1_value=value_prop[0] if value_prop else "",
        l2_value=value_prop[1] if len(value_prop) > 1 else "",
        l3_value=value_prop[2] if len(value_prop) > 2 else "",
        weight=0.85
    )
    
    positioning = data.get("competitive_positioning", {})
    differentiators = positioning.get("what_sets_me_apart", [])
    push_profile_fact("allee.business", "differentiators", "value",
        l1_value=differentiators[0] if differentiators else "",
        l2_value=differentiators[1] if len(differentiators) > 1 else "",
        l3_value=differentiators[2] if len(differentiators) > 2 else "",
        weight=0.8
    )
    
    print(f"✅ Created philosophy profiles with facts")

def main():
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Populate Nola database from Allee.json")
    parser.add_argument("json_path", help="Path to Allee.json file")
    args = parser.parse_args()
    
    print(f"📂 Loading profile from: {args.json_path}")
    data = load_allee_json(args.json_path)
    
    print("\n🔧 Creating profile types...")
    seed_identity_profile_types()
    seed_philosophy_profile_types()
    seed_fact_types()
    
    print("\n👤 Seeding identity profiles...")
    seed_identity_profiles(data)
    
    print("\n💭 Seeding philosophy profiles...")
    seed_philosophy_profiles(data)
    
    print("\n✨ Database population complete!")
    print("   Run your backend to see the new data in the UI.")

if __name__ == "__main__":
    main()
