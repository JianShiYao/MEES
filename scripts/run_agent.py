#!/usr/bin/env python3
"""CLI for a single MEES Agent request."""
import argparse
import json
import sys
from pathlib import Path

from agent_runtime import AgentInputError, ROOT, run_request


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("request")
    parser.add_argument("--output", required=True)
    parser.add_argument("--audit", default="build/agents/audit.jsonl")
    args = parser.parse_args()
    try:
        request = json.loads((ROOT / args.request).read_text(encoding="utf-8"))
        result = run_request(request, ROOT / args.audit)
    except (OSError, json.JSONDecodeError, AgentInputError) as exc:
        print(f"[agent] {exc}", file=sys.stderr)
        return 2
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{result['agent']}: {result['decision']}; {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
