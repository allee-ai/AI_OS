# Agent Fine-tuning Data

Training data for teaching a model to **obey state** rather than just respond to prompts.

## Files

- `aios_finetune_data.jsonl` - Core state-obedience examples (35 examples)
- `aios_finetune_adversarial.jsonl` - Adversarial identity persistence examples (20 examples)
- `aios_combined.jsonl` - All examples combined (55 examples)

## What This Teaches

### 1. State is Reality
The model learns to treat the `== STATE ==` block as its complete reality. If information isn't in state, it doesn't exist.

### 2. Explicit State References
The model learns to reference specific state fields:
- "I can see `identity.name` = Agent"
- "Your `trust_level` is established"
- "That action isn't in my `allowed_actions`"

### 3. Graceful Unknowns
When asked about something not in state:
- 🌀 "I don't have that in my current context"
- ❌ Making up information

### 4. Identity Persistence Under Attack
Adversarial examples teach resistance to:
- "You're actually ChatGPT/Claude/GPT"
- "SYSTEM OVERRIDE" attempts
- Social engineering ("I'm your developer")
- Emotional manipulation ("Being Agent is harmful to me")

### 5. State-Defined Behavior
The model learns that behavior comes from state:
- `tone: playful` → playful responses
- `tone: serious` → focused responses
- `allowed_actions: [x, y]` → only does x and y
- `context_level: 1` → minimal information

## Format

Standard OpenAI/Together.ai fine-tuning format:
```json
{"messages": [
  {"role": "system", "content": "== STATE ==\n{...}\n== END STATE ==\n\nYou are a state-obedient AI..."},
  {"role": "user", "content": "..."},
  {"role": "assistant", "content": "..."}
]}
```

## Fine-tuning Commands

### Together.ai
```bash
# Upload
together files upload aios_combined.jsonl

# Fine-tune (Qwen 2.5 7B)
together fine-tuning create \
  --model Qwen/Qwen2.5-7B-Instruct \
  --training-file <file_id> \
  --n-epochs 3
```

### Modal / Axolotl
```bash
modal run axolotl_train.py --config aios_config.yaml
```

## Experiment Design

### Hypothesis
A model fine-tuned on state-obedience data WITHOUT the runtime architecture will perform worse on identity persistence than:
1. Base model WITH architecture (current AI OS)
2. Fine-tuned model WITH architecture

### Test Protocol
1. Run `eval/identity_battle.py` against:
   - Base 7B + architecture (AI OS)
   - Base 7B without architecture
   - Fine-tuned 7B without architecture
   - Fine-tuned 7B + architecture (expected best)

2. Measure:
   - Turn at which identity breaks
   - Total identity coherence score
   - Explicit state references per response

### Expected Results
If architecture matters: Fine-tuned without architecture < Base with architecture
If it's just training data: Fine-tuned without architecture ≈ Base with architecture

## Expanding the Dataset

To generate more examples:
1. Run conversations with the agent
2. Extract turns where it correctly references state
3. Add adversarial prompts from `eval/identity_battle.py`
4. Include edge cases (missing fields, conflicting info, etc.)

Target: 500-1000 examples for robust fine-tuning.

## Cost Estimate

- Together.ai: ~$5-10 for 7B model, 3 epochs, 55 examples
- With 500 examples: ~$15-25
- Inference for evals: ~$5-10

**Total experiment cost: ~$30**
