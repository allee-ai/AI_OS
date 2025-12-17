# relevance.py - Embedding-based relevance scoring for context management
"""
Uses JSON keys as semantic tokens to create a 0-1 relevance scale.
Each thread (machineID, userID, identity) can have its own RelevanceIndex.

Flow:
1. Extract keys from JSON structure (flatten nested paths)
2. Embed keys once (cached to disk)
3. On conversation/stimulus start: embed the file content, score against keys
4. Set context_level based on overall relevance to identity topics

This runs ONCE at conversation start, not per-turn.
"""

import json
import numpy as np
from pathlib import Path
from typing import Optional


# -----------------------------------------------------------------------------
# Key Extraction
# -----------------------------------------------------------------------------

def extract_key_values(
    data: dict,
    prefix: str = "",
    max_depth: int = 2,
    skip_keys: set = None
) -> dict[str, str]:
    """Extract keys with their string values for richer embeddings.
    
    Returns dict mapping key paths to stringified values.
    This gives better embeddings than keys alone.
    """
    if skip_keys is None:
        skip_keys = {"metadata", "profile_metadata", "last_updated", "version", "source_file", "stale_threshold_seconds", "needs_sync", "status", "context_level"}
    
    result = {}
    
    for key, value in data.items():
        if key in skip_keys:
            continue
        
        path = f"{prefix}.{key}" if prefix else key
        
        # Convert value to string representation for embedding
        if isinstance(value, str):
            result[path] = f"{key}: {value}"
        elif isinstance(value, list):
            if all(isinstance(x, str) for x in value[:5]):  # first 5 items
                result[path] = f"{key}: {', '.join(value[:5])}"
            else:
                result[path] = key
        elif isinstance(value, dict) and max_depth > 0:
            # Add this level
            result[path] = key
            # Recurse
            result.update(extract_key_values(value, prefix=path, max_depth=max_depth - 1, skip_keys=skip_keys))
        else:
            result[path] = key
    
    return result


# -----------------------------------------------------------------------------
# Embedding Functions
# -----------------------------------------------------------------------------

def get_embeddings(texts: list[str], model: str = "nomic-embed-text") -> np.ndarray:
    """Get embeddings for a list of texts using Ollama.
    
    Args:
        texts: List of strings to embed
        model: Ollama embedding model name
    
    Returns:
        numpy array of shape (len(texts), embedding_dim)
    """
    try:
        import ollama
    except ImportError:
        raise ImportError("ollama package required. Run: pip install ollama")
    
    embeddings = []
    for text in texts:
        response = ollama.embeddings(model=model, prompt=text)
        embeddings.append(response['embedding'])
    
    return np.array(embeddings)


def get_embedding(text: str, model: str = "nomic-embed-text") -> np.ndarray:
    """Get embedding for a single text."""
    return get_embeddings([text], model=model)[0]


def cosine_similarities(query: np.ndarray, corpus: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between query and all corpus vectors.
    
    Args:
        query: Single embedding vector (embedding_dim,)
        corpus: Matrix of embeddings (n_items, embedding_dim)
    
    Returns:
        Array of similarities (n_items,)
    """
    query_norm = query / (np.linalg.norm(query) + 1e-9)
    corpus_norms = corpus / (np.linalg.norm(corpus, axis=1, keepdims=True) + 1e-9)
    return np.dot(corpus_norms, query_norm)


# -----------------------------------------------------------------------------
# Relevance Index (per-thread, cached to disk)
# -----------------------------------------------------------------------------

class RelevanceIndex:
    """Embedding-based relevance index for a JSON data source.
    
    Built once per thread, cached to disk. Used to score stimulus files.
    
    Usage:
        # Build and cache (do once)
        index = RelevanceIndex.from_json_file("identity_thread/userID/user.json")
        index.save("identity_thread/userID/user_index.json")
        
        # Load cached (fast)
        index = RelevanceIndex.load("identity_thread/userID/user_index.json")
        
        # Score a conversation/stimulus file
        scores = index.score_file("Stimuli/convo001.txt")
        level = index.get_context_level_for_file("Stimuli/convo001.txt")
    """
    
    def __init__(
        self,
        key_texts: dict[str, str],
        embeddings: np.ndarray,
        model: str = "nomic-embed-text"
    ):
        self.key_texts = key_texts
        self.keys = list(key_texts.keys())
        self.embeddings = embeddings
        self.model = model
    
    @classmethod
    def from_dict(
        cls,
        data: dict,
        model: str = "nomic-embed-text",
        max_depth: int = 2
    ) -> "RelevanceIndex":
        """Build index from a JSON dict."""
        key_texts = extract_key_values(data, max_depth=max_depth)
        
        if not key_texts:
            return cls({}, np.array([]), model)
        
        texts = list(key_texts.values())
        embeddings = get_embeddings(texts, model=model)
        
        return cls(key_texts, embeddings, model)
    
    @classmethod
    def from_json_file(
        cls,
        path: str | Path,
        model: str = "nomic-embed-text",
        max_depth: int = 2
    ) -> "RelevanceIndex":
        """Build index from a JSON file."""
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data, model=model, max_depth=max_depth)
    
    def score_text(self, content: str) -> dict[str, float]:
        """Score a text blob against all keys.
        
        Args:
            content: Full text content (conversation, email, etc.)
        
        Returns:
            Dict mapping key paths to relevance scores (0.0-1.0)
        """
        if len(self.keys) == 0:
            return {}
        
        # Embed the full content
        content_embedding = get_embedding(content, model=self.model)
        
        # Compute similarities against all keys
        similarities = cosine_similarities(content_embedding, self.embeddings)
        similarities = np.clip(similarities, 0, 1)
        
        return {key: float(sim) for key, sim in zip(self.keys, similarities)}
    
    def score_file(self, path: str | Path) -> dict[str, float]:
        """Score a stimulus file against all keys.
        
        Args:
            path: Path to a text file (conversation, email, etc.)
        
        Returns:
            Dict mapping key paths to relevance scores (0.0-1.0)
        """
        path = Path(path)
        content = path.read_text(encoding="utf-8")
        return self.score_text(content)
    
    def top_k(self, content: str, k: int = 5) -> list[tuple[str, float]]:
        """Get top-k most relevant keys for content."""
        scores = self.score_text(content)
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores[:k]
    
    def max_score(self, content: str) -> float:
        """Get the maximum relevance score for content."""
        scores = self.score_text(content)
        return max(scores.values()) if scores else 0.0
    
    def get_context_level(
        self,
        content: str,
        thresholds: tuple[float, float] = (0.3, 0.5)
    ) -> int:
        """Determine context level needed for content.
        
        Args:
            content: Text content to analyze
            thresholds: (level_2_threshold, level_3_threshold)
        
        Returns:
            Context level 1, 2, or 3
        """
        score = self.max_score(content)
        
        if score >= thresholds[1]:
            return 3
        elif score >= thresholds[0]:
            return 2
        else:
            return 1
    
    def get_context_level_for_file(
        self,
        path: str | Path,
        thresholds: tuple[float, float] = (0.3, 0.5)
    ) -> int:
        """Determine context level needed for a stimulus file."""
        path = Path(path)
        content = path.read_text(encoding="utf-8")
        return self.get_context_level(content, thresholds)
    
    def save(self, path: str | Path):
        """Save index to disk for fast loading."""
        path = Path(path)
        data = {
            "key_texts": self.key_texts,
            "embeddings": self.embeddings.tolist(),
            "model": self.model
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    
    @classmethod
    def load(cls, path: str | Path) -> "RelevanceIndex":
        """Load pre-computed index from disk."""
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            key_texts=data["key_texts"],
            embeddings=np.array(data["embeddings"]),
            model=data["model"]
        )


# -----------------------------------------------------------------------------
# Stimulus Analyzer (runs at conversation start)
# -----------------------------------------------------------------------------

class StimulusAnalyzer:
    """Analyzes stimulus files to determine context requirements.
    
    Runs ONCE at conversation/session start, not per-turn.
    
    Usage:
        analyzer = StimulusAnalyzer.from_defaults()
        
        # At conversation start:
        result = analyzer.analyze_file("Stimuli/convo001.txt")
        # result = {
        #     "context_level": 2,
        #     "max_score": 0.47,
        #     "relevant_topics": [("relationships.partner", 0.47), ...],
        #     "needs_sync": True
        # }
    """
    
    def __init__(self, thresholds: tuple[float, float] = (0.3, 0.5)):
        self.indices: dict[str, RelevanceIndex] = {}
        self.thresholds = thresholds
    
    def add_index(self, name: str, index: RelevanceIndex):
        """Register a relevance index for a thread."""
        self.indices[name] = index
    
    def analyze_text(self, content: str) -> dict:
        """Analyze text content and return context requirements.
        
        Args:
            content: Full text content to analyze
        
        Returns:
            {
                "context_level": 1|2|3,
                "max_score": float,
                "relevant_topics": [(key, score), ...],
                "scores_by_thread": {thread_name: {key: score}},
                "needs_sync": bool
            }
        """
        all_scores = {}
        scores_by_thread = {}
        max_score = 0.0
        
        for thread_name, index in self.indices.items():
            scores = index.score_text(content)
            scores_by_thread[thread_name] = scores
            for key, score in scores.items():
                all_scores[f"{thread_name}.{key}"] = score
                max_score = max(max_score, score)
        
        # Determine context level
        if max_score >= self.thresholds[1]:
            context_level = 3
        elif max_score >= self.thresholds[0]:
            context_level = 2
        else:
            context_level = 1
        
        # Get top relevant topics
        sorted_scores = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
        relevant_topics = sorted_scores[:10]
        
        return {
            "context_level": context_level,
            "max_score": max_score,
            "relevant_topics": relevant_topics,
            "scores_by_thread": scores_by_thread,
            "needs_sync": context_level > 1  # sync needed if beyond minimal
        }
    
    def analyze_file(self, path: str | Path) -> dict:
        """Analyze a stimulus file and return context requirements."""
        path = Path(path)
        content = path.read_text(encoding="utf-8")
        result = self.analyze_text(content)
        result["source_file"] = str(path)
        return result
    
    @classmethod
    def from_defaults(cls, base_path: str = ".", use_cache: bool = True) -> "StimulusAnalyzer":
        """Build analyzer with default thread indices.
        
        If cached indices exist, loads them. Otherwise builds and caches.
        
        Args:
            base_path: Root path of the project
            use_cache: Whether to use/create cached indices
        """
        base = Path(base_path)
        analyzer = cls()
        
        thread_configs = {
            "userID": {
                "json": base / "identity_thread/userID/user.json",
                "cache": base / "identity_thread/userID/user_index.json"
            },
            "machineID": {
                "json": base / "identity_thread/machineID/machineID.json",
                "cache": base / "identity_thread/machineID/machineID_index.json"
            },
        }
        
        for name, paths in thread_configs.items():
            try:
                # Try cache first
                if use_cache and paths["cache"].exists():
                    index = RelevanceIndex.load(paths["cache"])
                    print(f"✓ Loaded {name} index from cache ({len(index.keys)} keys)")
                elif paths["json"].exists():
                    # Build from JSON
                    print(f"  Building {name} index...")
                    index = RelevanceIndex.from_json_file(paths["json"])
                    if use_cache:
                        index.save(paths["cache"])
                        print(f"✓ Built and cached {name} index ({len(index.keys)} keys)")
                    else:
                        print(f"✓ Built {name} index ({len(index.keys)} keys)")
                else:
                    continue
                
                analyzer.add_index(name, index)
            except Exception as e:
                print(f"✗ Failed to load {name}: {e}")
        
        return analyzer
    
    def rebuild_cache(self, base_path: str = "."):
        """Force rebuild all cached indices."""
        base = Path(base_path)
        
        thread_configs = {
            "userID": {
                "json": base / "identity_thread/userID/user.json",
                "cache": base / "identity_thread/userID/user_index.json"
            },
            "machineID": {
                "json": base / "identity_thread/machineID/machineID.json",
                "cache": base / "identity_thread/machineID/machineID_index.json"
            },
        }
        
        for name, paths in thread_configs.items():
            if paths["json"].exists():
                print(f"  Rebuilding {name} index...")
                index = RelevanceIndex.from_json_file(paths["json"])
                index.save(paths["cache"])
                self.indices[name] = index
                print(f"✓ Rebuilt {name} index ({len(index.keys)} keys)")


# -----------------------------------------------------------------------------
# Convenience function for chat_demo integration
# -----------------------------------------------------------------------------

def analyze_conversation_start(
    convo_path: str | Path = None,
    convo_content: str = None,
    base_path: str = "."
) -> dict:
    """Analyze at conversation start to determine context level.
    
    Call this once when starting/resuming a conversation.
    
    Args:
        convo_path: Path to conversation file (e.g., Stimuli/convo001.txt)
        convo_content: Or pass content directly
        base_path: Root path for finding indices
    
    Returns:
        Analysis result with context_level, relevant_topics, etc.
    """
    analyzer = StimulusAnalyzer.from_defaults(base_path)
    
    if convo_path:
        return analyzer.analyze_file(convo_path)
    elif convo_content:
        return analyzer.analyze_text(convo_content)
    else:
        # No content yet (new conversation) - start minimal
        return {
            "context_level": 1,
            "max_score": 0.0,
            "relevant_topics": [],
            "scores_by_thread": {},
            "needs_sync": False,
            "source_file": None
        }


# -----------------------------------------------------------------------------
# CLI Test
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    
    print("Building stimulus analyzer...")
    analyzer = StimulusAnalyzer.from_defaults()
    
    if not analyzer.indices:
        print("No indices loaded. Make sure JSON files exist.")
        sys.exit(1)
    
    # Test with existing stimulus file if available
    stimuli_path = Path("Stimuli")
    test_files = list(stimuli_path.glob("*.txt")) if stimuli_path.exists() else []
    
    if test_files:
        print(f"\nAnalyzing: {test_files[0]}")
        result = analyzer.analyze_file(test_files[0])
        print(f"  Context Level: {result['context_level']}")
        print(f"  Max Score: {result['max_score']:.3f}")
        print(f"  Needs Sync: {result['needs_sync']}")
        print(f"  Top Topics:")
        for key, score in result['relevant_topics'][:5]:
            print(f"    {key}: {score:.3f}")
    
    # Test with sample content
    print("\n--- Testing sample content ---")
    test_contents = [
        "Hello, how are you today?",
        "I'm really stressed about the AccessibleUI project deadline. Sam thinks I'm overworking.",
        "Can you help me with some React and TypeScript code?",
    ]
    
    for content in test_contents:
        result = analyzer.analyze_text(content)
        print(f"\n'{content[:50]}...'")
        print(f"  → Level {result['context_level']} (max score: {result['max_score']:.3f})")
        if result['relevant_topics']:
            top_key, top_score = result['relevant_topics'][0]
            print(f"  → Top match: {top_key} ({top_score:.3f})")
