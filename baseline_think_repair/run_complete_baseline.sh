#!/bin/bash
# Complete ThinkRepair Baseline Pipeline
# This script runs both phases: collection and evaluation

set -e  # Exit on error

echo "========================================"
echo "ThinkRepair Baseline - Complete Pipeline"
echo "========================================"
echo ""

# Configuration
MODEL=${MODEL:-"minimax-m2_5"}  # Use minimax-m2_5 to match L1+L2+L3 experiments
K_SHOT=${K_SHOT:-2}
MAX_EXAMPLES=${MAX_EXAMPLES:-150}  # Use all 150 memory issues by default
MEMORY_DATA="data/memory_set.jsonl"
EVAL_DATA="data/eval_set.jsonl"
KNOWLEDGE_POOL="baseline_think_repair/knowledge_pool_${MODEL}.json"
OUTPUT_DIR="results/think_repair/baseline_${MODEL}_k${K_SHOT}"

echo "Configuration:"
echo "  Model: $MODEL"
echo "  K-shot: $K_SHOT"
echo "  Max examples for knowledge pool: $MAX_EXAMPLES"
echo "  Memory data: $MEMORY_DATA"
echo "  Eval data: $EVAL_DATA"
echo "  Output: $OUTPUT_DIR"
echo ""

# Phase 1: Build Knowledge Pool (if not exists or --rebuild flag)
if [ ! -f "$KNOWLEDGE_POOL" ] || [ "$1" == "--rebuild" ]; then
    echo "========================================"
    echo "PHASE 1: Building Knowledge Pool"
    echo "========================================"
    echo "Using $MAX_EXAMPLES memory issues to build knowledge pool..."
    echo ""

    python3 baseline_think_repair/collection.py \
        --train_data "$MEMORY_DATA" \
        --output "$KNOWLEDGE_POOL" \
        --model "$MODEL" \
        --max_examples $MAX_EXAMPLES

    echo ""
    echo "✓ Knowledge pool built successfully"
else
    echo "✓ Knowledge pool already exists at: $KNOWLEDGE_POOL"
    echo "  (Use --rebuild to regenerate)"
fi

echo ""
echo "========================================"
echo "PHASE 2: Running Baseline on Eval Set"
echo "========================================"
echo "Testing on 408 eval issues..."
echo ""

# Phase 2: Run Baseline on Eval Set
python3 baseline_think_repair/run_baseline.py \
    --eval_data "$EVAL_DATA" \
    --model "$MODEL" \
    --k_shot $K_SHOT \
    --knowledge_pool "$KNOWLEDGE_POOL" \
    --max_interactions 5

echo ""
echo "========================================"
echo "✓ ThinkRepair Baseline Complete!"
echo "========================================"
echo "Results saved to: $OUTPUT_DIR/preds.json"
echo ""
echo "To compare with your L1+L2+L3 results:"
echo "  python scripts/compare_baselines.py \\"
echo "    --memory_results results/codex/forward/l1_l2_l3_*/predictions.json \\"
echo "    --thinkrepair_results $OUTPUT_DIR/preds.json"
echo ""
