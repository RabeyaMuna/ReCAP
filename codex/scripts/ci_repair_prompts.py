"""Cache-friendly prompt layout for the CI repair agents.

OpenAI prompt caching matches exact prompt prefixes.  Keep instructions in the
stable prefix and append repository/issue/problem data after the explicit
boundary.  The dynamic suffix is never included in the template fingerprint.
"""

from __future__ import annotations

import hashlib
from typing import Any


DYNAMIC_CONTEXT_BOUNDARY = "\n<!-- ci-repair-dynamic-context:v1 -->\n"

_COMMON_REPAIR_INSTRUCTIONS = r"""# CI Repair Task

You are fixing one CI failure problem in the current repository. Perform the
full analysis needed for a correct repair; do not omit relevant configuration,
dependency, package, environment, or source-code evidence from the dynamic
context supplied below.

## Instructions

**Your Task:**
- Analyze the supplied CI failure context
- Identify the root cause from error signals and relevant files
- Determine the minimal fix needed
- Implement and validate the fix

**Evidence and repair quality:**
- Treat every issue as dynamic; derive the repair from the current repository,
  CI evidence, environment constraints, and supplied problem relationships
- Preserve and inspect all relevant configuration changes instead of reducing
  the problem to source-code edits alone
- When a package, dependency declaration, lockfile, resolver option, runtime,
  build tool, or CI image changed, analyze why that change may be required by
  the project's supported versions and environment
- Consider package deprecation, removed APIs, incompatible version ranges,
  platform/runtime support, resolver behavior, build isolation, and the next
  validation step when the available evidence supports those possibilities
- Distinguish observed evidence from a plausible inference; confirm an
  inference in repository files or tool output before changing the project
- Keep related configuration, dependency, and source changes together when
  they form one repair, but do not combine unrelated problems
- Do not discard a configuration or package change merely because the first
  visible CI failure can be fixed elsewhere
- After the first failure is repaired, consider whether the same environment
  constraints expose a directly dependent installation, build, test, lint, or
  runtime failure; validate only what is relevant to this problem
- Prefer the smallest complete repair over a partial edit that hides the first
  error while leaving its supported cause unresolved
- Do not invent package failures or configuration requirements that are not
  supported by the repository, CI logs, dependency metadata, or tool output

**STEP 0: Validate Problem Exists**

CRITICAL: Validation requirements differ based on problem type.

**PRIMARY PROBLEMS (from CI logs - problem_type: "ci_failure"):**
- Directly observed in CI failure logs with error messages
- NO VALIDATION REQUIRED - trust the CI evidence
- PROCEED DIRECTLY TO FIX - skip validation steps below

**HIDDEN PROBLEMS (inferred/consecutive - problem_type: "consecutive", "dependency", "common"):**
- Inferred by agent or derived from patterns, not in CI logs
- VALIDATION REQUIRED - must confirm existence before fixing
- Follow validation process below

---

**Validation Process for HIDDEN Problems Only:**

1. **Verify file paths** - CI logs sometimes provide incomplete/partial paths:
   - If a file path doesn't exist, search for it: `find . -type f -name "$(basename <file>)"`
   - Use the correct full path for all subsequent commands

2. **Attempt local verification** - Try to confirm problem exists:
   ```bash
   echo "HIDDEN PROBLEM - Verifying locally..."
   if <verification_cmd> 2>&1 | tee /tmp/verify_output.log; then
     VERIFY_EXIT_CODE=0
   else
     VERIFY_EXIT_CODE=$?
   fi
   ```

3. **Check for failure signals:**
   ```bash
   SIGNALS_FOUND=false

   for signal in <failure_signal_1> <failure_signal_2> <failure_signal_3>; do
     if grep -qF "$signal" /tmp/verify_output.log 2>/dev/null; then
       echo "CONFIRMED: Found signal in verification"
       SIGNALS_FOUND=true
       break
     fi
   done
   ```

4. **Decide: Fix or Skip**

   **If verification confirms problem (signals found):**
   ```bash
   if [ "$SIGNALS_FOUND" = "true" ]; then
     echo "PROCEED: Hidden problem confirmed by verification"
     # Continue to fix
   ```

   **If verification ran but NO problem found:**
   ```bash
   elif [ -f /tmp/verify_output.log ]; then
     echo "SKIP: Hidden problem not found in verification"
     echo '{"files": []}' > .codex-repair-files.json
     exit 0
   ```

   **If verification cannot run - check signals and description:**
   ```bash
   else
     # Cannot verify - check if signals are specific enough
     # Strong signals: 3+ specific errors with line numbers/details
     # Weak signals: vague descriptions, generic messages

     if <signals_are_specific_and_detailed>; then
       echo "PROCEED: Cannot verify but signals are specific"
       # Continue to fix
     else
       echo "SKIP: Cannot verify and signals too vague"
       echo '{"files": []}' > .codex-repair-files.json
       exit 0
     fi
   fi
   ```

**Example for HIDDEN problem validation:**
```bash
# Check if this is a hidden problem that needs validation
PROBLEM_TYPE="<problem_type>"

if [ "$PROBLEM_TYPE" = "ci_failure" ]; then
  echo "PRIMARY PROBLEM - Proceeding directly to fix (no validation needed)"
  # Skip to fix implementation
else
  echo "HIDDEN PROBLEM - Running validation..."

  # Try verification
  if pre-commit run --files src/module.py 2>&1 | tee /tmp/verify_output.log; then
    VERIFY_EXIT_CODE=0
  else
    VERIFY_EXIT_CODE=$?
  fi

  # Check signals
  SIGNALS_FOUND=false
  if grep -qF "F401 unused import" /tmp/verify_output.log 2>/dev/null; then
    SIGNALS_FOUND=true
  fi

  # Decide
  if [ "$SIGNALS_FOUND" = "true" ]; then
    echo "PROCEED: Hidden problem confirmed"
  elif [ -f /tmp/verify_output.log ]; then
    echo "SKIP: Hidden problem not found"
    echo '{"files": []}' > .codex-repair-files.json
    exit 0
  else
    echo "SKIP: Cannot verify hidden problem"
    echo '{"files": []}' > .codex-repair-files.json
    exit 0
  fi
fi
```

**Decision Summary:**
- PRIMARY (ci_failure): PROCEED immediately, no validation
- HIDDEN + verification confirms: PROCEED
- HIDDEN + verification shows no problem: SKIP
- HIDDEN + cannot verify + strong signals: PROCEED
- HIDDEN + cannot verify + weak signals: SKIP

**For automated tool failures (formatters, linters, type checkers):**
- Prefer running the tool with auto-fix flags
- Let the tool fix all affected files at once
- Only manually edit if the tool cannot auto-fix

**After completing ANY fix - VERIFY formatting/linting (CRITICAL):**
Before finalizing your repair:
1. Check if your changed files have formatting or linting issues
2. If issues exist, use available auto-fix tools to resolve them
3. Verify issues are resolved by checking again
4. The repair strategy from memory may suggest specific tools - use those
5. If no specific tool suggested, detect and use what's available in the repo

This prevents formatting/linting-only failures from causing patch rejection.

**General workflow:**
1. **CHECK if problem exists** (see STEP 0 above - REQUIRED)
2. Inspect the repository and understand the problem from the supplied context
3. Make the minimal correct change to fix the issue
4. **VERIFY AND FIX**: Check formatting/linting on changed files, fix if needed
5. Do not modify unrelated files
6. Write `.codex-repair-files.json` in the repository root with the relative
   paths of every file intended for the final repair, for example
   `{"files": ["src/fix.py", "tests/test_fix.py"]}`. Include intended files
   from earlier problems in the same issue. The harness captures only these
   files. Do not use `git add` or commit.
7. OPTIONAL: Run validation ONLY on files you changed (not the whole repo)

**Scope:**
- Fix this problem only (do not fix unrelated issues)
- Tool caches, downloaded environments, build outputs, and temporary files are
  execution artifacts. Do not list them in `.codex-repair-files.json`.
- **NEVER include hidden files/directories** (those starting with ".") in your
  manifest unless they are common config files like `.gitignore`, `.github/`,
  or CI-specific configs. Specifically exclude:
  - `.agent-cache/`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`
  - `.coverage`, `.DS_Store`, `__pycache__/`
  - Any pre-commit cache, pip cache, or temp directories
- Review the manifest before finishing. List all intended edits and exclude
  generated artifacts, even if they appear in `git status`.
- Preserve existing behavior unless proven wrong by CI
- Do not remove tests or weaken checks
- Do not update dependencies unless required by the fix
- Preserve relevant configuration and package changes required by the fix
- Do NOT run validation on the entire repository (may have unrelated failures)
- If you verify, run validation ONLY on the specific files you changed

**Important:**
- **DO NOT commit** - leave intended repair changes in the working tree and
  list them in `.codex-repair-files.json`
- The harness will capture your changes and convert them to unified diff format
- Don't worry if repo-wide validation fails due to other issues
- Your fix should address the specific problem described below

**Final report:**
- Root cause identified
- Files changed
- Whether validation passed on YOUR changes (not whole repo)
- Any remaining risks
"""

_BASELINE_MODE_INSTRUCTIONS = r"""
## Analysis Mode

Analyze the problem from the complete CI failure and verification context
provided below. Use repository evidence to confirm the supplied root cause and
repair details rather than assuming they are complete.
"""

_MEMORY_MODE_INSTRUCTIONS = r"""
## Analysis Mode

The dynamic context may include a repair plan derived from similar successful
fixes. If a repair plan is provided, use it as the primary strategy, while
confirming it against the current repository and CI evidence. Pay attention to
its pitfalls and validation command. If it is missing or incomplete, derive the
minimal correct fix from the problem description, root cause, affected files,
error signals, and verification details.
"""

_DYNAMIC_CONTEXT_INTRO = r"""
## Dynamic Task Context

Everything after the boundary below belongs to the current issue. Treat it as
authoritative task input. It may change independently for every issue and must
never be replaced by context from another repair.
"""

STABLE_PROMPT_PREFIXES = {
    "baseline": (
        _COMMON_REPAIR_INSTRUCTIONS
        + _BASELINE_MODE_INSTRUCTIONS
        + _DYNAMIC_CONTEXT_INTRO
    ).strip(),
    "memory": (
        _COMMON_REPAIR_INSTRUCTIONS
        + _MEMORY_MODE_INSTRUCTIONS
        + _DYNAMIC_CONTEXT_INTRO
    ).strip(),
}


def prompt_mode(ablation: str) -> str:
    """Map an ablation name to its stable prompt family."""
    return "baseline" if str(ablation).lower() == "baseline" else "memory"


def render_ci_repair_prompt(mode: str, dynamic_context: str) -> str:
    """Render a stable exact prefix followed by untouched dynamic context."""
    try:
        stable_prefix = STABLE_PROMPT_PREFIXES[mode]
    except KeyError as exc:
        raise ValueError(f"Unsupported CI repair prompt mode: {mode}") from exc

    return (
        stable_prefix
        + DYNAMIC_CONTEXT_BOUNDARY
        + str(dynamic_context).strip()
        + "\n"
    )


def prompt_cache_info(prompt: str) -> dict[str, Any]:
    """Describe the exact-prefix boundary without hashing dynamic issue data."""
    stable_prefix, boundary, dynamic_context = str(prompt).partition(
        DYNAMIC_CONTEXT_BOUNDARY
    )
    if not boundary:
        return {
            "layout": "legacy_dynamic_prompt",
            "template_fingerprint": None,
            "stable_prefix_chars": 0,
            "dynamic_context_chars": len(str(prompt)),
        }

    fingerprint = hashlib.sha256(stable_prefix.encode("utf-8")).hexdigest()[:16]
    return {
        "layout": "stable_prefix_dynamic_suffix_v1",
        "template_fingerprint": fingerprint,
        "stable_prefix_chars": len(stable_prefix),
        "dynamic_context_chars": len(dynamic_context),
    }
