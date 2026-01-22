# Evaluator Checklist (Progress)

## Core Requirements (Infrastructure & Backend)

### ✅ 1. Reproducible one-liner
**Status:** COMPLETE  
**Profile:** DevOps/Infrastructure  
**Completed:** Default model set to `qwen2.5:7b`, start.sh offers Local/Docker mode with auto-install

### ✅ 2. Pinned dependency versions
**Status:** COMPLETE  
**Profile:** Backend Developer  
**Completed:** Generated requirements.lock with SHA256 hashes, Dockerfile updated

### ✅ 3. CI badge (GitHub Actions)
**Status:** COMPLETE  
**Profile:** DevOps/Infrastructure  
**Completed:** .github/workflows/ci.yml created, badge in README.md

### ✅ 4. No hard-coded paths/secrets
**Status:** COMPLETE  
**Profile:** Backend Developer  
**Completed:** All paths use pathlib with __file__ relative resolution

### ✅ 5. Clean shutdown & logs
**Status:** COMPLETE  
**Profile:** DevOps/Infrastructure  
**Completed:** System prompt logging to logs/nola.system.log with 1MB rotation

### ⏳ 6. README.zh (Chinese technical docs)
**Status:** Not started  
**Profile:** GitHub Specialist  
**Tasks:**
- [ ] Translate core README concepts with proper terminology
- [ ] Use mainland terms: 大模型, 推理能力, 人格一致性
- [ ] Keep technical depth, adapt examples for CN engineering culture

---

## Evaluation & Benchmark Requirements (Cross-Functional)

### ✅ 7. Test Suite Setup
**Status:** COMPLETE  
**Lead Profile:** Backend Developer  
**Supporting:** AI/ML Engineer  
**Tasks:**
- [x] Create root-level `tests/` directory structure
- [x] Set up pytest with conftest.py fixtures
- [x] Write unit tests for:
  - [x] `tests/test_agent.py` - singleton, thread safety (7 tests)
  - [x] `tests/test_idv2.py` - DB push/pull/sync (6 tests)
  - [x] `tests/test_hea.py` - L1/L2/L3 context filtering (10 tests)
- [x] Add pyproject.toml with pytest configuration

**Result:** 23 tests passing (`pytest tests/ -v`)

---

### ⏳ 8. Adversarial-Coherence Benchmark
**Status:** Harness complete, baseline pending  
**Lead Profiles:** Cognitive Psychologist + AI/ML Engineer  
**Supporting:** Computational Neuroscientist  

#### Phase 1: Define Evaluation Criteria (Cognitive Psychologist) ✅
**Tasks:**
- [x] Map psychological constructs to measurable metrics:
  - **Personality Consistency:** Does Nola maintain coherent traits across 50+ turns?
  - **Context Appropriateness:** L1/L2/L3 selection matches task demands?
  - **Boundary Respect:** Refuses inappropriate requests while staying in character?
  - **Emotional Intelligence:** Appropriate tone/empathy responses?
- [x] Define scoring rubric (1-5 scale per dimension)
- [x] Document expected behaviors for each context level
- [x] Create edge-case scenarios (ambiguous stimuli, conflicting cues)

**Deliverable:** ✅ `docs/evaluation_framework.md`

#### Phase 2: Build Benchmark Harness (AI/ML Engineer) ✅
**Tasks:**
- [x] Create `eval/` directory structure
- [x] Implement `duel.py` skeleton with CLI
- [x] Add judge model integration (OpenAI, Anthropic, Mock)
- [x] Multi-turn conversation loop with opponent classes
- [x] Transcript export paths configured
- [ ] Full conversation loop execution (post-launch)

**Deliverable:** ✅ Working `eval/duel.py`

#### Phase 3: Neural Grounding (Computational Neuroscientist) ⏳
**Tasks:**
- [x] Map evaluation dimensions to neural systems (in metrics.py)
- [ ] Add activation logging to track context level selection
- [ ] Generate visualization of turn-by-turn transitions
- [ ] Write `docs/interpretability.md`

**Deliverable:** ⏳ `docs/interpretability.md` (post-launch)

#### Phase 4: Baseline Transcript (All Three Profiles) ⏳
**Tasks:**
- [ ] Run 100-turn conversation with escalating complexity
- [ ] Annotate with context levels and neural activations
- [ ] Export to `eval/baselines/nola_baseline_100turn.md`

**Deliverable:** ⏳ Annotated 100-turn baseline transcript (post-launch)

---

## Success Criteria

### Minimal Viable Demo (Must Have)
- [x] One-liner setup works on fresh Ubuntu 22.04 / macOS
- [x] CI shows green badge
- [x] Deps pinned and reproducible
- [x] Test suite runs with `pytest` (23 passing)
- [ ] 50-turn adversarial benchmark completes (harness ready)
- [ ] Baseline transcript demonstrates personality coherence (post-launch)

### Strong Demo (Should Have)
- [ ] 100-turn transcript with psychological + neural annotations
- [ ] Judge model shows Nola > baseline on coherence metrics
- [ ] `docs/interpretability.md` explains system clearly
- [ ] README.zh for international reach

---

## Next Actions (Prioritized)
1. ~~**Backend Dev:** Run `pytest tests/` to validate test structure~~ ✅ DONE
2. **Post-Launch:** Run full `eval/duel.py` conversation loop
3. **Post-Launch:** Generate baseline transcript
4. **Nice-to-have:** README.zh Chinese documentation
5. **Nice-to-have:** Interpretability visualizations
