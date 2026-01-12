"""
Nola Training Module
====================

Self-generating training data from confident thread decisions.

The key insight: threads only log decisions they're confident about.
This creates perfectly aligned training data with zero synthetic examples.
"""

from .logger import (
    # Main API
    log_training_example,
    log_conversation_example,
    get_training_stats,
    export_for_finetuning,
    
    # Convenience functions
    log_identity_decision,
    log_philosophy_decision,
    log_linking_decision,
    
    # Categories
    TrainingCategory,
    
    # Constants
    DEFAULT_CONFIDENCE_THRESHOLD,
    TRAINING_DIR,
)

__all__ = [
    "log_training_example",
    "log_conversation_example", 
    "get_training_stats",
    "export_for_finetuning",
    "log_identity_decision",
    "log_philosophy_decision",
    "log_linking_decision",
    "TrainingCategory",
    "DEFAULT_CONFIDENCE_THRESHOLD",
    "TRAINING_DIR",
]
