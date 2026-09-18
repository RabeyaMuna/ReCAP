# ThinkRepair Baseline: Quick Start

## What Is This?

ThinkRepair generates **repair plans** using a knowledge pool → MiniSWEAgent executes plans to generate **patches**.

## Visual Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  CI Issue   │ ──→ │ ThinkRepair  │ ──→ │ MiniSWEAgent│ ──→ PATCH
│ (eval_set)  │     │ (Plan Gen)   │     │ (Execution) │
└─────────────┘     └──────────────┘     └─────────────┘
                           ↑
                           │
                    Knowledge Pool
                    (150 examples)
```

## Run It

```bash
# 1. Build knowledge pool (one-time, ~2 minutes)
python baseline_think_repair/collection.py \
    --train_data data/memory_set.jsonl \
    --output baseline_think_repair/knowledge_pool_minimax.json

# 2. Test on one issue (~30 seconds)
python test_thinkrepair_one.py

# 3. Run on 10 issues (~10 minutes)
python baseline_think_repair/run_thinkrepair_miniswe.py \
    --eval_data data/eval_set.jsonl \
    --limit 10

# 4. Check results
cat results/thinkrepair_full/plans.json | jq 'length'
cat results/thinkrepair_full/preds.json | jq 'length'
```

## Files You Need

- ✅ `data/memory_set.jsonl` - Training data (150 issues)
- ✅ `data/eval_set.jsonl` - Evaluation data (408 issues)
- ✅ `baseline_think_repair/collection.py` - Build knowledge pool
- ✅ `baseline_think_repair/run_thinkrepair_miniswe.py` - Full pipeline
- ✅ `test_thinkrepair_one.py` - Test script

## What Gets Generated

```
results/thinkrepair_full/
├── plans.json     ← ThinkRepair plans (reasoning + steps)
└── preds.json     ← MiniSWEAgent patches (unified diffs)
```

## Key Points

- **ThinkRepair**: Generates PLANS, not patches
- **Knowledge Pool**: 150 examples with reasoning
- **Few-Shot**: Uses K=2 similar examples
- **MiniSWEAgent**: Executes plans to generate patches
- **Cost**: ~$0.001 per plan, $0.XX per patch

## Documentation

- `README.md` - Overview and usage
- `INTEGRATION_FLOW.md` - Detailed flow with examples
- `THINKREPAIR_FINAL_FLOW.md` - Complete architecture
- `QUICK_START.md` - This file

Done! 🚀
