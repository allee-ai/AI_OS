#!/bin/bash

# Setup script for CUDA Fine-tuning (Linux/WSL with NVIDIA GPU)
# Usage: ./train_cuda.sh
# Mirrors train_mac.sh but uses PyTorch + PEFT instead of MLX.
# Works on any machine with an NVIDIA GPU (even if it's running other tasks).

echo "🟢 Setting up AI OS Fine-Tuning for CUDA..."

# 1. Check for Python & nvidia-smi
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required."
    exit 1
fi

if ! command -v nvidia-smi &> /dev/null; then
    echo "⚠️  nvidia-smi not found. Training will fall back to CPU (very slow)."
    USE_CPU=1
else
    echo "🖥️  GPU detected:"
    nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader
    USE_CPU=0
fi

# 2. Virtual Environment
if [ ! -d "venv-cuda" ]; then
    echo "📦 Creating virtual environment 'venv-cuda'..."
    python3 -m venv venv-cuda
fi

source venv-cuda/bin/activate

# 3. Install PyTorch + PEFT
echo "⬇️  Installing PyTorch + PEFT + dependencies..."
pip install -U pip
pip install torch --index-url https://download.pytorch.org/whl/cu121 2>/dev/null || pip install torch
pip install transformers peft datasets accelerate bitsandbytes pandas trl

# 4. Prepare Data
DATA_FILE="${AIOS_FT_DATA:-aios_base.jsonl}"
if [ ! -f "$DATA_FILE" ]; then
    DATA_FILE="aios_combined.jsonl"
fi
if [ ! -f "$DATA_FILE" ]; then
    echo "❌ No training data found. Run export first."
    exit 1
fi
echo "✂️  Splitting $DATA_FILE..."
python3 -c "
import json, random

data_file = '$DATA_FILE'
with open(data_file) as f:
    rows = [json.loads(line) for line in f if line.strip()]

random.seed(42)
random.shuffle(rows)

split = int(len(rows) * 0.9)
train_rows = rows[:split]
valid_rows = rows[split:]

with open('train.jsonl', 'w') as f:
    for r in train_rows:
        f.write(json.dumps(r) + '\n')
with open('valid.jsonl', 'w') as f:
    for r in valid_rows:
        f.write(json.dumps(r) + '\n')

print(f'🌀 Created train.jsonl ({len(train_rows)} rows) and valid.jsonl ({len(valid_rows)} rows) from {data_file}')
"

# 5. Resolve model + adapter dir from env (set by API) or defaults
MODEL="${AIOS_FT_MODEL:-Qwen/Qwen2.5-1.5B-Instruct}"
ADAPTER_DIR="${AIOS_FT_ADAPTER_DIR:-adapters}"
RUN_NAME="${AIOS_FT_RUN_NAME:-manual}"
RUN_DIR="${AIOS_FT_RUN_DIR:-}"
RESUME_ADAPTER="${AIOS_FT_RESUME_ADAPTER:-}"
CONFIG_FILE="${AIOS_FT_CONFIG:-cuda_config.yaml}"

echo "🔥 Starting CUDA Training..."
echo "   Model:    $MODEL"
echo "   Adapter:  $ADAPTER_DIR"
echo "   Run:      $RUN_NAME"
echo "   Config:   $CONFIG_FILE"
if [ -n "$RESUME_ADAPTER" ]; then
    echo "   Resume:   $RESUME_ADAPTER"
fi

# 6. Run training via Python (reads cuda_config.yaml for hyperparams)
python3 - <<'TRAIN_SCRIPT'
import json, yaml, os, sys
from pathlib import Path

# Load config
config_path = os.environ.get("AIOS_FT_CONFIG", "cuda_config.yaml")
with open(config_path) as f:
    cfg = yaml.safe_load(f)

model_id = os.environ.get("AIOS_FT_MODEL", cfg.get("model", "Qwen/Qwen2.5-1.5B-Instruct"))
adapter_dir = os.environ.get("AIOS_FT_ADAPTER_DIR", "adapters")
resume_adapter = os.environ.get("AIOS_FT_RESUME_ADAPTER", "")
run_dir = os.environ.get("AIOS_FT_RUN_DIR", "")

lora = cfg.get("lora_parameters", {})
rank = lora.get("rank", 8)
alpha = lora.get("alpha", 16)
dropout = lora.get("dropout", 0.05)

batch_size = cfg.get("batch_size", 1)
grad_accum = cfg.get("grad_accumulation_steps", 4)
lr = float(cfg.get("learning_rate", 1e-5))
max_steps = cfg.get("iters", 700)
max_seq = cfg.get("max_seq_length", 1024)
warmup_steps = cfg.get("warmup", 50)
save_every = cfg.get("save_every", 100)
eval_every = cfg.get("steps_per_eval", 100)
log_every = cfg.get("steps_per_report", 25)
use_4bit = cfg.get("quantization", {}).get("load_in_4bit", True)

print(f"Loading model: {model_id}")
print(f"LoRA: r={rank}, alpha={alpha}, dropout={dropout}")
print(f"Training: {max_steps} steps, batch={batch_size}, grad_accum={grad_accum}, lr={lr}")

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, TaskType
from datasets import load_dataset

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Device: {device}")
if device == "cuda":
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB")

# Quantization config for 4-bit loading (saves VRAM)
bnb_config = None
if use_4bit and device == "cuda":
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    print("Using 4-bit quantization (QLoRA)")

# Load model + tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    model_id,
    quantization_config=bnb_config,
    device_map="auto" if device == "cuda" else None,
    torch_dtype=torch.bfloat16 if device == "cuda" else torch.float32,
    trust_remote_code=True,
)

# LoRA config
lora_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    r=rank,
    lora_alpha=alpha,
    lora_dropout=dropout,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    bias="none",
)

# Resume or init
if resume_adapter and Path(resume_adapter).exists():
    from peft import PeftModel
    model = PeftModel.from_pretrained(model, resume_adapter)
    print(f"Resumed from adapter: {resume_adapter}")
else:
    model = get_peft_model(model, lora_config)

trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
total = sum(p.numel() for p in model.parameters())
print(f"Parameters: {trainable:,} trainable / {total:,} total ({100*trainable/total:.2f}%)")

# Load data (chat-ml format: messages array)
def format_example(example):
    """Convert messages array to training text."""
    messages = example.get("messages", [])
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    return {"text": text}

dataset = load_dataset("json", data_files={"train": "train.jsonl", "validation": "valid.jsonl"})
dataset = dataset.map(format_example, remove_columns=dataset["train"].column_names)

def tokenize(example):
    out = tokenizer(example["text"], truncation=True, max_length=max_seq, padding=False)
    out["labels"] = out["input_ids"].copy()
    return out

dataset = dataset.map(tokenize, remove_columns=["text"])

# Training
from transformers import TrainingArguments, Trainer, TrainerCallback

output_dir = adapter_dir
os.makedirs(output_dir, exist_ok=True)

training_args = TrainingArguments(
    output_dir=output_dir,
    num_train_epochs=999,          # controlled by max_steps instead
    max_steps=max_steps,
    per_device_train_batch_size=batch_size,
    gradient_accumulation_steps=grad_accum,
    learning_rate=lr,
    warmup_steps=warmup_steps,
    lr_scheduler_type="cosine",
    logging_steps=log_every,
    eval_strategy="steps",
    eval_steps=eval_every,
    save_steps=save_every,
    save_total_limit=3,
    bf16=device == "cuda",
    optim="paged_adamw_8bit" if (use_4bit and device == "cuda") else "adamw_torch",
    gradient_checkpointing=True,
    report_to="none",
    seed=42,
    dataloader_pin_memory=False,
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=dataset["train"],
    eval_dataset=dataset["validation"],
    tokenizer=tokenizer,
)

print("Training started...")
trainer.train()
print("Training complete.")

# Save final adapter
model.save_pretrained(output_dir)
tokenizer.save_pretrained(output_dir)
print(f"Adapter saved to {output_dir}")

# Update run metadata
if run_dir and Path(run_dir).exists():
    meta_path = Path(run_dir) / "run_meta.json"
    if meta_path.exists():
        import datetime
        meta = json.loads(meta_path.read_text())
        meta["status"] = "completed"
        meta["completed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        meta["backend"] = "cuda"
        meta_path.write_text(json.dumps(meta, indent=2))

TRAIN_SCRIPT

TRAIN_EXIT=$?

# 7. Report status
if [ $TRAIN_EXIT -eq 0 ]; then
    echo "🌀 CUDA Training Complete. Adapters saved in '$ADAPTER_DIR'."
else
    # Update run metadata on failure
    if [ -n "$RUN_DIR" ] && [ -f "$RUN_DIR/run_meta.json" ]; then
        python3 -c "
import json, datetime
p = '$RUN_DIR/run_meta.json'
m = json.loads(open(p).read())
m['status'] = 'failed'
m['failed_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
m['backend'] = 'cuda'
open(p, 'w').write(json.dumps(m, indent=2))
"
    fi
    echo "❌ Training failed with exit code $TRAIN_EXIT"
fi

echo "   To test: python3 -c \"from transformers import pipeline; pipe = pipeline('text-generation', '$MODEL', device_map='auto'); print(pipe('== STATE ==')[0]['generated_text'])\""
