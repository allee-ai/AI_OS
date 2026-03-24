"""Python syntax highlighting test for the workspace FileViewer."""

from dataclasses import dataclass
from typing import Optional
import asyncio


@dataclass
class Agent:
    name: str
    model: str = "qwen2.5:7b"
    context_window: int = 32768
    enabled: bool = True

    @property
    def display_name(self) -> str:
        return f"{self.name} ({self.model})"


async def process_message(agent: Agent, message: str) -> Optional[str]:
    """Send a message through the agent pipeline."""
    if not agent.enabled:
        return None

    # Simulate async LLM call
    await asyncio.sleep(0.1)

    facts = {
        "identity": "I am Nola, a personal AI.",
        "philosophy": "Privacy-first, open-source.",
        "memory": f"Processing: {message[:50]}...",
    }

    return "\n".join(f"[{k}] {v}" for k, v in facts.items())


if __name__ == "__main__":
    agent = Agent(name="Nola")
    result = asyncio.run(process_message(agent, "Hello world"))
    print(result)
