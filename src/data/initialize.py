"""Initialization Pipeline
Loads all raw CSV files, runs data validation, applies normalization,
and loads datasets into DuckDB analytical storage.
"""

import sys
from src.data.loader import load_all_data
from src.data.validator import DataValidator
from src.data.normalizer import normalize_all_data
from src.data.repository import LogisticsRepository


def run_initialization():
    print("[1/4] Loading raw datasets...")
    raw_data = load_all_data()

    print("[2/4] Validating schemas and integrity constraints...")
    validator = DataValidator(raw_data)
    report = validator.run_all()
    print(report.summary())

    if not report.is_valid:
        print("Validation failed with critical errors! Aborting initialization.")
        sys.exit(1)

    print("[3/4] Normalizing and computing derived attributes...")
    normalized_data = normalize_all_data(raw_data)

    print("[4/4] Populating DuckDB analytical storage...")
    repo = LogisticsRepository()
    repo.initialize_database(normalized_data)

    print("Initialization completed successfully!")


if __name__ == "__main__":
    run_initialization()

