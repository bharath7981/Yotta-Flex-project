"""Master Pipeline Runner — Logistics ETA Prediction & Delay Intelligence Platform
Executes the end-to-end reproducible pipeline in strict sequential order:
1. Full-mode dataset generation when explicitly requested (--generate-full or missing raw data)
2. Relational & Business Rule Validation (src.data.validator)
3. DuckDB Analytical Lakehouse Initialization (src.data.initialize)
4. Point-in-Time Feature Engineering (src.features.feature_builder)
5. Independent Leakage Audit Across All Entities (src.features.feature_validator)
6. Pre-Training Dataset & Feature Verification (50k shipments, 100 facilities, 1k disruptions, 1k weather, 95,088 features)
7. Authoritative Multi-Slice Model Training & Held-Out Evaluation (src.models.evaluate_comprehensive)
8. Operational Anomaly Detection & Ground-Truth Benchmarking (src.anomaly.evaluator)
9. Root Cause Delay Explanation Intelligence Engine (src.intelligence.delay_explainer)
10. Operational Exception Engine & Actionable Recommendations (src.exceptions.engine)
11. Complete Analytical Data & Standalone SQL Export (src.data.exporter)
12. Complete Automated Unit & Integration Test Suite (pytest tests/)
"""

import argparse
from pathlib import Path
import subprocess
import sys
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent


def run_step(cmd_str: str, desc: str):
    print("\n" + "=" * 75)
    print(f"STEP: {desc}")
    print(f"COMMAND: {cmd_str}")
    print("=" * 75)
    args = [sys.executable] + cmd_str.split()[1:]
    res = subprocess.run(args, check=False)
    if res.returncode != 0:
        print(f"\nFATAL: Step failed with return code {res.returncode}: {desc}")
        sys.exit(res.returncode)


def verify_pre_training_counts():
    """Verify raw datasets and generated feature matrix counts before ML training."""
    print("\n" + "=" * 75)
    print("STEP: Pre-Training Dataset & Feature Matrix Verification")
    print("=" * 75)

    data_dir = PROJECT_ROOT / "data" / "generated"
    if not (data_dir / "shipments.csv").exists():
        data_dir = PROJECT_ROOT / "data" / "existing"

    ships_df = pd.read_csv(data_dir / "shipments.csv")
    facs_df = pd.read_csv(data_dir / "facilities.csv")
    disr_df = pd.read_csv(data_dir / "disruptions.csv")
    wth_df = pd.read_csv(data_dir / "weather_forecasts.csv")

    features_path = PROJECT_ROOT / "data" / "processed" / "features.csv"
    if not features_path.exists():
        print(f"FATAL: Features file missing at {features_path}!")
        sys.exit(1)
    features_df = pd.read_csv(features_path)

    print(f"  Shipments count:       {len(ships_df):,} (Required: >= 50,000)")
    print(f"  Facilities count:      {len(facs_df):,} (Required: == 100)")
    print(f"  Disruptions count:     {len(disr_df):,} (Required: >= 1,000)")
    print(f"  Weather events count:  {len(wth_df):,} (Required: >= 1,000)")
    print(f"  Feature snapshots:     {len(features_df):,} (Required: >= 90,000)")

    if len(ships_df) < 50000:
        print(f"FATAL: Insufficient shipments ({len(ships_df)} < 50,000)")
        sys.exit(1)
    if len(facs_df) != 100:
        print(f"FATAL: Invalid facilities count ({len(facs_df)} != 100)")
        sys.exit(1)
    if len(disr_df) < 1000:
        print(f"FATAL: Insufficient disruptions ({len(disr_df)} < 1,000)")
        sys.exit(1)
    if len(wth_df) < 1000:
        print(f"FATAL: Insufficient weather events ({len(wth_df)} < 1,000)")
        sys.exit(1)
    if len(features_df) < 90000:
        print(f"FATAL: Insufficient feature snapshots ({len(features_df)} < 90,000)")
        sys.exit(1)

    print("Pre-training counts verified successfully!")


def main():
    parser = argparse.ArgumentParser(description="Master Pipeline Runner for Logistics Platform")
    parser.add_argument("--generate-full", action="store_true", help="Force regeneration of full 50,000-shipment dataset")
    parser.add_argument("--skip-tests", action="store_true", help="Skip pytest execution at the end")
    args = parser.parse_args()

    print("=" * 75)
    print("STARTING LOGISTICS PLATFORM MASTER PIPELINE EXECUTION")
    print("=" * 75)

    # 1. Dataset Generation if requested or missing
    ships_file = PROJECT_ROOT / "data" / "generated" / "shipments.csv"
    if args.generate_full or not ships_file.exists():
        run_step(
            "python -m src.data_generation.generator_pipeline --mode full --seed 20261022 --shipments 50000",
            "Full-Scale Dataset Generation (50,000 shipments, seed 20261022)"
        )

    # 2. Data Validation
    run_step("python -m src.data.validator", "Data Lake Relational & Business Rule Validation")

    # 3. DuckDB Initialization
    run_step("python -m src.data.initialize", "DuckDB Analytical Storage Setup & Normalization")

    # 4. Point-in-Time Feature Engineering
    run_step("python -m src.features.feature_builder", "Point-in-Time Feature Matrix Generation")

    # 5. Independent Leakage Audit
    run_step("python -m src.features.feature_validator", "Independent Point-in-Time Leakage Audit")

    # 6. Pre-Training Verification
    verify_pre_training_counts()

    # 7. Authoritative Multi-Slice Model Training & Held-Out Evaluation
    run_step("python -m src.models.evaluate_comprehensive", "Authoritative Multi-Slice Model Training & Evaluation")

    # 8. Operational Anomaly Detection & Ground-Truth Benchmarking
    run_step("python -m src.anomaly.evaluator", "Operational Anomaly Detection & Ground-Truth Benchmarking")

    # 9. Delay Intelligence & Root Cause Explanations
    run_step("python -m src.intelligence.delay_explainer", "Root Cause Delay Explanation Intelligence Engine")

    # 10. Operational Exception Engine & Actionable Recommendations
    run_step("python -m src.exceptions.engine", "Operational Exception Engine & Actionable Recommendations")

    # 11. Complete Data & Standalone SQL Export
    run_step("python -m src.data.exporter", "Complete Analytical Data & Standalone SQL Reconstruction Export")

    # 12. Automated Test Suite Execution
    if not args.skip_tests:
        run_step("python -m pytest tests/ -v", "Complete Automated Unit & Integration Test Suite")

    print("\n" + "=" * 75)
    print("ALL MASTER PIPELINE STEPS COMPLETED SUCCESSFULLY!")
    print("To launch the FastAPI backend:")
    print("   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload")
    print("To launch the Streamlit dashboard:")
    print("   streamlit run frontend/streamlit_app.py")
    print("=" * 75)


if __name__ == "__main__":
    main()
