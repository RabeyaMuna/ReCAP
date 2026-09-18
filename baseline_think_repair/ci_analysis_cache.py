"""
CI Analysis Cache - Load from log_details.json or generate with CI log analyzer.
"""

import json
from pathlib import Path
from typing import Dict, Optional
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utilities.ci_log_analyzer import _run_log_analysis


class CIAnalysisCache:
    """
    Cache for CI failure analyses.

    Priority:
    1. Load from log_details.json if available
    2. Generate with CI log analyzer and save to cache
    3. Use cached analysis
    """

    def __init__(
        self,
        log_details_path: str = "data/log_details.json",
        cache_path: str = "baseline_think_repair/ci_analysis_cache.json"
    ):
        self.log_details_path = Path(log_details_path)
        self.cache_path = Path(cache_path)

        # Load log_details.json (pre-generated analyses)
        self.log_details = self._load_log_details()

        # Load/create analysis cache (for newly generated ones)
        self.analysis_cache = self._load_cache()

    def _load_log_details(self) -> Dict:
        """Load pre-generated log details."""
        if not self.log_details_path.exists():
            print(f"Warning: {self.log_details_path} not found")
            return {}

        with open(self.log_details_path) as f:
            data = json.load(f)

        # Build lookup by sha_fail and id
        lookup = {}
        if isinstance(data, list):
            for entry in data:
                sha = entry.get('sha_fail')
                issue_id = entry.get('id')
                if sha:
                    lookup[f"sha_{sha}"] = entry
                if issue_id is not None:
                    lookup[f"id_{issue_id}"] = entry

        print(f"Loaded {len(lookup)} entries from log_details.json")
        return lookup

    def _load_cache(self) -> Dict:
        """Load analysis cache."""
        if not self.cache_path.exists():
            return {}

        with open(self.cache_path) as f:
            cache = json.load(f)

        print(f"Loaded {len(cache)} entries from analysis cache")
        return cache

    def _save_cache(self):
        """Save analysis cache."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, 'w') as f:
            json.dump(self.analysis_cache, f, indent=2)

    def _get_key(self, instance: Dict) -> str:
        """Get lookup key for instance."""
        sha = instance.get('sha_fail')
        issue_id = instance.get('instance_id') or instance.get('id')

        if sha:
            return f"sha_{sha}"
        elif issue_id:
            return f"id_{issue_id}"
        else:
            return f"unknown_{hash(str(instance))}"

    def get_analysis(self, instance: Dict, model: str = "deepseek-v4-flash") -> Dict:
        """
        Get CI analysis for an instance.

        Priority:
        1. Check log_details.json
        2. Check analysis cache
        3. Generate with CI analyzer and cache it
        """
        key = self._get_key(instance)

        # 1. Try log_details.json first
        if key in self.log_details:
            return self.log_details[key]

        # 2. Try analysis cache
        if key in self.analysis_cache:
            return self.analysis_cache[key]

        # 3. Generate with CI analyzer
        print(f"\nGenerating CI analysis for {key}...")
        try:
            analysis = _run_log_analysis(
                instance=instance,  # Correct parameter name
                llm=None,  # Use default
                model=model
            )

            # Save to cache
            self.analysis_cache[key] = analysis
            self._save_cache()

            return analysis

        except Exception as e:
            print(f"Error generating analysis for {key}: {e}")
            # Return minimal analysis
            return {
                'error_summary': 'Analysis generation failed',
                'error_context': str(e),
                'relevant_files': [],
                'failure_signals': []
            }

    def format_analysis(self, analysis: Dict) -> str:
        """Format analysis dict into readable text."""
        parts = []

        # Error context (most important)
        if analysis.get('error_context'):
            context = analysis['error_context']
            if isinstance(context, list):
                context = '\n'.join(context)
            parts.append(f"## Error Context\n{context}\n")

        # Failure signals
        if analysis.get('failure_signals'):
            parts.append("## Failure Signals")
            for signal in analysis['failure_signals']:
                parts.append(f"- {signal}")
            parts.append("")

        # Relevant files
        if analysis.get('relevant_files'):
            parts.append("## Relevant Files")
            for file_info in analysis['relevant_files']:
                file_path = file_info.get('file', 'unknown')
                line_num = file_info.get('line_number', '?')
                issue_type = file_info.get('issue_type', '')
                reason = file_info.get('reason', '')

                parts.append(f"### {file_path}:{line_num}")
                if issue_type:
                    parts.append(f"**Type:** {issue_type}")
                if reason:
                    parts.append(f"**Reason:** {reason}")
                parts.append("")

        # Error types
        if analysis.get('error_types'):
            parts.append("## Error Types")
            for err in analysis['error_types']:
                category = err.get('category', 'Unknown')
                subcategory = err.get('subcategory', '')
                parts.append(f"- **{category}**: {subcategory}")
            parts.append("")

        # Failed job
        if analysis.get('failed_job'):
            jobs = analysis['failed_job']
            if jobs:
                parts.append("## Failed Job")
                for job_info in jobs:
                    job = job_info.get('job', 'unknown')
                    step = job_info.get('step', 'unknown')
                    command = job_info.get('command', 'unknown')
                    parts.append(f"- **Job:** {job}")
                    parts.append(f"  **Step:** {step}")
                    parts.append(f"  **Command:** `{command}`")
                parts.append("")

        return "\n".join(parts)


# Global cache instance
_global_cache = None


def get_ci_analysis_for_instance(instance: Dict, model: str = "deepseek-v4-flash") -> str:
    """
    Get formatted CI analysis for an instance.

    This is the main function to use.
    """
    global _global_cache

    if _global_cache is None:
        _global_cache = CIAnalysisCache()

    analysis = _global_cache.get_analysis(instance, model=model)
    return _global_cache.format_analysis(analysis)
