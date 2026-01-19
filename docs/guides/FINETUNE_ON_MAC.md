# Fine-Tuning on Apple Silicon (M-Series)

This guide explains **how to teach your own AI model** using your Mac. We use a technique called **LoRA** (Low-Rank Adaptation) and a framework called **MLX**.

## 🎓 The Core Concepts

### 1. What is Fine-Tuning?
Standard LLMs (like Mistral 7B) are "Pre-trained" on the whole internet. They know *English*, but they don't know *You*.
Fine-tuning is like sending the model to a specialized graduate school. We aren't teaching it to speak; we are teaching it **your specific format and rules**.

### 2. Can my Mac do this?
**Yes.**
*   **The Problem:** Normal training requires massive GPU VRAM (40GB+) that laptops don't have.
*   **The Solution (QLoRA):** We use **Quantization** (shrinking the model to 4-bit) and **LoRA** (training only tiny adapter layers).
*   **The Mac Advantage:** Apple Silicon uses "Unified Memory". The GPU can access all 16GB+ of your System RAM.

### 3. What is LoRA?
Imagine the model's brain is a massive encyclopedia (7 Billion pages).
*   **Full Training:** Rewriting every page. (Expensive, slow).
*   **LoRA:** Sticking **Post-it notes** on the pages with corrections.
When we run the model, it reads the page *plus* your Post-it note changes. This is fast and cheap.

---

## 🛠️ The Setup

I have created an automated system for you in `/finetune`.

### Files Explained
*   **`mlx_config.yaml`**: The "syllabus" for the training. I have heavily annotated this file so you can learn what `Rank`, `Alpha`, and `Dropout` mean.
*   **`train_mac.sh`**: Extensive script that handles the plumbing (virtual environments, data splitting).
*   **`nola_combined.jsonl`**: Your textbook. The examples the AI will study.

---

## 🚀 How to Run It

1.  **Open Terminal** in the project folder.
2.  **Navigate** to the fine-tune directory:
    ```bash
    cd finetune
    ```
3.  **Run the script**:
    ```bash
    chmod +x train_mac.sh
    ./train_mac.sh
    ```

### What happens next?
1.  **Download:** It fetches the 4GB Mistral model.
2.  **Training:** You will see a progress bar.
    *   `Loss`: This number represents "How wrong is the model?" It should start high (e.g., 2.5) and go down (e.g., 0.8).
    *   **time/it**: How many seconds it takes to process one batch.
3.  **Completion:** After ~600 steps, it saves the "adapters" in a folder `adapters/`.

---

## 🌡️ Safety Note (Heat)
Your MacBook Air has no fan. During training, the M4 chip will work at 100%.
*   The chassis will get **hot**.
*   macOS will automatically slow the chip down ("throttle") if it gets too hot. **This is safe.**
*   *Tip:* Raise the laptop off the desk or point a desk fan at it for faster training.

---

## 🧪 Testing Your Model
Once done, test it to see if it follows your instructions:

```bash
# Activation (if not already actionable)
source venv-mlx/bin/activate

# Run
mlx_lm.generate \
  --model mlx-community/Mistral-7B-Instruct-v0.3-4bit \
  --adapter-path adapters \
  --prompt "Your Prompt Here"
```
