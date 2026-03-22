#!/bin/bash
# =============================================================================
#  AI_OS 120M Pretrain Pipeline
#  Phase 1: Continued pretraining on raw text (all code + conversations + docs)
#  Phase 2: SFT on instruction pairs (system knowledge + curated)
# =============================================================================
set -e

cd "$(dirname "$0")/.."  # AI_OS root
FINETUNE_DIR="finetune"
PRETRAIN_DIR="$FINETUNE_DIR/pretrain_data"
BASE_MODEL="$FINETUNE_DIR/runs/smol-135m-base"
FUSED_DIR="$FINETUNE_DIR/runs/smol-135m-pretrained"
SFT_DIR="$FINETUNE_DIR/runs/smol-135m-sft"

echo "============================================"
echo "  AI_OS 135M Pretrain + SFT Pipeline"
echo "============================================"

# ── Step 1: Build pretrain data ──────────────────────────────────────────
echo ""
echo ">>> Step 1: Building pretraining data..."
python3 "$FINETUNE_DIR/build_pretrain_data.py" --output "$PRETRAIN_DIR"

# ── Step 2: Download base model ──────────────────────────────────────────
echo ""
echo ">>> Step 2: Base model already converted at $BASE_MODEL"
if [ ! -f "$BASE_MODEL/model.safetensors" ]; then
  echo "ERROR: Base model not found. Run: python3 -m mlx_lm convert --hf-path HuggingFaceTB/SmolLM2-135M --mlx-path $BASE_MODEL"
  exit 1
fi
echo "  Model found. Proceeding..."

# ── Step 3: Continued pretraining (raw text, full weights) ───────────────
#  ~3.5M tokens, 135M params, batch 4, seq 2048
#  ~850 iters per epoch at batch 4, so 2500 iters ≈ ~3 epochs
echo ""
echo ">>> Step 3: Continued pretraining (full finetune on raw text)..."
echo "    This will take a few hours on M4 Air."
echo ""

python3 -m mlx_lm lora \
  --model "$BASE_MODEL" \
  --data "$PRETRAIN_DIR" \
  --train \
  --fine-tune-type full \
  --num-layers -1 \
  --batch-size 4 \
  --iters 2500 \
  --learning-rate 5e-5 \
  --steps-per-report 50 \
  --steps-per-eval 500 \
  --save-every 500 \
  --max-seq-length 2048 \
  --grad-checkpoint \
  --adapter-path "$PRETRAIN_DIR/weights" \
  --seed 42 2>&1 | tee "$PRETRAIN_DIR/training.log"

# ── Step 4: Fuse pretrained weights into standalone model ────────────────
echo ""
echo ">>> Step 4: Fusing pretrained weights..."
python3 -m mlx_lm fuse \
  --model "$BASE_MODEL" \
  --adapter-path "$PRETRAIN_DIR/weights" \
  --save-path "$FUSED_DIR"

echo "  Fused model saved to: $FUSED_DIR"

# ── Step 5: SFT on instruction pairs ────────────────────────────────────
#  Use the combined training data (system knowledge + curated pairs + conversation chunks)
#  from the runs/full-v1 directory
echo ""
echo ">>> Step 5: SFT on instruction pairs (full finetune)..."
echo "    Training on: $FINETUNE_DIR/runs/full-v1/train.jsonl"
echo ""

python3 -m mlx_lm lora \
  --model "$FUSED_DIR" \
  --data "$FINETUNE_DIR/runs/full-v1" \
  --train \
  --fine-tune-type full \
  --num-layers -1 \
  --batch-size 2 \
  --iters 2000 \
  --learning-rate 1e-5 \
  --steps-per-report 50 \
  --steps-per-eval 200 \
  --save-every 500 \
  --max-seq-length 2048 \
  --grad-checkpoint \
  --adapter-path "$SFT_DIR/weights" \
  --seed 42 2>&1 | tee "$SFT_DIR/training.log"

# ── Step 6: Fuse SFT weights ────────────────────────────────────────────
echo ""
echo ">>> Step 6: Fusing SFT weights into final model..."
mkdir -p "$FINETUNE_DIR/runs/smol-135m-final"
python3 -m mlx_lm fuse \
  --model "$FUSED_DIR" \
  --adapter-path "$SFT_DIR/weights" \
  --save-path "$FINETUNE_DIR/runs/smol-135m-final"

echo ""
echo "============================================"
echo "  PIPELINE COMPLETE"
echo "============================================"
echo "  Base model:      $BASE_MODEL"
echo "  Pretrained:      $FUSED_DIR"
echo "  SFT final:       $FINETUNE_DIR/runs/smol-135m-final"
echo ""
echo "  Test it:"
echo "    python3 -m mlx_lm.generate --model $FINETUNE_DIR/runs/smol-135m-final --prompt 'What are your cognitive threads?'"
echo ""
