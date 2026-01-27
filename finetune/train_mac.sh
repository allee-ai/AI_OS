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
pip install -U pip
pip install mlx-lm pandas

# 4. Prepare Data
# MLX requires two separate files: 'train.jsonl' (to learn from) and 'valid.jsonl' (to test against).
# You have 'state_obedience.jsonl', so we use this python snippet to split it 90/10.
echo "✂️  Splitting data..."
python3 -c "
import pandas as pd
import numpy as np

# Load combined data
try:
    df = pd.read_json('state_obedience.jsonl', lines=True)
    
    # Shuffle the data so we don't learn patterns based on order (e.g. all 'Greetings' first)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    
    # Split 90% for Training, 10% for Validation
    split_idx = int(len(df) * 0.9)
    train_df = df.iloc[:split_idx]
    valid_df = df.iloc[split_idx:]
    
    # Save the split files
    train_df.to_json('train.jsonl', orient='records', lines=True)
    valid_df.to_json('valid.jsonl', orient='records', lines=True)
    print(f'🌀 Created train.jsonl ({len(train_df)} rows) and valid.jsonl ({len(valid_df)} rows)')
except Exception as e:
    print(f'❌ Error processing data: {e}')
    exit(1)
"

# 5. Run Training
# This command starts the heavy lifting.
echo "🔥 Starting Training (Expect Heat!)..."
echo "ℹ️  Monitor limits with 'sudo powermetrics --samplers smc | grep -i \"CPU die temperature\"'"

# mlx_lm: The MLX LoRA training tool.
# --model: The base brain we download/use.
# --config: Your annotated yaml file.
# --train: Tells it to start learning.
# --data .: Tells it to look in the current folder (.) for train.jsonl.
mlx_lm.lora \
    --model mlx-community/Qwen2.5-1.5B-Instruct-4bit \
    --config mlx_config.yaml \
    --train \
    --data . 

echo "🌀 Training Complete. Adapters saved in 'adapters/'."
echo "   To test your new brain:"
echo "   mlx_lm.lora --model mlx-community/Qwen2.5-1.5B-Instruct-4bit --adapter-path adapters --prompt '== STATE == ...'"
