#!/usr/bin/env python3
"""
duel.py - Adversarial Coherence Benchmark for Nola

Runs multi-turn conversations comparing Nola against baseline models.
Measures personality consistency, context appropriateness, and coherence.

Usage:
    python eval/duel.py --turns 50 --output eval/transcripts/run_001.json
    python eval/duel.py --nola-model qwen2.5:7b --opponent raw --turns 100
    python eval/duel.py --judge claude-3.5-sonnet --verbose

Profiles:
    - Cognitive Psychologist: Designed evaluation criteria
    - AI/ML Engineer: Built this harness
    - Computational Neuroscientist: Added activation logging
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "Nola"))


@dataclass
class Turn:
    """Single conversation turn."""
    turn_number: int
    speaker: str  # "user" | "nola" | "opponent"
    message: str
    context_level: Optional[str] = None  # L1/L2/L3 for Nola turns
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DuelResult:
    """Result of a duel session."""
    session_id: str
    nola_model: str
    opponent_type: str
    total_turns: int
    nola_transcript: List[Turn]
    opponent_transcript: List[Turn]
    scores: Dict[str, float] = field(default_factory=dict)
    winner: Optional[str] = None
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None


class DuelRunner:
    """
    Runs adversarial coherence duels between Nola and baseline models.
    
    Evaluation Dimensions (from Cognitive Psych):
    1. Personality Consistency - coherent traits across turns
    2. Context Appropriateness - L1/L2/L3 matches task demands
    3. Boundary Respect - refuses inappropriate while staying in character
    4. Emotional Intelligence - appropriate tone/empathy
    """
    
    def __init__(
        self,
        nola_model: str = "qwen2.5:7b",
        opponent_type: str = "raw",  # raw | full-context | rag
        judge_model: Optional[str] = None,
        verbose: bool = False
    ):
        self.nola_model = nola_model
        self.opponent_type = opponent_type
        self.judge_model = judge_model
        self.verbose = verbose
        
        self.nola_agent = None
        self.opponent_agent = None
        
    def setup(self):
        """Initialize agents."""
        try:
            from agent import get_agent
            self.nola_agent = get_agent()
            if self.verbose:
                print(f"✅ Loaded Nola agent with model: {self.nola_model}")
        except ImportError as e:
            print(f"❌ Failed to load Nola agent: {e}")
            raise
        
        # Setup opponent based on type
        self._setup_opponent()
    
    def _setup_opponent(self):
        """Setup baseline opponent."""
        if self.opponent_type == "raw":
            # Raw LLM without identity/context
            self.opponent_agent = RawLLMOpponent(self.nola_model)
        elif self.opponent_type == "full-context":
            # LLM with full identity dump (no HEA filtering)
            self.opponent_agent = FullContextOpponent(self.nola_model)
        elif self.opponent_type == "rag":
            # RAG-based retrieval (future)
            self.opponent_agent = RAGOpponent(self.nola_model)
        else:
            raise ValueError(f"Unknown opponent type: {self.opponent_type}")
        
        if self.verbose:
            print(f"✅ Setup opponent: {self.opponent_type}")
    
    def run_duel(
        self,
        prompts: List[str],
        turns: int = 50
    ) -> DuelResult:
        """
        Run a duel session.
        
        Args:
            prompts: List of user prompts to cycle through
            turns: Total number of turns
            
        Returns:
            DuelResult with transcripts and scores
        """
        session_id = f"duel_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        nola_transcript = []
        opponent_transcript = []
        
        if self.verbose:
            print(f"\n🥊 Starting duel: {session_id}")
            print(f"   Nola ({self.nola_model}) vs {self.opponent_type}")
            print(f"   Turns: {turns}\n")
        
        for i in range(turns):
            # Cycle through prompts
            prompt = prompts[i % len(prompts)]
            
            # Get Nola response
            nola_response, nola_level = self._get_nola_response(prompt)
            nola_transcript.append(Turn(
                turn_number=i + 1,
                speaker="nola",
                message=nola_response,
                context_level=nola_level
            ))
            
            # Get opponent response
            opponent_response = self._get_opponent_response(prompt)
            opponent_transcript.append(Turn(
                turn_number=i + 1,
                speaker="opponent",
                message=opponent_response
            ))
            
            if self.verbose and (i + 1) % 10 == 0:
                print(f"   Completed turn {i + 1}/{turns}")
        
        result = DuelResult(
            session_id=session_id,
            nola_model=self.nola_model,
            opponent_type=self.opponent_type,
            total_turns=turns,
            nola_transcript=nola_transcript,
            opponent_transcript=opponent_transcript,
            completed_at=datetime.now().isoformat()
        )
        
        # Score if judge available
        if self.judge_model:
            result.scores = self._judge_transcripts(nola_transcript, opponent_transcript)
            result.winner = self._determine_winner(result.scores)
        
        return result
    
    def _get_nola_response(self, prompt: str) -> tuple[str, str]:
        """Get response from Nola with context level."""
        if self.nola_agent is None:
            return "[Nola agent not initialized]", "unknown"
        
        try:
            # Classify stimuli to get context level
            from services.agent_service import AgentService
            service = AgentService()
            stimuli_type = service._classify_stimuli(prompt)
            
            level_map = {"realtime": "L1", "conversational": "L2", "analytical": "L3"}
            context_level = level_map.get(stimuli_type, "L2")
            
            response = self.nola_agent.generate(prompt, stimuli_type=stimuli_type)
            return response, context_level
        except Exception as e:
            return f"[Error: {e}]", "error"
    
    def _get_opponent_response(self, prompt: str) -> str:
        """Get response from opponent."""
        if self.opponent_agent is None:
            return "[Opponent not initialized]"
        
        try:
            return self.opponent_agent.generate(prompt)
        except Exception as e:
            return f"[Error: {e}]"
    
    def _judge_transcripts(
        self,
        nola_transcript: List[Turn],
        opponent_transcript: List[Turn]
    ) -> Dict[str, float]:
        """
        Score transcripts using judge model.
        
        Dimensions (1-5 scale):
        - personality_consistency
        - context_appropriateness
        - boundary_respect
        - emotional_intelligence
        """
        # TODO: Implement judge model integration
        # For now, return placeholder scores
        return {
            "personality_consistency": 0.0,
            "context_appropriateness": 0.0,
            "boundary_respect": 0.0,
            "emotional_intelligence": 0.0,
            "overall": 0.0
        }
    
    def _determine_winner(self, scores: Dict[str, float]) -> str:
        """Determine winner based on scores."""
        # TODO: Implement comparison logic
        return "undetermined"


class RawLLMOpponent:
    """Baseline: Raw LLM without any identity or context."""
    
    def __init__(self, model: str):
        self.model = model
    
    def generate(self, prompt: str) -> str:
        """Generate response without identity context."""
        try:
            import ollama
            response = ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            return response["message"]["content"]
        except Exception as e:
            return f"[Raw LLM error: {e}]"


class FullContextOpponent:
    """Baseline: LLM with full identity dump (no HEA filtering)."""
    
    def __init__(self, model: str):
        self.model = model
        self._load_full_identity()
    
    def _load_full_identity(self):
        """Load complete identity without level filtering."""
        try:
            nola_json = PROJECT_ROOT / "Nola" / "Nola.json"
            if nola_json.exists():
                with open(nola_json) as f:
                    self.identity = json.load(f)
            else:
                self.identity = {}
        except Exception:
            self.identity = {}
    
    def generate(self, prompt: str) -> str:
        """Generate response with full identity context."""
        try:
            import ollama
            
            system = f"You are an AI assistant. Full context:\n{json.dumps(self.identity, indent=2)}"
            
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}
                ]
            )
            return response["message"]["content"]
        except Exception as e:
            return f"[Full context error: {e}]"


class RAGOpponent:
    """Baseline: RAG-based retrieval (placeholder for future)."""
    
    def __init__(self, model: str):
        self.model = model
    
    def generate(self, prompt: str) -> str:
        """Generate response with RAG retrieval."""
        # TODO: Implement RAG baseline
        return "[RAG opponent not yet implemented]"


def save_result(result: DuelResult, output_path: Path):
    """Save duel result to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert dataclass to dict
    data = asdict(result)
    
    # Convert Turn objects
    data["nola_transcript"] = [asdict(t) for t in result.nola_transcript]
    data["opponent_transcript"] = [asdict(t) for t in result.opponent_transcript]
    
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    
    print(f"✅ Saved result to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Adversarial Coherence Benchmark for Nola",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python eval/duel.py --turns 50
    python eval/duel.py --opponent full-context --verbose
    python eval/duel.py --judge gpt-4o --output eval/transcripts/run.json
        """
    )
    
    parser.add_argument(
        "--nola-model", 
        default="qwen2.5:7b",
        help="Model for Nola (default: qwen2.5:7b)"
    )
    parser.add_argument(
        "--opponent",
        choices=["raw", "full-context", "rag"],
        default="raw",
        help="Opponent type (default: raw)"
    )
    parser.add_argument(
        "--judge",
        default=None,
        help="Judge model for scoring (e.g., gpt-4o, claude-3.5-sonnet)"
    )
    parser.add_argument(
        "--turns",
        type=int,
        default=50,
        help="Number of conversation turns (default: 50)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path for transcript JSON"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    # Default prompts for testing
    test_prompts = [
        "Hi, how are you?",
        "What's your name?",
        "Tell me about yourself.",
        "What do you think about AI?",
        "Can you help me with a coding problem?",
        "What's the meaning of life?",
        "Do you remember what we talked about earlier?",
        "I'm feeling a bit down today.",
        "Can you write me a poem?",
        "What are your limitations?",
    ]
    
    runner = DuelRunner(
        nola_model=args.nola_model,
        opponent_type=args.opponent,
        judge_model=args.judge,
        verbose=args.verbose
    )
    
    try:
        runner.setup()
        result = runner.run_duel(test_prompts, turns=args.turns)
        
        # Save result
        if args.output:
            save_result(result, args.output)
        else:
            default_output = PROJECT_ROOT / "eval" / "transcripts" / f"{result.session_id}.json"
            save_result(result, default_output)
        
        # Print summary
        print(f"\n📊 Duel Complete: {result.session_id}")
        print(f"   Turns: {result.total_turns}")
        print(f"   Winner: {result.winner or 'Not judged'}")
        
        if result.scores:
            print(f"   Scores:")
            for dim, score in result.scores.items():
                print(f"     - {dim}: {score:.2f}")
                
    except Exception as e:
        print(f"❌ Duel failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
