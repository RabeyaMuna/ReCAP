# ThinkRepair Baseline (Plan Generation)

**Simplified implementation of ThinkRepair for CI repair plan generation.**

## Paper Reference

**Title**: "ThinkRepair: Self-Directed Automated Program Repair"  
**Authors**: Xin Yin, Chao Ni, Shaohua Wang, Zhenhao Li, Limin Zeng, Xiaohu Yang  
**Venue**: ISSTA 2024  
**Paper**: https://arxiv.org/abs/2407.20898  
**Code**: https://github.com/vinci-grape/ThinkRepair

## Overview

ThinkRepair is used as a **plan generator** using knowledge pool, NOT as a patch generator.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ThinkRepair Baseline                      │
└─────────────────────────────────────────────────────────────┘

Phase 1: Collection (Offline)
──────────────────────────────
Memory Set (150 issues)
         ↓
   CI Analysis
         ↓
   LLM Reasoning
         ↓
Knowledge Pool
{id, analysis, reasoning, patch, changed_files}


Phase 2: Plan Generation (Online)
──────────────────────────────────
Eval Issue → CI Analysis
                ↓
    Select K=2 similar examples
                ↓
    Few-shot prompt with examples
                ↓
         LLM generates PLAN
                ↓
         ┌──────────┐
         │   PLAN   │  ← ThinkRepair output
         │ (Reasoning │
         │  + Steps)  │
         └──────────┘
                ↓
      Pass to MiniSWEAgent
                ↓
      Generate actual patch
```

## Why Plan Generation?

**Original ThinkRepair**: Generates patches directly
- Works for Defects4J (single functions, simple bugs)
- Struggles with CI failures (multiple files, formatting issues)
- Hard to generate valid unified diffs

**Our Approach**: ThinkRepair generates plans → MiniSWEAgent generates patches
- ThinkRepair: Reasoning and strategy (its strength)
- MiniSWEAgent: Patch generation (its strength)
- Better division of labor

## Files

### Core Files
- `collection.py` - Build knowledge pool from memory_set.jsonl
- `repair_ci.py` - ThinkRepairCI class (plan generation)
- `prompts.py` - Prompt templates
- `wrapper.py` - Entry point (generate_plan_thinkrepair)
- `run_baseline.py` - Generate plans for eval_set.jsonl

### Data Files
- `knowledge_pool_minimax.json` - 150 examples with CoT reasoning
- `ci_analysis_cache.py` - Cache for CI analysis

### Test Files
- `test_thinkrepair_one.py` - Test plan generation on one issue

## Usage

### Two-Stage Approach (Recommended)

Generate all plans first, then run MiniSWEAgent to generate patches.

#### Stage 1: Generate ThinkRepair Plans

```bash
python3 baseline_think_repair/run_stage1_plans.py \
    --eval_data data/eval_set.jsonl \
    --model minimax-m2_5 \
    --k_shot 2 \
    --knowledge_pool baseline_think_repair/knowledge_pool_minimax.json \
    --output results/think_repair/
```

**Outputs**:
- `results/think_repair/plans.json` - Plans for inspection
- `results/think_repair/instances_with_plans.jsonl` - Ready for MiniSWEAgent

**What it does**:
- Loads log_details for each issue
- Selects K=2 similar examples from knowledge pool
- Generates plan with ThinkRepair (using Chain-of-Thought)
- Saves both files

#### Stage 2: Generate Patches with MiniSWEAgent

```bash
python3 -m minisweagent.run.benchmarks.cibench \
    --dataset results/think_repair/instances_with_plans.jsonl \
    --output results/think_repair/ \
    -m openrouter/minimax/minimax-m2.5 \
    --no-memory-enabled
```

**Output**: `results/think_repair/preds.json`

**What it does**:
- Reads plans from instances_with_plans.jsonl
- Passes each plan to MiniSWEAgent as problem statement
- Generates patches
- Saves to preds.json

### Setup: Build Knowledge Pool (One-time)

Before first run, build the knowledge pool:

```bash
python baseline_think_repair/collection.py \
    --train_data data/memory_set.jsonl \
    --output baseline_think_repair/knowledge_pool_minimax.json \
    --model minimax-m2_5
```

### Test on One Issue

```bash
python test_thinkrepair_one.py
```

## Output Format

All results saved to: `results/think_repair/`

```
results/think_repair/
├── plans.json                      # ThinkRepair plans (if using 2-stage)
├── instances_with_plans.jsonl      # Formatted for cibench (if using 2-stage)
├── preds.json                      # Generated patches ⭐
├── cibench.log                     # Execution logs
└── <sha>/                          # Per-instance directories
    ├── testbed/                    # Cloned repos
    └── *.traj.json                 # Agent trajectories
```

### Plans JSON (Stage 1 or cached)

```json
{
  "44": {
    "id": "44",
    "sha_fail": "c99ead95...",
    "repo": "wandb/wandb",
    "plan": "## Root Cause\nBlack formatting...\n\n## Steps\n1. Open image.py\n2. Change quotes...",
    "reasoning": "...",
    "cost": 0.0012,
    "examples_used": 2,
    "model": "minimax-m2_5"
  }
}
```

### Patches JSON (Final Output)

```json
{
  "44": {
    "id": "44",
    "sha_fail": "c99ead95...",
    "diff": "diff --git a/wandb/sdk/data_types/image.py b/wandb/sdk/data_types/image.py\n--- a/wandb/sdk/data_types/image.py\n+++ b/wandb/sdk/data_types/image.py\n@@ -277,7 +277,7 @@\n-\"png\"\n+'png'"
  }
}
```

## Key Differences from Original ThinkRepair

### Original ThinkRepair
- Dataset: Defects4J (single functions)
- Task: Issue-based repair (logic bugs)
- Output: Unified diff patch
- Validation: Test suite

### Our ThinkRepair (Plan Generation)
- Dataset: CI failures (multiple files)
- Task: Repo-based repair (formatting, imports)
- Output: Repair plan (reasoning + steps)
- Validation: Plan passed to MiniSWEAgent → patch generated → evaluated

## Knowledge Pool

Contains 150 examples from memory_set.jsonl, each with:
- `id`: Issue ID
- `analysis`: CI failure analysis
- `reasoning`: Step-by-step CoT reasoning
- `patch`: Ground truth patch
- `changed_files`: Files modified
- `repo`: Repository name
- `sha_fail`: Failing commit SHA

### Few-Shot Learning

For each eval issue:
1. Select K=2 most similar examples from knowledge pool (currently random)
2. Build prompt: Example 1 → Example 2 → Current issue
3. LLM learns pattern from examples
4. LLM generates plan for current issue

## Integration with MiniSWEAgent

ThinkRepair plans are passed to MiniSWEAgent as problem statements:

```python
# ThinkRepair plan
plan = """
Root Cause: Black formatting failure in image.py
Strategy: Accept formatter's changes for string quotes
Steps:
1. Open wandb/sdk/data_types/image.py
2. Change line 277: "png" → 'png'
3. Change line 285: "jpeg" → 'jpeg'
4. Run black to verify
"""

# Pass to MiniSWEAgent
minisweagent.solve(problem_statement=plan, ...)
```

## Comparison to L1+L2+L3

Both approaches use LLM reasoning + execution:

**ThinkRepair + MiniSWEAgent**:
- ThinkRepair: Knowledge pool → Plan generation
- MiniSWEAgent: Plan → Patch generation

**L1+L2+L3**:
- L1: Specific examples
- L2: General strategies
- L3: Abstract patterns
- Hierarchical memory → Patch generation

## Check Results

```bash
# How many patches generated?
cat results/think_repair/preds.json | jq 'length'

# How many successful patches (non-empty)?
cat results/think_repair/preds.json | jq '[.[] | select(.diff != "")] | length'

# View one patch
cat results/think_repair/preds.json | jq '.["44"]'

# If using 2-stage, check plans
cat results/think_repair/plans.json | jq 'length'
```

## Resume After Interruption

If the run is interrupted, just run the same command again:

```bash
python -m minisweagent.run.benchmarks.cibench \
    --dataset data/eval_set.jsonl \
    --output results/think_repair/ \
    -m openrouter/minimax/minimax-m2.5 \
    --no-memory-enabled \
    --slice 0:150
```

It automatically **skips completed instances** from `preds.json` and resumes! ✅

## Cost

Approximate costs (using minimax-m2.5):
- Collection phase: ~$0.15 (one-time, 150 issues)
- Plan generation: ~$0.001 per issue
- Patch generation: ~$0.XX per issue (depends on agent steps)
- **Total for 408 eval issues**: ~$XX

## Comparison to Other Baselines

| Baseline | Plans From | Patches From | Output |
|----------|-----------|--------------|--------|
| **Normal Baseline** | Raw CI logs | MiniSWEAgent | `results/baseline/` |
| **ThinkRepair** | Knowledge pool + CoT | MiniSWEAgent | `results/think_repair/` |
| **L1+L2+L3** | Hierarchical memory | MiniSWEAgent | `results/l1_l2_l3/` |

## TODO

- [ ] Implement semantic similarity for example selection (currently random)
- [x] Integrate with MiniSWEAgent for end-to-end evaluation
- [ ] Compare plan quality vs L1+L2+L3
- [ ] Measure patch success rate after MiniSWEAgent execution
