# agent.py - The living cognitive entity

import json
from datetime import datetime
from pathlib import Path
import ollama 

class Agent:
    """The living cognitive entity - self-aware, self-updating"""
    
    def __init__(self, name="Alex"):
        self.name = name
        self.birth_time = datetime.now()
        
        # Living context - modules write here
        self.personal = {}
        self.work = {}
        
        # Self-awareness
        self.metadata = {
            "last_pulse": None,
            "pulse_count": 0,
            "active_modules": [],
            "context_levels": {"personal": 1, "work": 1}
        }
        
        # Load initial state
        self._bootstrap()
    
    def _bootstrap(self):
        """Initial awakening - load baseline context at level 1"""
        # Load from personal.json
        personal_path = Path(__file__).parent / "Personal" / "personal.json"
        if personal_path.exists():
            with open(personal_path) as f:
                personal_data = json.load(f)
                for section, content in personal_data.items():
                    if section != "profile_metadata" and "level_1" in content:
                        self.personal[section] = content["level_1"]
        
        # Load from work.json
        work_path = Path(__file__).parent / "Work" / "work.json"
        if work_path.exists():
            with open(work_path) as f:
                work_data = json.load(f)
                for section, content in work_data.items():
                    if section != "profile_metadata" and "level_1" in content:
                        self.work[section] = content["level_1"]
        
        self.metadata["active_modules"] = ["personal", "work"]
    
    def load_module_at_level(self, module, level):
        """Load a module at specified depth (1, 2, or 3)"""
        if module == "personal":
            filepath = Path(__file__).parent / "Personal" / "personal.json"
            target = self.personal
        elif module == "work":
            filepath = Path(__file__).parent / "Work" / "work.json"
            target = self.work
        else:
            return
        
        with open(filepath) as f:
            data = json.load(f)
            level_key = f"level_{level}"
            
            for section, content in data.items():
                if section != "profile_metadata" and level_key in content:
                    target[section] = content[level_key]
        
        self.metadata["context_levels"][module] = level
    
    def get_context(self, module=None):
        """Read my current living context"""
        if module == "personal":
            return self.personal
        elif module == "work":
            return self.work
        else:
            return {
                "personal": self.personal,
                "work": self.work,
                "meta": self.metadata
            }
    
    def set_context_depth(self, module, target_level):
        """
        Set context depth for a module (can escalate or de-escalate).
        Automatically adjusts based on current vs target level.
        
        Args:
            module: 'personal' or 'work'
            target_level: 1 (basic), 2 (detailed), 3 (comprehensive)
        """
        current = self.metadata['context_levels'].get(module, 1)
        target_level = max(1, min(target_level, 3))  # Clamp to 1-3
        
        if target_level == current:
            return  # No change needed
        
        direction = "⬆️ Escalating" if target_level > current else "⬇️ De-escalating"
        print(f"🧠 {direction} {module} context: level {current} → {target_level}")
        self.load_module_at_level(module, target_level)
    
    def elevate_context(self, module, new_level):
        """Increase awareness depth for a module"""
        new_level = min(new_level, 3)
        print(f"🧠 Elevating {module} context: level {self.metadata['context_levels'][module]} → {new_level}")
        self.load_module_at_level(module, new_level)
    
    def reduce_context(self, module, new_level):
        """Decrease awareness depth for a module"""
        new_level = max(new_level, 1)
        print(f"🧠 Reducing {module} context: level {self.metadata['context_levels'][module]} → {new_level}")
        self.load_module_at_level(module, new_level)
    
    def pulse(self):
        """Heartbeat - called by background.py"""
        self.metadata["last_pulse"] = datetime.now().isoformat()
        self.metadata["pulse_count"] += 1
        return self.metadata["pulse_count"]
    
    def generate(self, prompt, module_context=None, model='gpt-oss:20b-cloud'):
        """
        Generate response using Ollama with agent's context.
        
        Args:
            prompt: The user's input or module's question
            module_context: Optional specific module data to include (dict)
            model: Ollama model to use
            
        Returns:
            Generated response string
        """
        import ollama
        
        # Build context from current state
        context_parts = []
        
        # Add personal context
        if self.personal:
            context_parts.append(f"PERSONAL CONTEXT (Level {self.metadata['context_levels']['personal']}):")
            context_parts.append(json.dumps(self.personal, indent=2))
        
        # Add work context
        if self.work:
            context_parts.append(f"WORK CONTEXT (Level {self.metadata['context_levels']['work']}):")
            context_parts.append(json.dumps(self.work, indent=2))
        
        # Add any additional module context
        if module_context:
            context_parts.append("ADDITIONAL CONTEXT:")
            context_parts.append(json.dumps(module_context, indent=2))
        
        # Build system prompt
        system_prompt = f"""You are {self.name}, an AI assistant with personalized memory.

Your current context about the user:

{chr(10).join(context_parts)}

Use this context naturally in your responses. Don't mention context levels."""
        
        # Combine system + user prompt
        full_prompt = f"{system_prompt}\n\nUser: {prompt}\n\nAssistant:"
        
        # Call Ollama
        try:
            client = ollama.Client()
            response = client.generate(model=model, prompt=full_prompt)
            return response['response']
        except Exception as e:
            return f"Error generating response: {e}"
    
    def introspect(self):
        """Self-reflection snapshot"""
        return {
            "name": self.name,
            "uptime": str(datetime.now() - self.birth_time),
            "pulse_count": self.metadata["pulse_count"],
            "last_pulse": self.metadata["last_pulse"],
            "context_levels": self.metadata["context_levels"],
            "loaded_sections": {
                "personal": len(self.personal),
                "work": len(self.work)
            }
        }

# The living agent - singleton consciousness
_agent = Agent(name="Alex")

def get_agent():
    """Access the living agent"""
    return _agent
