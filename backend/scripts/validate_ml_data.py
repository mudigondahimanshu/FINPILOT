#!/usr/bin/env python3
"""
ML data validation with Great Expectations (Phase 4.4).

Validates that the transaction dataset used for classifier training
meets quality expectations before training begins.

Run: python scripts/validate_ml_data.py [--csv path/to/transactions.csv]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

CATEGORIES = [
    "Food", "Transport", "Shopping", "Entertainment", "Health",
    "Utilities", "Travel", "Education", "Salary", "Investments",
    "Rent", "Insurance", "Dining", "Subscriptions", "Other",
]


def build_suite() -> list[dict]:
    """Return a list of GE-compatible expectation configs."""
    return [
        # Column presence
        {
            "expectation_type": "expect_table_columns_to_match_ordered_list",
            "kwargs": {
                "column_list": ["description", "amount", "date", "category"],
                "exact_match": False,
            },
        },

        # description — must be non-null, non-empty strings
        {"expectation_type": "expect_column_values_to_not_be_null",
         "kwargs": {"column": "description"}},
        {"expectation_type": "expect_column_value_lengths_to_be_between",
         "kwargs": {"column": "description", "min_value": 2, "max_value": 500}},

        # amount — numeric, reasonable range
        {"expectation_type": "expect_column_values_to_not_be_null",
         "kwargs": {"column": "amount"}},
        {"expectation_type": "expect_column_values_to_be_between",
         "kwargs": {"column": "amount", "min_value": -1_000_000, "max_value": 1_000_000}},

        # date — not null
        {"expectation_type": "expect_column_values_to_not_be_null",
         "kwargs": {"column": "date"}},
        {"expectation_type": "expect_column_values_to_match_strftime_format",
         "kwargs": {"column": "date", "strftime_format": "%Y-%m-%d"}},

        # category — from known set, low null rate
        {"expectation_type": "expect_column_values_to_be_in_set",
         "kwargs": {"column": "category", "value_set": CATEGORIES, "mostly": 0.95}},

        # Dataset-level
        {"expectation_type": "expect_table_row_count_to_be_between",
         "kwargs": {"min_value": 100, "max_value": 10_000_000}},
    ]


def validate_with_ge(csv_path: Path) -> bool:
    """Run Great Expectations validation. Returns True if all critical checks pass."""
    try:
        import great_expectations as gx  # noqa: PLC0415
    except ImportError:
        print("ERROR: great_expectations and pandas required")
        print("Run: pip install great-expectations pandas")
        return False

    context = gx.get_context()
    ds = context.data_sources.add_pandas(name="transactions")
    asset = ds.add_dataframe_asset(name="train_data")
    batch_def = asset.add_batch_definition_whole_dataframe("batch")

    suite = context.suites.add(gx.ExpectationSuite(name="transaction_quality"))
    for exp in build_suite():
        suite.add_expectation(gx.expectations.UnexpectedRowsExpectation(**exp))  # type: ignore[attr-defined]

    results = context.run_checkpoint(
        checkpoint=context.checkpoints.add(
            gx.Checkpoint(
                name="transaction_quality_checkpoint",
                validation_definitions=[
                    context.validation_definitions.add(
                        gx.ValidationDefinition(
                            name="transaction_quality",
                            data=batch_def,
                            suite=suite,
                        )
                    )
                ],
            )
        )
    )

    passed = results.success
    stats = results.statistics
    print(f"\nGreat Expectations: {'✓ PASS' if passed else '✗ FAIL'}")
    print(f"  Evaluated: {stats['evaluated_expectations']}")
    print(f"  Successful: {stats['successful_expectations']}")
    print(f"  Failed:     {stats['unsuccessful_expectations']}")
    return passed


def validate_simple(csv_path: Path) -> bool:
    """Lightweight validation without GE (used when GE not installed)."""
    import csv  # noqa: PLC0415
    from datetime import datetime  # noqa: PLC0415

    errors: list[str] = []
    row_count = 0

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        required = {"description", "amount", "date", "category"}
        if not required.issubset(set(reader.fieldnames or [])):
            missing = required - set(reader.fieldnames or [])
            print(f"FAIL: missing columns: {missing}")
            return False

        for i, row in enumerate(reader, 1):
            row_count += 1
            if not row["description"] or len(row["description"]) < 2:
                errors.append(f"Row {i}: empty description")
            try:
                amt = float(row["amount"])
                if not (-1_000_000 <= amt <= 1_000_000):
                    errors.append(f"Row {i}: amount out of range: {amt}")
            except ValueError:
                errors.append(f"Row {i}: non-numeric amount: {row['amount']!r}")
            try:
                datetime.strptime(row["date"], "%Y-%m-%d")
            except ValueError:
                errors.append(f"Row {i}: invalid date: {row['date']!r}")
            if row["category"] and row["category"] not in CATEGORIES:
                errors.append(f"Row {i}: unknown category: {row['category']!r}")

    if row_count < 100:
        errors.append(f"Too few rows: {row_count} (need ≥ 100)")

    for err in errors[:20]:
        print(f"  ERROR: {err}")
    if len(errors) > 20:
        print(f"  ... and {len(errors) - 20} more errors")

    passed = len(errors) == 0
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"\nSimple validation: {status} ({row_count} rows, {len(errors)} errors)")
    return passed


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate ML training data quality")
    parser.add_argument(
        "--csv", type=Path, default=Path("data/transactions_train.csv")
    )
    parser.add_argument(
        "--simple",
        action="store_true",
        help="Skip Great Expectations; use built-in checks",
    )
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"ERROR: {args.csv} not found")
        print("Generate synthetic data with:")
        print("  python scripts/train_classifier.py --generate-data-only")
        sys.exit(1)

    if args.simple:
        ok = validate_simple(args.csv)
    else:
        try:
            ok = validate_with_ge(args.csv)
        except Exception as exc:
            print(f"GE validation error ({exc}); falling back to simple mode")
            ok = validate_simple(args.csv)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
