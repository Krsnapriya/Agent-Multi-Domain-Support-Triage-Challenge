#!/usr/bin/env python3
"""
Multi-Domain Support Triage Agent
HackerRank Orchestrate Hackathon - May 2026

Entry point: reads support_tickets/support_tickets.csv,
processes each ticket through the triage pipeline,
writes results to support_tickets/output.csv
"""

import sys
from pathlib import Path

# Add code directory to path for imports
code_dir = Path(__file__).parent
sys.path.insert(0, str(code_dir))

from robust_agent import RobustTriageAgent


def main():
    # Resolve paths relative to repo root (one level up from code/)
    repo_root = code_dir.parent
    input_csv = repo_root / "support_issues" / "support_issues.csv"
    output_csv = repo_root / "support_issues" / "output.csv"
    data_dir = repo_root / "data"

    # Validate paths
    if not input_csv.exists():
        print(f"[ERROR] Could not find support_tickets.csv at {input_csv}")
        sys.exit(1)

    if not data_dir.exists():
        print(f"[ERROR] data/ directory not found at {data_dir}")
        sys.exit(1)

    print("=" * 60)
    print("  Multi-Domain Support Triage Agent")
    print("  HackerRank Orchestrate - May 2026")
    print("=" * 60)
    print(f"  Input : {input_csv}")
    print(f"  Output: {output_csv}")
    print(f"  Corpus: {data_dir}")
    print("=" * 60)

    # Initialize agent (loads and indexes corpus)
    print("\n[1/3] Loading and indexing corpus...")
    agent = RobustTriageAgent()
    print(f"      Done. Loaded {agent.corpus.total_articles} articles")

    # Process tickets
    print(f"\n[2/3] Triaging tickets...\n")
    results = agent.process_csv(str(input_csv))

    # Write output CSV
    agent.write_output(results, str(output_csv))

    # Summary
    total = len(results)
    replied = sum(1 for r in results if r["status"] == "replied")
    escalated = total - replied
    print(f"\n{'=' * 60}")
    print(f"  Done. {total} tickets processed.")
    print(f"  replied={replied}  escalated={escalated}  "
          f"({100*replied/total:.0f}% reply rate)")
    print(f"  Output written to: {output_csv}")
    print("=" * 60)


if __name__ == "__main__":
    main()
