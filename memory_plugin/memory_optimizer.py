"""
Memory Optimizer - Minimal addition for smart filtering.
Removes repetitive info and prioritizes L1 > L2 > L3.
"""

import json
from typing import Dict, List, Any


def optimize_memories(
    l1_matches: List[Dict],
    l2_matches: List[Dict],
    l3_matches: List[Dict],
    max_total_size: int = 100000  # ~100K tokens
) -> tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Smart memory optimization:
    1. Remove duplicate information across L1/L2/L3
    2. Skip L3 if L1+L2 are sufficient
    3. Prioritize L1 > L2 > L3 if too large

    Returns: (filtered_l1, filtered_l2, filtered_l3)
    """

    # Step 1: Deduplicate across levels
    l1_deduped = l1_matches  # Never filter L1
    l2_deduped = _deduplicate_against(l2_matches, l1_matches)
    l3_deduped = _deduplicate_against(l3_matches, l1_matches + l2_deduped)

    # Step 2: Check size
    l1_size = _estimate_size(l1_deduped)
    l2_size = _estimate_size(l2_deduped)
    l3_size = _estimate_size(l3_deduped)
    total_size = l1_size + l2_size + l3_size

    # Step 3: If L1+L2 are sufficient and fit, skip L3
    if _is_sufficient(l1_deduped, l2_deduped) and (l1_size + l2_size <= max_total_size):
        print(f"[Optimizer] ✅ L1+L2 sufficient ({l1_size + l2_size} chars), skipping L3")
        return l1_deduped, l2_deduped, []

    # Step 4: If everything fits, use all
    if total_size <= max_total_size:
        print(f"[Optimizer] ✅ All levels fit ({total_size} chars)")
        return l1_deduped, l2_deduped, l3_deduped

    # Step 5: Too large - prioritize L1 > L2 > L3
    print(f"[Optimizer] ⚠️ Too large ({total_size} chars), prioritizing...")
    return _prioritize_by_importance(
        l1_deduped, l2_deduped, l3_deduped, max_total_size
    )


def _deduplicate_against(
    matches: List[Dict],
    reference: List[Dict]
) -> List[Dict]:
    """Remove matches that have same file+solution as reference"""
    if not matches or not reference:
        return matches

    # Build signature set from reference
    ref_signatures = set()
    for ref in reference:
        sig = _get_match_signature(ref)
        if sig:
            ref_signatures.add(sig)

    # Filter out duplicates
    deduped = []
    removed_count = 0
    for match in matches:
        sig = _get_match_signature(match)
        if sig not in ref_signatures:
            deduped.append(match)
        else:
            removed_count += 1

    if removed_count > 0:
        print(f"[Optimizer] 🔄 Removed {removed_count} duplicate matches")

    return deduped


def _get_match_signature(match: Dict) -> str:
    """Get unique signature for a match (file + key fix pattern)"""
    try:
        # Try to extract file and solution
        files = match.get("changed_files", [])
        diff = match.get("diff", "")
        solution = match.get("solution", "")

        # Create signature from files + first 200 chars of fix
        file_str = "|".join(sorted(files[:3]))  # Top 3 files
        fix_str = (diff + solution)[:200]  # First 200 chars

        return f"{file_str}||{fix_str}"
    except:
        return ""


def _is_sufficient(l1: List[Dict], l2: List[Dict]) -> bool:
    """Check if L1+L2 have enough context"""
    return (
        len(l1) >= 3 or      # Have 3+ similar fixes
        len(l2) >= 5 or      # Have 5+ common patterns
        len(l1) + len(l2) >= 8  # Total of 8+ memories
    )


def _estimate_size(matches: List[Dict]) -> int:
    """Estimate size in characters"""
    if not matches:
        return 0
    try:
        return len(json.dumps(matches))
    except:
        return len(str(matches))


def _prioritize_by_importance(
    l1: List[Dict],
    l2: List[Dict],
    l3: List[Dict],
    max_size: int
) -> tuple[List[Dict], List[Dict], List[Dict]]:
    """
    When too large: Keep ALL L1, fit L2, add L3 only if room.
    """

    l1_size = _estimate_size(l1)

    # Priority 1: Keep ALL L1 (never compromise)
    if l1_size > max_size * 0.8:  # L1 alone > 80% of limit
        print(f"[Optimizer] ⚠️ L1 alone is large ({l1_size} chars)")
        # Keep all L1, skip L2/L3
        return l1, [], []

    remaining = max_size - l1_size

    # Priority 2: Fit as much L2 as possible
    l2_size = _estimate_size(l2)
    if l2_size <= remaining * 0.6:  # L2 fits in 60% of remaining
        l2_kept = l2
        l2_size_kept = l2_size
    else:
        # Truncate L2 to fit
        l2_kept = _truncate_to_size(l2, int(remaining * 0.6))
        l2_size_kept = _estimate_size(l2_kept)
        print(f"[Optimizer] 🔄 Truncated L2: {len(l2)} → {len(l2_kept)} matches")

    remaining = max_size - l1_size - l2_size_kept

    # Priority 3: Add L3 only if room (minimum 10K chars)
    if remaining >= 10000:
        l3_kept = _truncate_to_size(l3, remaining)
        if len(l3_kept) < len(l3):
            print(f"[Optimizer] 🔄 Truncated L3: {len(l3)} → {len(l3_kept)} matches")
    else:
        l3_kept = []
        print(f"[Optimizer] ⚠️ No room for L3 (only {remaining} chars left)")

    final_size = l1_size + l2_size_kept + _estimate_size(l3_kept)
    print(f"[Optimizer] ✅ Prioritized: L1={len(l1)}, L2={len(l2_kept)}, L3={len(l3_kept)} ({final_size} chars)")

    return l1, l2_kept, l3_kept


def _truncate_to_size(matches: List[Dict], max_size: int) -> List[Dict]:
    """Keep matches until size limit"""
    if not matches:
        return []

    kept = []
    current_size = 0

    for match in matches:
        match_size = _estimate_size([match])
        if current_size + match_size <= max_size:
            kept.append(match)
            current_size += match_size
        else:
            break

    return kept
