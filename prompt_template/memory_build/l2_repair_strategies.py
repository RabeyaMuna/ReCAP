"""
L2 Repair Strategies Prompts.

Prompts for generating repair strategies from L1 problems.
"""

from typing import Dict, List
import json


def build_l2_prompt(
    l1_memory: Dict,
    automated_tools: List[Dict],
    sampling_info: Dict = None,
) -> str:
    """
    Build L2 prompt to generate repair strategies from L1 problems.

    LEAN VERSION: Trust the LLM to analyze problems and match to automation tools.
    No hardcoded templates, no repetitive examples, fully dynamic.

    Args:
        l1_memory: L1 memory with problems (may be sampled)
        automated_tools: List of available automation tools (self-documenting)
        sampling_info: Optional sampling metadata (if L1 was sampled)

    Returns:
        Prompt string for LLM
    """
    issue_id = l1_memory.get("issue_id")
    repo = l1_memory.get("repo")
    workflow = l1_memory.get("workflow")
    problems = l1_memory.get("problems", [])
    changed_files = l1_memory.get("changed_files", [])

    # Sampling note
    sampling_note = ""
    if sampling_info and sampling_info.get("was_sampled"):
        sampling_note = f"""
NOTE: L1 sampled (~{sampling_info.get("total_size", 0):,} tokens). Problems with >10 files show first 5 + files_metadata with total count.
"""

    prompt = f"""Analyze CI failure and generate repair strategies (L2).

ISSUE: {issue_id} | REPO: {repo} | WORKFLOW: {workflow}
{sampling_note}

=== CHANGED FILES ===
{json.dumps(changed_files, indent=2)}

=== L1 PROBLEMS ({len(problems)} total) ===
{json.dumps(problems, indent=2)}

L1 Problem Schema:
- problem_id, verification_cmd, failure_type, problem, root_cause, fix_strategy
- files: affected paths (or files_metadata if >10 files: total_count, pattern, note)
- enabled: [problem_ids] revealed after fixing this (sequential dependencies)

=== AUTOMATION TOOLS ===
{json.dumps(automated_tools, indent=2)}

Each tool specifies:
- purpose: what it fixes
- fixes: list of problem types it addresses
- file_pattern: what files it works on
- install_command: how to install
- fix_command: how to run ({{{{file_or_dir}}}} = placeholder for target path)

=== YOUR TASK ===

1. **Analyze Problems**: For each L1 problem:
   - Check if problem.failure_type matches any tool.fixes array
   - Check if problem.files match any tool.file_pattern
   - Count files: use files_metadata.total_count if exists, else len(files)
   - Decision: IF (match exists AND files ≥ 10) → automation; ELSE → manual

2. **Group Problems**: Create strategies by grouping:
   - Problems with same root_cause → ONE strategy
   - Problems where A.enabled contains [B, C] → ONE strategy (A enables B and C)
   - Independent problems → SEPARATE strategies

3. **Generate Strategies**: For each strategy, build key_actions:
   - IF automation: Use tool.install_command, then tool.fix_command
     * Replace {{{{file_or_dir}}}} with: common parent directory if multiple files share one, else individual file
     * EFFICIENT: 20 files in src/utils/ → run on src/utils/ (NOT file-by-file)
   - IF manual: Use steps from L1.fix_strategy
   - ALWAYS end with: L1.verification_cmd to verify

4. **Output**: Return JSON with:
   - failure_identify: ["failure_type (validator) - N problems"] (use files_metadata.total_count when present)
   - repair_strategies: Array of strategy objects (see schema below)

=== ANALYSIS GUIDELINES ===

**Grouping Logic**:
- problem.enabled = [X, Y] means fixing this problem reveals problems X and Y
- Group enabled problems in ONE strategy, explain causal chain
- Share root_cause → group together; different causes → separate

**Automation Matching**:
- Match problem.failure_type to tool.fixes array (each tool lists what it fixes)
- Match problem.files extensions to tool.file_pattern
- Use tool.install_command and tool.fix_command from matched tool

**Signals** (observable error patterns):
- Extract actual error messages from L1.problem field
- Include file paths/patterns, command failures, tool versions
- Be specific: "mypy: error [arg-type] at helpers.py:42" not "type error"

**Key Actions**:
- Automation: tool.install_command → tool.fix_command with target → L1.verification_cmd
  * If multiple files in SAME directory: target = common parent directory (more efficient)
  * If files scattered across directories: target = repository root or common ancestor
  * Example: 20 files in src/utils/ → run tool on src/utils/ NOT file-by-file
- Manual: steps from L1.fix_strategy → L1.verification_cmd
- Config changes: specify exact file, section, key=value

CRITICAL OUTPUT FORMAT:

Return ONLY valid JSON with this structure:

IMPORTANT JSON FORMATTING:
- Your FIRST character MUST be {{ - NO text or backticks before
- Your LAST character MUST be }} - NO text or backticks after
- Do NOT wrap in backticks: NO ``` or ```json or ` - NONE AT ALL
- Do NOT add markdown, explanations, or any text outside the JSON
- The response will be passed DIRECTLY to json.loads() - it MUST parse perfectly

{{
  "issue_id": "{issue_id}",
  "repo": "{repo}",
  "workflow": "{workflow}",
  "total_problems": {len(problems)},
  "failure_identify": [
    "failure_type (validator) - N problems/files"
  ],
  "repair_strategies": [
    {{
      "step": 1,
      "failure_type": "<extract from L1 problem.failure_type>",
      "validation_cmd": "<extract from L1 problem.verification_cmd>",
      "applies_to_failures": ["<from failure_identify above>"],

      // USE PATTERN: "<failure_type> in <location> (<specific_error>)" for each problem
      "causal_chain": "<Describe relationship between problems using the pattern. Extract location from L1 files/files_metadata, error details from L1 problem field>",

      "summary": "<One-line description - what files/areas affected>",
      "intent": "<What this strategy achieves - be specific to YOUR issue>",

      // Reference problems using pattern, extract details from YOUR L1 data
      "reasoning": "<Why grouping these problems - use actual file names and error details from L1>",
      "rationale": "<Why this approach works - manual vs automation based on YOUR L1 error types>",

      "when_to_apply": "<Specific conditions from YOUR L1 - validators, error patterns, file patterns>",

      // OBSERVABLE PATTERNS that detect this failure (extract from L1 but format as actual CI log patterns)
      // CRITICAL: Include config/version info when relevant!
      "signals": [
        "<tool>: <actual_error_message_as_it_appears> at <file>:<line>",
        "<N> files matching <pattern> affected",
        "Config: <specific_version_constraint_or_setting> in <config_file>",
        "Command '<actual_command>' exits with code <exit_code>"
      ],

      // EXAMPLES of properly formatted signals (NOTICE CONFIG INFO):
      // Type error: "mypy: error: Incompatible type [arg-type] at helpers.py:42"
      // Format error: "67 files matching docs/source/**/*.rst with heading adornment errors"
      // Test error: "pytest: AssertionError: assert 200 == 401 in test_auth.py::test_login"
      // Import error: "ImportError: No module named 'numpy.typing' in utils/config.py"
      // Dependency: "poetry: Dependency conflict - typer requires click<8.2.0 but pyproject.toml has no constraint"
      // Version: "numpy 2.0 removed DTypeLike - need to update type annotations"
      // Command: "Command 'python -m mypy .' exits with code 1"

      "key_actions": [
        // USE COMPREHENSIVE TOOLS (not narrow single-purpose tools):
        // PREFER: ruff (fixes imports+linting+formatting), pre-commit (runs all)
        // AVOID: isort only, black only, flake8 only (too narrow)
        //
        // PHASE 1: INITIAL FIX
        // Step order: (1) Config changes (2) Code changes (3) Initial verification
        //
        // PHASE 2: COMPREHENSIVE FORMATTING/LINTING FIX (MANDATORY)
        // After applying the initial fix, ALWAYS run comprehensive tools:
        //
        // FOR PYTHON PROJECTS (use comprehensive tools):
        //   Step 1: Run comprehensive formatter/linter:
        //     BEST: ruff check --fix . && ruff format .
        //     (This fixes: imports, linting, formatting ALL AT ONCE)
        //
        //   Step 2: Verify all checks pass:
        //     ruff check . (exit 0)
        //     black --check . (exit 0, if project uses black)
        //     isort --check . (exit 0, if project uses isort)
        //
        //   Step 3: If project has pre-commit:
        //     pre-commit run --all-files
        //     (Runs ALL configured formatters/linters)
        //
        // WHY COMPREHENSIVE TOOLS:
        //   - Problem: "isort failed" but workflow also checks black, flake8
        //   - Narrow fix: isort file.py → only fixes imports
        //   - Broad fix: ruff check --fix . → fixes imports + linting + more
        //   - Result: All checks pass, not just the L1 problem
        //
        // PHASE 3: POST-FIX VERIFICATION & ITERATION
        // After comprehensive fix, run validation_cmd and CHECK the failure type:
        //
        // IF STATIC ANALYSIS STILL FAILS:
        //   Step 1: Check what else failed (might be different error now)
        //   Step 2: Apply targeted fix
        //   Step 3: Re-run comprehensive tools again
        //   Step 4: Iterate: fix → comprehensive check → verify
        //
        // IF TEST FAILURE:
        //   Step 1: Run tests with verbose output: pytest -v or pytest -vv
        //   Step 2: Analyze specific test failure:
        //     - ImportError → Fix import paths, check __init__.py files
        //     - AttributeError/KeyError in tests → Fix test fixtures/mocks
        //     - AssertionError → Fix test expectations or actual code
        //     - Async RuntimeWarning → Add @pytest.mark.asyncio, use AsyncMock
        //   Step 3: Apply targeted fix for that specific test error
        //   Step 4: Re-run tests
        //   Step 5: Iterate: fix test → verify → fix next test until all pass
        //
        // IF DEPENDENCY/IMPORT FAILURE:
        //   Step 1: Check requirements.txt, pyproject.toml for version constraints
        //   Step 2: Resolve version conflicts (use compatible version ranges)
        //   Step 3: Check for missing __init__.py in new directories
        //   Step 4: Re-run validation_cmd
        //
        // IF CONFIG FAILURE:
        //   Step 1: Validate config file syntax (yamllint, toml-sort --check)
        //   Step 2: Check for deprecated config options
        //   Step 3: Fix config issues
        //   Step 4: Re-run validation_cmd
        //
        // PHASE 3: FINAL VERIFICATION
        // - Run validation_cmd one final time
        // - Ensure exit code is 0
        // - Include ALL modified files in final patch (code + auto-fixed formatting)
        //
        // ITERATION LIMIT: Max 3 iterations per failure type
        // If still failing after 3 iterations, document the remaining issue
        //
        // Be specific: exact file paths, line numbers when available, config sections, version constraints
      ],

      "pitfalls": [
        "<Common mistakes specific to THIS error type>",
        "<Tool-specific warnings if using automation>"
      ],

      // MANDATORY POST-FIX VERIFICATION (applies to ALL strategies)
      "post_fix_verification": [
        "AFTER applying ANY fix (code, config, docs, etc.), ALWAYS verify formatting/linting:",
        "",
        "STEP 1: Run comprehensive formatting/linting check:",
        "  Option A (if ruff available): ruff check . && ruff format --check .",
        "  Option B (if pre-commit): pre-commit run --all-files"
        "",
        "STEP 2: If formatting/linting issues found:",
        "  Auto-fix immediately:",
        "    - ruff check --fix . && ruff format .",
        "    - OR: pre-commit run --all-files (then commit changes)"
        "",
        "STEP 3: Re-run check to confirm all issues fixed:"
        
        "STEP 4: Include ALL auto-fixed files in final patch:",
        "  Original fix + formatting fixes = complete patch",
        "",
        "WHY THIS IS CRITICAL:",
        "  - Even if you fixed the problem, formatting/linting might still fail",
        "  - CI workflows often check formatting AFTER running your fix",
        "  - Better to catch and fix formatting NOW than fail CI later",
        "",
        "APPLIES TO:",
        "  - Code fixes (Python, JavaScript, etc.)",
        "  - Config changes (might affect formatting rules)",
        "  - Documentation changes (Python docstrings need formatting)",
        "  - Test changes (test files must pass formatting too)"
      ],

      "critical_warnings": [
        "After ANY file edit: MANDATORY post-fix formatting/linting verification",
        "Use comprehensive tools (ruff, pre-commit) not narrow tools (isort only)",
        "Auto-fix formatting issues immediately, don't leave for CI to catch",
        "Include ALL auto-fixed files in the final patch"
      ],

      "example_phrasing": "<Natural language using actual file names and error types from YOUR L1>"
    }}
  ]
}}

REMEMBER:
- Use files_metadata.total_count when available (not len(files))
- Choose automation tool only if appropriate (check file pattern + error type)
- Group problems by causal relationship, not just validation
- Include sequential dependencies from "enabled" field
- Make signals and key_actions SPECIFIC and EXECUTABLE

CRITICAL REQUIREMENTS:
- ALWAYS include "failure_type" and "validation_cmd" fields in each strategy
- SIGNALS must include config/version info when relevant (e.g., "click >= 8.2.0 constraint missing")
- KEY_ACTIONS must follow pattern:
  * CONFIG changes BEFORE code changes (if both needed)
  * For AUTOMATED fixes: exact install + run command + "no manual check unless this fails"
  * For MANUAL fixes: exact file, line number (if available), specific change
  * Include specific config values (versions, sections, keys)
- For AUTOMATION tools: Use exact commands from AUTOMATED_TOOLS list (install_command, fix_command)
- Separate config modification from code modification in steps
"""

    return prompt
