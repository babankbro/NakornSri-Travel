"""
Benchmark Test Suite for Travel Route Optimization Algorithms

Runs SM, GA, SM+ALNS, GA+ALNS across 9 test cases:
- Small (1-day): 3 subsets with ~8-10 places
- Large (2-day): 3 subsets with ~25-35 places
- Real  (1-3 day): 3 subsets with all 44 places

Output: Console table + benchmark_results.csv
"""

import time
import csv
import sys
import os
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app.services.data_loader import DataLoader
from backend.app.schemas.models import OptimizeRequest, AlgorithmType, LifestyleType
from backend.app.optimizers.sm import SMOptimizer
from backend.app.optimizers.ga import GAOptimizer
from backend.app.optimizers.sm_alns import SMAlnsOptimizer
from backend.app.optimizers.ga_alns import GAAlnsOptimizer


# ============================================================
# Test case definitions
# ============================================================

# Place IDs from TravelInfo.csv (44 total):
# D1 (Depot), H1-H18 (Hotels), T1-T21 (Travel/Culture), P1-P4 (OTOP)

SMALL1_IDS = {"D1", "H1", "H2", "P1", "P2", "T1", "T2", "T3"}
SMALL2_IDS = {"D1", "H1", "H2", "P1", "P2", "T1", "T2", "T3", "T7", "T8"}
SMALL3_IDS = {"D1", "H3", "H5", "P3", "P4", "T10", "T11", "T14", "T15", "H8"}

LARGE1_IDS = {"D1"} | {f"H{i}" for i in range(1, 7)} | {f"P{i}" for i in range(1, 5)} | {f"T{i}" for i in range(1, 15)}
LARGE2_IDS = {"D1"} | {f"H{i}" for i in range(1, 9)} | {f"P{i}" for i in range(1, 5)} | {f"T{i}" for i in range(1, 18)}
LARGE3_IDS = {"D1"} | {f"H{i}" for i in range(1, 11)} | {f"P{i}" for i in range(1, 5)} | {f"T{i}" for i in range(1, 21)}

# Real = all 44 places (no filter)
REAL_ALL = None  # None means use all places

TEST_CASES = [
    # (name, place_ids, trip_days, lifestyle, description)
    ("Small1", SMALL1_IDS, 1, "all",     "Minimal 1-day, 8 places"),
    ("Small2", SMALL2_IDS, 1, "all",     "Mixed types 1-day, 10 places"),
    ("Small3", SMALL3_IDS, 1, "all",     "Different subset 1-day, 10 places"),
    ("Large1", LARGE1_IDS, 2, "all",     "Medium 2-day, ~25 places"),
    ("Large2", LARGE2_IDS, 2, "all",     "Larger 2-day, ~30 places"),
    ("Large3", LARGE3_IDS, 2, "all",     "Near-full 2-day, ~35 places"),
    ("Real1",  REAL_ALL,   1, "all",     "Full data 1-day"),
    ("Real2",  REAL_ALL,   2, "all",     "Full data 2-day"),
    ("Real3",  REAL_ALL,   2, "culture", "Full data 2-day, culture lifestyle"),
]

# Algorithm configs (reduced params for benchmark speed)
ALGORITHMS = {
    "SM":      {"class": SMOptimizer,     "kwargs": {}},
    "GA":      {"class": GAOptimizer,     "kwargs": {"population_size": 50, "generations": 100, "verbose": False}},
    "SM+ALNS": {"class": SMAlnsOptimizer, "kwargs": {"alns_iterations": 50, "verbose": False}},
    "GA+ALNS": {"class": GAAlnsOptimizer, "kwargs": {"population_size": 30, "generations": 50, "alns_iterations": 10, "verbose": False}},
}

ALGO_NAMES = list(ALGORITHMS.keys())


def create_subset_loader(place_ids) -> DataLoader:
    """Create a DataLoader with only the specified place IDs."""
    loader = DataLoader()
    loader.load_places()

    if place_ids is not None:
        # Must always include depot
        place_ids = set(place_ids)
        loader.places = [p for p in loader.places if p.id in place_ids]
        loader.places_df = loader.places_df[
            loader.places_df["ID"].str.strip().isin(place_ids)
        ].reset_index(drop=True)
        loader.id_to_index = {p.id: i for i, p in enumerate(loader.places)}
        loader.index_to_id = {i: p.id for i, p in enumerate(loader.places)}
        loader._compute_matrices()

    return loader


def run_single(loader: DataLoader, request: OptimizeRequest, algo_name: str) -> dict:
    """Run a single algorithm and return results."""
    cfg = ALGORITHMS[algo_name]
    OptimizerClass = cfg["class"]
    kwargs = cfg["kwargs"].copy()

    try:
        optimizer = OptimizerClass(loader, request, **kwargs)
        route = optimizer.optimize()
        evaluation = optimizer.evaluator.evaluate_route(route)
        fitness = optimizer.evaluator.fitness(route)
        violations = optimizer.evaluator.check_constraints(route)

        return {
            "success": True,
            "time_sec": optimizer.computation_time,
            "fitness": fitness,
            "distance_km": evaluation["total_distance_km"],
            "time_min": evaluation["total_time_min"],
            "co2_kg": evaluation["total_co2_kg"],
            "feasible": evaluation["feasible"],
            "violations": violations,
        }
    except Exception as e:
        return {
            "success": False,
            "time_sec": 0,
            "fitness": float("inf"),
            "distance_km": 0,
            "time_min": 0,
            "co2_kg": 0,
            "feasible": False,
            "violations": [str(e)],
        }


def main():
    print("=" * 80)
    print("  BENCHMARK: Travel Route Optimization Algorithms")
    print("=" * 80)
    print(f"  Test cases: {len(TEST_CASES)}")
    print(f"  Algorithms: {', '.join(ALGO_NAMES)}")
    print("=" * 80)
    print()

    # Results storage: results[case_name][algo_name] = result_dict
    results = {}
    csv_rows = []

    for case_idx, (case_name, place_ids, trip_days, lifestyle, desc) in enumerate(TEST_CASES):
        print(f"\n{'─'*70}")
        print(f"  Case {case_idx+1}/{len(TEST_CASES)}: {case_name} — {desc}")
        print(f"  trip_days={trip_days}, lifestyle={lifestyle}")

        loader = create_subset_loader(place_ids)
        n_places = len(loader.places)
        n_tourist = len(loader.get_tourist_places())
        n_hotels = len(loader.get_hotels())
        n_otop = len(loader.get_otop_places())
        print(f"  Places: {n_places} total ({n_tourist} tourist, {n_hotels} hotels, {n_otop} OTOP)")
        print(f"{'─'*70}")

        request = OptimizeRequest(
            trip_days=trip_days,
            algorithm=AlgorithmType.SM,  # will be overridden
            lifestyle_type=LifestyleType(lifestyle),
            weight_distance=0.4,
            weight_time=0.3,
            weight_co2=0.3,
            max_places_per_day=6,
        )

        results[case_name] = {}

        for algo_name in ALGO_NAMES:
            print(f"\n  Running {algo_name}...", end=" ", flush=True)
            result = run_single(loader, request, algo_name)
            results[case_name][algo_name] = result

            if result["success"]:
                status = "✓" if result["feasible"] and not result["violations"] else "⚠"
                print(
                    f"{status} {result['time_sec']:.3f}s  "
                    f"fit={result['fitness']:.4f}  "
                    f"dist={result['distance_km']:.1f}km  "
                    f"co2={result['co2_kg']:.3f}kg"
                )
                if result["violations"]:
                    for v in result["violations"]:
                        print(f"    ⚠ {v}")
            else:
                print(f"✗ FAILED: {result['violations']}")

            csv_rows.append({
                "case": case_name,
                "description": desc,
                "trip_days": trip_days,
                "lifestyle": lifestyle,
                "n_places": n_places,
                "algorithm": algo_name,
                "time_sec": round(result["time_sec"], 4),
                "fitness": round(result["fitness"], 4) if result["fitness"] < float("inf") else "INF",
                "distance_km": round(result["distance_km"], 2),
                "time_min": round(result["time_min"], 1),
                "co2_kg": round(result["co2_kg"], 3),
                "feasible": result["feasible"],
                "violations": "; ".join(result["violations"]) if result["violations"] else "",
            })

    # ============================================================
    # Print summary table
    # ============================================================
    print("\n\n")
    print("=" * 80)
    print("  COMPUTATION TIME TABLE (seconds)")
    print("=" * 80)

    # Header
    col_w = 12
    case_w = 10
    header = f"{'Case':<{case_w}}"
    for algo in ALGO_NAMES:
        header += f" | {algo:>{col_w}}"
    print(header)
    print("-" * len(header))

    for case_name, _, _, _, _ in TEST_CASES:
        row = f"{case_name:<{case_w}}"
        for algo in ALGO_NAMES:
            r = results[case_name][algo]
            if r["success"]:
                row += f" | {r['time_sec']:>{col_w}.3f}"
            else:
                row += f" | {'FAIL':>{col_w}}"
        print(row)

    print()
    print("=" * 80)
    print("  FITNESS TABLE (lower is better)")
    print("=" * 80)

    print(header)
    print("-" * len(header))

    for case_name, _, _, _, _ in TEST_CASES:
        row = f"{case_name:<{case_w}}"
        for algo in ALGO_NAMES:
            r = results[case_name][algo]
            if r["success"] and r["fitness"] < float("inf"):
                row += f" | {r['fitness']:>{col_w}.4f}"
            else:
                row += f" | {'FAIL':>{col_w}}"
        print(row)

    print()
    print("=" * 80)
    print("  DISTANCE TABLE (km)")
    print("=" * 80)

    print(header)
    print("-" * len(header))

    for case_name, _, _, _, _ in TEST_CASES:
        row = f"{case_name:<{case_w}}"
        for algo in ALGO_NAMES:
            r = results[case_name][algo]
            if r["success"]:
                row += f" | {r['distance_km']:>{col_w}.2f}"
            else:
                row += f" | {'FAIL':>{col_w}}"
        print(row)

    # ============================================================
    # Save CSV
    # ============================================================
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark_results.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "case", "description", "trip_days", "lifestyle", "n_places",
            "algorithm", "time_sec", "fitness", "distance_km", "time_min",
            "co2_kg", "feasible", "violations",
        ])
        writer.writeheader()
        writer.writerows(csv_rows)

    print(f"\n  Results saved to: {csv_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
