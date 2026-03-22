#!/bin/bash
# =============================================================================
#  Auto-Fuse: Wait for SFT training to finish, find best checkpoint, fuse it
# =============================================================================

cd "$(dirname "$0")/.."  # AI_OS root

SFT_DIR="finetune/runs/smol-135m-sft"
PRETRAINED="finetune/runs/smol-135m-pretrained"
FINAL="finetune/runs/smol-135m-final"
LOG="$SFT_DIR/training.log"

echo "=== Auto-Fuse Monitor ==="
echo "Watching: $LOG"
echo ""

# ── Step 1: Wait for training to finish ──────────────────────────────────
# Training is done when we see the final iter (2000) in the log
# We check every 60 seconds

while true; do
    # Is the mlx_lm process still running?
    if ! pgrep -f "mlx_lm lora" > /dev/null 2>&1; then
        echo "Training process exited."
        break
    fi
    
    # Show latest iter for fun
    LATEST=$(grep "^Iter" "$LOG" 2>/dev/null | tail -1)
    echo "[$(date +%H:%M)] $LATEST"
    
    sleep 60
done

echo ""
echo "=== Training Complete ==="
echo ""

# ── Step 2: Parse val losses, find best checkpoint ──────────────────────
# Val loss lines look like: "Iter 200: Val loss 2.456, Val took 7.074s"
# We want the iter with the lowest val loss

echo "Parsing validation losses..."
echo ""

# Extract all val loss lines: iter number and loss value
# grep pulls lines like "Iter 200: Val loss 2.456"
# awk extracts the iter number ($2 with colon stripped) and loss value ($5)

BEST_ITER=""
BEST_LOSS="999"

while IFS= read -r line; do
    # Extract iter number (field 2, strip colon)
    ITER=$(echo "$line" | awk '{print $2}' | tr -d ':')
    # Extract val loss (field 5, strip comma)  
    LOSS=$(echo "$line" | awk '{print $5}' | tr -d ',')
    
    echo "  Iter $ITER: val_loss = $LOSS"
    
    # Compare: is this loss lower than our best?
    # bash can't do float comparison, so we use awk
    IS_BETTER=$(awk "BEGIN {print ($LOSS < $BEST_LOSS) ? 1 : 0}")
    
    if [ "$IS_BETTER" = "1" ]; then
        BEST_ITER="$ITER"
        BEST_LOSS="$LOSS"
    fi
done < <(grep "Val loss" "$LOG")

echo ""
echo "Best checkpoint: iter $BEST_ITER (val_loss = $BEST_LOSS)"
echo ""

# ── Step 3: Find the checkpoint file ────────────────────────────────────
# Checkpoints are saved as: 0000500_adapters.safetensors, 0001000_adapters.safetensors, etc.
# The "latest" is also saved as adapters.safetensors (always the most recent save)
# We need to find the file matching BEST_ITER

# Pad iter to 7 digits: 500 -> 0000500
PADDED=$(printf "%07d" "$BEST_ITER")
BEST_FILE="$SFT_DIR/weights/${PADDED}_adapters.safetensors"

if [ ! -f "$BEST_FILE" ]; then
    echo "WARNING: Best checkpoint file not found: $BEST_FILE"
    echo "Available checkpoints:"
    ls "$SFT_DIR/weights/"*_adapters.safetensors 2>/dev/null
    echo ""
    echo "Falling back to latest checkpoint (adapters.safetensors)"
    BEST_FILE="$SFT_DIR/weights/adapters.safetensors"
fi

echo "Using: $BEST_FILE"
echo ""

# ── Step 4: Copy best checkpoint to a clean adapter dir ─────────────────
# mlx_lm fuse expects adapters.safetensors + adapter_config.json in a dir

BEST_DIR="$SFT_DIR/weights-best"
mkdir -p "$BEST_DIR"
cp "$BEST_FILE" "$BEST_DIR/adapters.safetensors"
cp "$SFT_DIR/weights/adapter_config.json" "$BEST_DIR/"

echo "Isolated best checkpoint to: $BEST_DIR"
echo ""

# ── Step 5: Fuse into final model ───────────────────────────────────────
# This merges the adapter weights back into the base model
# Input:  smol-135m-pretrained (Phase 1 output) + SFT adapter weights
# Output: smol-135m-final (standalone model, ready to use)

echo "Fusing weights into final model..."
python3 -m mlx_lm fuse \
    --model "$PRETRAINED" \
    --adapter-path "$BEST_DIR" \
    --save-path "$FINAL"

echo ""

# ── Step 6: Copy chat template to final model ──────────────────────────
# The fuse might not preserve our chat template addition, so ensure it's there
python3 -c "
import json
path = '$FINAL/tokenizer_config.json'
with open(path) as f:
    config = json.load(f)
if 'chat_template' not in config:
    config['chat_template'] = \"{% for message in messages %}{{'<|im_start|>' + message['role'] + '\n' + message['content'] + '<|im_end|>' + '\n'}}{% endfor %}{% if add_generation_prompt %}{{ '<|im_start|>assistant\n' }}{% endif %}\"
    with open(path, 'w') as f:
        json.dump(config, f, indent=2)
    print('Chat template added to final model')
else:
    print('Chat template already present')
"

echo ""
echo "=== DONE ==="
echo ""
echo "Final model: $FINAL"
echo ""
echo "Test it:"
echo "  python3 -m mlx_lm.generate \\"
echo "    --model $FINAL \\"
echo "    --prompt '<|im_start|>user"
echo "What are your cognitive threads?<|im_end|>"
echo "<|im_start|>assistant"
echo "'"
echo ""
echo "Or simpler:"
echo "  python3 -m mlx_lm.generate --model $FINAL --prompt 'What is Nola?'"
echo ""
