#!/bin/bash

# Setup script for Mac M-Series Fine-tuning
# Usage: ./train_mac.sh
# This script automates the messy setup of Python environments and MLX commands.

echo "🍎 Setting up AI OS Fine-Tuning for Apple Silicon..."

# 1. Check for Python
# We need Python 3 installed on the system to proceed.
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required."
    exit 1
fi

# 2. Virtual Environment (clean dependency isolation)
# We create a folder 'venv-mlx' to hold our libraries so they don't mess up your system Python.
if [ ! -d "venv-mlx" ]; then
    echo "📦 Creating virtual environment 'venv-mlx'..."
    python3 -m venv venv-mlx
fi

# Activate the environment (make the terminal use the local python)
source venv-mlx/bin/activate

# 3. Install MLX Framework
# 'mlx-lm' is Apple's specialized library for Large Language Models on Silicon.
# It includes the 'lxm_lora' tool we use later.
echo "⬇️  Installing Apple MLX Framework..."
if command -v uv &> /dev/null; then
    uv pip install mlx-lm pandas
else
    pip install -U pip
    pip install mlx-lm pandas
fi

# 4. Prepare Data
# MLX requires two separate files: 'train.jsonl' (to learn from) and 'valid.jsonl' (to test against).
# Use aios_base.jsonl (system knowledge only, no personal data) if available, else fall back to combined.
DATA_FILE="${AIOS_FT_DATA:-aios_base.jsonl}"
if [ ! -f "$DATA_FILE" ]; then
    DATA_FILE="aios_combined.jsonl"
fi
echo "✂️  Splitting $DATA_FILE..."
python3 -c "
import pandas as pd
import numpy as np
import sys

data_file = '$DATA_FILE'

# Load combined data
try:
    df = pd.read_json(data_file, lines=True)
    
    # Shuffle the data so we don't learn patterns based on order (e.g. all 'Greetings' first)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    
    # Split 90% for Training, 10% for Validation
    split_idx = int(len(df) * 0.9)
    train_df = df.iloc[:split_idx]
    valid_df = df.iloc[split_idx:]
    
    # Save the split files
    train_df.to_json('train.jsonl', orient='records', lines=True)
    valid_df.to_json('valid.jsonl', orient='records', lines=True)
    print(f'🌀 Created train.jsonl ({len(train_df)} rows) and valid.jsonl ({len(valid_df)} rows) from {data_file}')
except Exception as e:
    print(f'❌ Error processing data: {e}')
    exit(1)
"

# 5. Resolve model + adapter dir from env (set by API) or defaults
MODEL="${AIOS_FT_MODEL:-mlx-community/Llama-3.2-3B-Instruct-4bit}"
ADAPTER_DIR="${AIOS_FT_ADAPTER_DIR:-adapters}"
RUN_NAME="${AIOS_FT_RUN_NAME:-manual}"
RUN_DIR="${AIOS_FT_RUN_DIR:-}"
RESUME_ADAPTER="${AIOS_FT_RESUME_ADAPTER:-}"

echo "🔥 Starting Training (Expect Heat!)..."
echo "   Model:    $MODEL"
echo "   Adapter:  $ADAPTER_DIR"
echo "   Run:      $RUN_NAME"
if [ -n "$RESUME_ADAPTER" ]; then
    echo "   Resume:   $RESUME_ADAPTER"
fi
echo "ℹ️  Monitor limits with 'sudo powermetrics --samplers smc | grep -i \"CPU die temperature\"'"

# mlx_lm.lora: The MLX LoRA training tool.
RESUME_FLAG=""
if [ -n "$RESUME_ADAPTER" ]; then
    RESUME_FLAG="--resume-adapter-file $RESUME_ADAPTER"
    echo "🔄 Resuming from adapter: $RESUME_ADAPTER"
fi

mlx_lm lora \
    --model "$MODEL" \
    --config mlx_config.yaml \
    --train \
    --data . \
    --adapter-path "$ADAPTER_DIR" \
    $RESUME_FLAG

TRAIN_EXIT=$?

# 6. Update run metadata with completion status
if [ -n "$RUN_DIR" ] && [ -f "$RUN_DIR/run_meta.json" ]; then
    if [ $TRAIN_EXIT -eq 0 ]; then
        python3 -c "
import json, datetime
p = '$RUN_DIR/run_meta.json'
m = json.loads(open(p).read())
m['status'] = 'completed'
m['completed_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
open(p, 'w').write(json.dumps(m, indent=2))
"
        echo "🌀 Training Complete. Adapters saved in '$ADAPTER_DIR'."
    else
        python3 -c "
import json, datetime
p = '$RUN_DIR/run_meta.json'
m = json.loads(open(p).read())
m['status'] = 'failed'
m['failed_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
open(p, 'w').write(json.dumps(m, indent=2))
"
        echo "❌ Training failed with exit code $TRAIN_EXIT"
    fi
fi

echo "   To test: mlx_lm lora --model $MODEL --adapter-path $ADAPTER_DIR --prompt '== STATE == ...'"
