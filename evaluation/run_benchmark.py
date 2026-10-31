"""
RAG Doctor — Deterministic Specialist Evaluation Runner.

Loads golden diagnostic cases, submits them to the FastAPI
endpoint, and compares actual findings with expected outcomes.

This is a diagnostic rule evaluation, not a measurement of
semantic correctness or LLM hallucination detection accuracy.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import httpx


EVALUATION_DIR = Path(__file__).resolve().parent
BENCHMARK_FILE = EVALUATION_DIR / "golden_cases.json"

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
REQUEST_TIMEOUT = 30.0


def load_benchmark() -> dict:
    """Load and validate the golden evaluation dataset."""

    if not BENCHMARK_FILE.exists():
        raise FileNotFoundError(
            f"Benchmark file not found: {BENCHMARK_FILE}"
        )

    with BENCHMARK_FILE.open("r", encoding="utf-8") as file:
        benchmark = json.load(file)

    cases = benchmark.get("cases")

    if not isinstance(cases, list) or not cases:
        raise ValueError(
            "Benchmark must contain a non-empty cases list."
        )

    return benchmark


def finding_signature(finding: dict) -> tuple:
    """Extract the fields used to compare diagnostic findings."""

    return (
        finding.get("category"),
        finding.get("agent"),
        finding.get("severity"),
    )


def format_findings(findings: list[dict]) -> list[str]:
    """Format findings for readable terminal output."""

    if not findings:
        return ["(no findings)"]

    return [
        f"{item.get('category')} | "
        f"{item.get('agent')} | "
        f"{item.get('severity')}"
        for item in findings
    ]


def evaluate_case(
    client: httpx.Client,
    case: dict,
) -> bool:
    """Execute one golden case and compare expected outcomes."""

    test_id = case["test_id"]
    title = case["title"]

    expected = case.get("expected_findings", [])

    try:
        response = client.post(
            "/api/v1/diagnostics",
            json=case["input"],
        )
    except httpx.HTTPError as exc:
        print(f"[FAIL] {test_id} — {title}")
        print(f"       API communication error: {exc}")
        return False

    if response.status_code != 200:
        print(f"[FAIL] {test_id} — {title}")
        print(f"       HTTP status: {response.status_code}")
        print(f"       Response: {response.text[:500]}")
        return False

    try:
        result = response.json()
    except ValueError:
        print(f"[FAIL] {test_id} — {title}")
        print("       API returned invalid JSON.")
        return False

    report = result.get("report", {})
    findings = report.get("findings", [])
    errors = result.get("errors", [])

    expected_signatures = sorted(
        finding_signature(item)
        for item in expected
    )

    actual_signatures = sorted(
        finding_signature(item)
        for item in findings
    )

    checks = {
        "workflow completed": report.get("status") == "completed",
        "no specialist errors": len(errors) == 0,
        "expected findings matched": (
            Counter(expected_signatures)
            == Counter(actual_signatures)
        ),
    }

    passed = all(checks.values())

    label = "PASS" if passed else "FAIL"

    print(f"[{label}] {test_id} — {title}")

    if not passed:
        for check_name, check_passed in checks.items():
            if not check_passed:
                print(f"       Failed check: {check_name}")

        print("       Expected findings:")
        for item in format_findings(expected):
            print(f"         - {item}")

        print("       Actual findings:")
        for item in format_findings(findings):
            print(f"         - {item}")

        if errors:
            print(f"       Specialist errors: {len(errors)}")

    return passed


def main() -> int:
    """Run all evaluation cases and print the benchmark summary."""

    parser = argparse.ArgumentParser(
        description="Run the RAG Doctor specialist evaluation benchmark."
    )

    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="FastAPI base URL (default: http://127.0.0.1:8000)",
    )

    args = parser.parse_args()

    try:
        benchmark = load_benchmark()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Benchmark loading failed: {exc}")
        return 1

    cases = benchmark["cases"]

    print("=" * 65)
    print(benchmark["benchmark_name"])
    print(f"Version: {benchmark['benchmark_version']}")
    print(f"Test cases: {len(cases)}")
    print(f"API endpoint: {args.base_url}/api/v1/diagnostics")
    print("=" * 65)

    passed_count = 0

    try:
        with httpx.Client(
            base_url=args.base_url.rstrip("/"),
            timeout=REQUEST_TIMEOUT,
        ) as client:
            for case in cases:
                if evaluate_case(client, case):
                    passed_count += 1

    except httpx.HTTPError as exc:
        print(f"\nUnable to connect to the FastAPI backend: {exc}")
        return 1

    total = len(cases)
    failed_count = total - passed_count
    agreement = (passed_count / total) * 100

    print("\n" + "=" * 65)
    print("EVALUATION SUMMARY")
    print("=" * 65)
    print(f"Total test cases : {total}")
    print(f"Passed           : {passed_count}")
    print(f"Failed           : {failed_count}")
    print(f"Expected-output agreement: {agreement:.2f}%")
    print("=" * 65)

    if failed_count:
        print("RESULT: BENCHMARK FAILED")
        return 1

    print("RESULT: ALL EVALUATION CASES PASSED")

    return 0


if __name__ == "__main__":
    sys.exit(main())