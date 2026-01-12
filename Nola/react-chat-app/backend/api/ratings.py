"""
Rating API - Thumbs up/down for messages
Thumbs up generates a fine-tuning example
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import json
from pathlib import Path
import sys

# Ensure project root is on path
project_root = Path(__file__).resolve().parents[4]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

router = APIRouter(prefix="/api/ratings", tags=["ratings"])

# Fine-tuning output file
FINETUNE_DIR = project_root / "finetune"
FINETUNE_DIR.mkdir(parents=True, exist_ok=True)
USER_APPROVED_FILE = FINETUNE_DIR / "user_approved.jsonl"
NEGATIVE_FEEDBACK_FILE = FINETUNE_DIR / "negative_feedback.jsonl"


class RatingRequest(BaseModel):
    """Request to rate a message."""
    message_id: str
    conversation_id: str
    rating: str  # "up" or "down"
    user_message: str  # The user's input that prompted this response
    assistant_message: str  # The assistant's response being rated
    system_prompt: Optional[str] = None  # System prompt if available
    reason: Optional[str] = None  # Reason for downvote


class RatingResponse(BaseModel):
    """Response after rating."""
    success: bool
    message: str
    finetune_saved: bool = False


def create_finetune_example(
    user_message: str,
    assistant_message: str,
    system_prompt: Optional[str] = None
) -> dict:
    """
    Create a fine-tuning example in the OpenAI/Ollama format.
    """
    messages = []
    
    # Add system message if provided
    if system_prompt:
        messages.append({
            "role": "system",
            "content": system_prompt
        })
    else:
        # Default Nola system prompt
        messages.append({
            "role": "system", 
            "content": "You are Nola, a helpful AI assistant. Be concise, supportive, and clarifying."
        })
    
    messages.append({
        "role": "user",
        "content": user_message
    })
    
    messages.append({
        "role": "assistant",
        "content": assistant_message
    })
    
    return {"messages": messages}


@router.post("/rate", response_model=RatingResponse)
async def rate_message(request: RatingRequest):
    """
    Rate a message thumbs up or thumbs down.
    Thumbs up saves as a fine-tuning example.
    """
    if request.rating not in ["up", "down"]:
        raise HTTPException(status_code=400, detail="Rating must be 'up' or 'down'")
    
    finetune_saved = False
    
    if request.rating == "up":
        # Create and save fine-tuning example
        example = create_finetune_example(
            user_message=request.user_message,
            assistant_message=request.assistant_message,
            system_prompt=request.system_prompt
        )
        
        # Append metadata
        example["_meta"] = {
            "message_id": request.message_id,
            "conversation_id": request.conversation_id,
            "rated_at": datetime.utcnow().isoformat(),
            "source": "user_approved"
        }
        
        # Append to JSONL file
        with open(USER_APPROVED_FILE, "a") as f:
            f.write(json.dumps(example) + "\n")
        
        finetune_saved = True
        message = "Response saved as training example"
    else:
        # Save negative feedback with reason
        feedback = {
            "message_id": request.message_id,
            "conversation_id": request.conversation_id,
            "user_message": request.user_message,
            "assistant_message": request.assistant_message,
            "reason": request.reason or "",
            "rated_at": datetime.utcnow().isoformat()
        }
        
        with open(NEGATIVE_FEEDBACK_FILE, "a") as f:
            f.write(json.dumps(feedback) + "\n")
        
        message = "Feedback recorded - thank you!"
    
    return RatingResponse(
        success=True,
        message=message,
        finetune_saved=finetune_saved
    )


@router.get("/stats")
async def get_rating_stats():
    """Get statistics about rated messages."""
    approved_count = 0
    if USER_APPROVED_FILE.exists():
        with open(USER_APPROVED_FILE, "r") as f:
            for line in f:
                if line.strip():
                    approved_count += 1
    
    negative_count = 0
    if NEGATIVE_FEEDBACK_FILE.exists():
        with open(NEGATIVE_FEEDBACK_FILE, "r") as f:
            for line in f:
                if line.strip():
                    negative_count += 1
    
    return {
        "total_approved": approved_count,
        "total_negative": negative_count,
        "approved_file": str(USER_APPROVED_FILE),
        "negative_file": str(NEGATIVE_FEEDBACK_FILE)
    }
