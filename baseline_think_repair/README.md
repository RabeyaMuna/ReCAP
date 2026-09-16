# ThinkRepair Baseline for CI-Based Repair

Adaptation of **ThinkRepair: Self-Directed Automated Program Repair** (ISSTA 2024) for CI failure repair.

## Paper Reference

**Title**: "ThinkRepair: Self-Directed Automated Program Repair"  
**Authors**: Xin Yin, Chao Ni, Shaohua Wang, Zhenhao Li, Limin Zeng, Xiaohu Yang  
**Venue**: ISSTA 2024  
**Paper**: https://arxiv.org/abs/2407.20898  
**Code**: https://github.com/vinci-grape/ThinkRepair

## Original ThinkRepair Approach

ThinkRepair has two main phases:

### 1. Collection Phase
- Automatically collects **Chains of Thought (CoT)** from buggy→fixed examples
- Builds a knowledge pool of reasoning processes
- Filters by test validation

### 2. Fixing Phase
- **Few-shot selection**: Picks similar examples from knowledge pool
- **CoT prompting**: "Let's think step by step"
- **Interaction feedback**: Iterative refinement with test results

## Adaptation for CI Context

### Collection Phase (Offline)
```
Input: Historical CI failures + fixes from training set
Process:
  1. For each CI failure:
     - Prompt LLM with CI logs + changed files
     - Generate CoT reasoning + patch
     - Validate patch (would it fix CI?)
  2. Store successful (logs, reasoning, patch) triples
Output: Knowledge pool of CI repair examples with reasoning
```

### Fixing Phase (Online)
```
Input: New CI failure
Process:
  1. Few-shot Selection:
     - Embed CI logs semantically
     - Find K most similar examples from knowledge pool
  2. Prompt Construction:
     - Role: "You are an automated CI repair tool"
     - Examples: K selected (logs→reasoning→patch)
     - Target: Current CI failure
     - CoT trigger: "Let's think step by step"
  3. Iterative Feedback (max 5 rounds):
     - Generate reasoning + patch
     - If validation fails: add error message + retry
Output: Final patch with reasoning trace
```

## Key Components

| Component | Original ThinkRepair | Our CI Adaptation |
|-----------|---------------------|-------------------|
| **Buggy Input** | Single function | CI logs + changed files |
| **Knowledge Pool** | Defects4J functions | CI failure examples |
| **Few-shot Similarity** | Code embeddings (UniXcoder) | Log + code embeddings |
| **CoT Trigger** | "Let's think step by step" | Same |
| **Feedback** | Test failure messages | CI validation output |
| **Max Interactions** | 5 | 5 |

## Implementation Structure

```
baseline_think_repair/
├── README.md (this file)
├── wrapper.py          # Main interface matching ExpeRepair API
├── prompts.py          # Prompt templates with CoT
├── collection.py       # Knowledge pool building (offline)
├── selection.py        # Few-shot example selection
├── repair.py           # Iterative repair with feedback
├── knowledge_pool.json # Pre-built CoT examples
└── run_baseline.py     # Evaluation script
```

## Usage

### Option 1: With Pre-built Knowledge Pool (Recommended)
```python
from baseline_think_repair.wrapper import generate_patch_thinkrepair

result = generate_patch_thinkrepair(
    issue_description="CI logs...",
    changed_files=["file1.py", "file2.py"],
    repo_path="/path/to/repo",
    model="deepseek-v4-flash",
    max_interactions=5,
    k_shot=2  # Number of examples
)
```

### Option 2: Build Your Own Knowledge Pool
```bash
# Step 1: Build knowledge pool from training data
python -m baseline_think_repair.collection \
    --train_data data/train_set.jsonl \
    --output baseline_think_repair/knowledge_pool.json \
    --model deepseek-v4-flash

# Step 2: Run repair
python -m baseline_think_repair.run_baseline \
    --eval_data data/eval_set.jsonl \
    --output results/thinkrepair_baseline.json
```

## Differences from Original

1. **No Function-Level Focus**: We work with full CI context (logs, multiple files)
2. **CI-Specific Reasoning**: CoT adapted for CI error analysis (log parsing, workflow understanding)
3. **Simplified Collection**: Use forward training examples instead of collecting from scratch
4. **Semantic Similarity**: Combine log and code embeddings for example selection

## Expected Performance

- **Better than**: Simple one-shot prompting (ExpeRepair baseline)
- **Reasoning**: Explicit CoT helps LLM understand CI failure patterns
- **Few-shot Learning**: Relevant examples guide repair strategy
- **Iterative Refinement**: Feedback loop improves patch quality
