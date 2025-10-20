#!/usr/bin/env python3
"""
Zero-fill fix script for Grafana dashboards
Adds "or vector(0)" fallback to rate(), irate(), and histogram_quantile() queries
to prevent "No data" in idle periods
"""

import json
import glob
import re
import sys
from pathlib import Path

def fix_expr(expr: str) -> tuple[str, bool]:
    """
    Add zero-fill fallback to Prometheus queries.
    Returns (fixed_expr, changed)
    """
    if not expr or not isinstance(expr, str):
        return expr, False

    original = expr

    # Pattern to match rate/irate/histogram_quantile that don't already have "or vector(0)"
    if 'or vector(0)' in expr or 'or 0' in expr:
        return expr, False  # Already has fallback

    # Check if expression contains rate, irate, or histogram_quantile
    if any(keyword in expr for keyword in ['rate(', 'irate(', 'histogram_quantile(']):
        # Add fallback at the end of the expression
        # Handle complex expressions by wrapping in parentheses if needed
        expr = expr.strip()
        if expr and not expr.endswith(')'):
            expr = f"({expr}) or vector(0)"
        else:
            expr = f"{expr} or vector(0)"
        return expr, True

    return expr, False

def process_dashboard(file_path: Path) -> tuple[int, int]:
    """
    Process a single dashboard file.
    Returns (panels_processed, panels_modified)
    """
    print(f"Processing: {file_path}")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"  ERROR: Invalid JSON in {file_path}: {e}")
        return 0, 0
    except Exception as e:
        print(f"  ERROR: Failed to read {file_path}: {e}")
        return 0, 0

    panels_processed = 0
    panels_modified = 0

    # Process all panels (including nested panels in rows)
    def process_panels(panels):
        nonlocal panels_processed, panels_modified
        if not panels:
            return

        for panel in panels:
            # Handle row panels with nested panels
            if panel.get('type') == 'row' and 'panels' in panel:
                process_panels(panel['panels'])
                continue

            panels_processed += 1

            # Process targets (queries)
            targets = panel.get('targets', [])
            for target in targets:
                if 'expr' in target:
                    original_expr = target['expr']
                    fixed_expr, changed = fix_expr(original_expr)
                    if changed:
                        target['expr'] = fixed_expr
                        panels_modified += 1
                        print(f"  ✓ Modified panel '{panel.get('title', 'Untitled')}'")
                        print(f"    Before: {original_expr[:80]}...")
                        print(f"    After:  {fixed_expr[:80]}...")

    process_panels(data.get('panels', []))

    if panels_modified > 0:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"  ✅ Saved changes: {panels_modified}/{panels_processed} panels modified\n")
        except Exception as e:
            print(f"  ERROR: Failed to write {file_path}: {e}")
            return panels_processed, 0
    else:
        print(f"  ℹ️  No changes needed\n")

    return panels_processed, panels_modified

def main():
    base_dir = Path('/home/mint/projects/claude_sandbox/zakupai/monitoring/grafana/provisioning/dashboards')

    if not base_dir.exists():
        print(f"ERROR: Dashboard directory not found: {base_dir}")
        return 1

    dashboard_files = list(base_dir.glob('**/*.json'))
    # Exclude backup files
    dashboard_files = [f for f in dashboard_files if not f.name.endswith('.bak') and '.bak-' not in f.name]

    if not dashboard_files:
        print("ERROR: No dashboard files found")
        return 1

    print(f"Found {len(dashboard_files)} dashboard files\n")
    print("=" * 80)

    total_panels = 0
    total_modified = 0

    for file_path in sorted(dashboard_files):
        panels, modified = process_dashboard(file_path)
        total_panels += panels
        total_modified += modified

    print("=" * 80)
    print(f"\n📊 Summary:")
    print(f"  Dashboards processed: {len(dashboard_files)}")
    print(f"  Total panels: {total_panels}")
    print(f"  Panels modified: {total_modified}")

    if total_modified > 0:
        print(f"\n✅ Zero-fill fixes applied successfully!")
        return 0
    else:
        print(f"\nℹ️  No modifications were needed")
        return 0

if __name__ == '__main__':
    sys.exit(main())
