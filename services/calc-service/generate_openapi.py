#!/usr/bin/env python3
"""
Generate OpenAPI schema for calc-service.
Stage 7 Phase 1: Security Quick Wins

Usage:
    python generate_openapi.py

Output:
    ../../docs/openapi-calc.json
"""

import json
import os
import sys

# Add parent directory to path to import main
sys.path.insert(0, os.path.dirname(__file__))

from main import app


def generate_openapi_schema():
    """Generate OpenAPI schema and save to docs directory."""
    # Get OpenAPI schema
    openapi_schema = app.openapi()

    # Ensure docs directory exists
    docs_dir = os.path.join(os.path.dirname(__file__), "..", "..", "docs")
    os.makedirs(docs_dir, exist_ok=True)

    # Save to file
    output_path = os.path.join(docs_dir, "openapi-calc.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2, ensure_ascii=False)

    print(f"✅ OpenAPI schema generated: {output_path}")
    print(f"📊 Endpoints: {len([p for p in openapi_schema.get('paths', {}).values() for m in p.values()])}")
    print(f"📋 Schemas: {len(openapi_schema.get('components', {}).get('schemas', {}))}")

    return output_path


if __name__ == "__main__":
    try:
        output = generate_openapi_schema()
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error generating OpenAPI schema: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
