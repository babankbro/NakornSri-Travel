"""
Benchmark Test Suite for Travel Route Optimization Algorithms

Runs SM, GA, SA, SM+ALNS, GA+ALNS, SA+ALNS across 9 test cases:
- Small (1-day): 3 subsets with ~8-10 places
- Large (2-day): 3 subsets with ~25-35 places
- Real  (1-3 day): 3 subsets with all 44 places

Each algorithm × test case is run N_ROUNDS times.
Output reports mean ± std for time, fitness, and distance.

Output: Console table + benchmark_results.csv
"""

import time
import csv
import sys
import os
import numpy as np

# Resolve project root (directory that contains the 'backend' folder)
def _find_project_root() -> str:
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        if os.path.isdir(os.path.join(d, "backend")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return os.path.dirname(os.path.abspath(__file__))

PROJECT_ROOT = _find_project_root()
sys.path.insert(0, PROJECT_ROOT)

from backend.app.services.data_loader import DataLoader
from backend.app.schemas.models import OptimizeRequest, AlgorithmType, LifestyleType
from backend.app.optimizers.sm import SMOptimizer
from backend.app.optimizers.ga import GAOptimizer
from backend.app.optimizers.sa import SAOptimizer
from backend.app.optimizers.sm_alns import SMAlnsOptimizer
from backend.app.optimizers.ga_alns import GAAlnsOptimizer
from backend.app.optimizers.sa_alns import SAAlnsOptimizer
from backend.app.optimizers.pure_alns import PureALNSOptimizer
from backend.app.optimizers.moma import MOMAOptimizer 



# ============================================================
# Configuration
# ============================================================

N_ROUNDS = 10  # Number of repeated runs per algorithm × test case

# ============================================================
# Test case definitions
# ============================================================

# Place IDs from TravelInfo_v2.csv (63 total):
# D1 (Depot), H1-H18 (Hotels), T1-T21 (Travel/Culture), P1-P4 (OTOP), R1-R19 (Food)

SMALL1_IDS = {"D1", "H1", "H2", "P1", "P2", "T1", "T2", "T3", "R1", "R2"}
SMALL2_IDS = {"D1", "H1", "H2", "P1", "P2", "T1", "T2", "T3", "T7", "T8", "R3", "R4"}
SMALL3_IDS = {"D1", "H3", "H5", "H8", "P3", "P4", "T10", "T11", "T14", "T15", "R5", "R6"}

LARGE1_IDS = {"D1"} | {f"H{i}" for i in range(1, 7)} | {f"P{i}" for i in range(1, 5)} | {f"T{i}" for i in range(1, 15)} | {f"R{i}" for i in range(1, 6)}
LARGE2_IDS = {"D1"} | {f"H{i}" for i in range(1, 9)} | {f"P{i}" for i in range(1, 5)} | {f"T{i}" for i in range(1, 18)} | {f"R{i}" for i in range(1, 8)}
LARGE3_IDS = {"D1"} | {f"H{i}" for i in range(1, 11)} | {f"P{i}" for i in range(1, 5)} | {f"T{i}" for i in range(1, 21)} | {f"R{i}" for i in range(1, 12)}

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
    "SA":      {"class": SAOptimizer,     "kwargs": {"verbose": False}},
    "ALNS":    {"class": PureALNSOptimizer, "kwargs": {"alns_iterations": 50, "verbose": False}},
    "SM+ALNS": {"class": SMAlnsOptimizer, "kwargs": {"alns_iterations": 50, "verbose": False}},
    "GA+ALNS": {"class": GAAlnsOptimizer, "kwargs": {"population_size": 50, "generations": 100, "alns_iterations": 20, "verbose": False}},
    "SA+ALNS": {"class": SAAlnsOptimizer, "kwargs": {"verbose": False}},
   # "MOMA":    {"class": MOMAOptimizer,   "kwargs": {"population_size": 30, "generations": 30, "alns_iterations": 2, "verbose": False}},
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
    """Run a single algorithm once and return results."""
    cfg = ALGORITHMS[algo_name]
    OptimizerClass = cfg["class"]
    kwargs = cfg["kwargs"].copy()

    try:
        optimizer = OptimizerClass(loader, request, **kwargs)
        route = optimizer.optimize()
        evaluation = optimizer.evaluator.evaluate_route(route)
        fitness = optimizer.evaluator.fitness(route)
        violations = optimizer.evaluator.check_constraints(route)

        place_map = {p.id: p for p in loader.places}
        all_place_ids = [pid for day in route.day_places for pid in day]
        ratings = [place_map[pid].rate for pid in all_place_ids if pid in place_map]
        avg_rating = float(np.mean(ratings)) if ratings else 0.0

        return {
            "success": True,
            "time_sec": optimizer.computation_time,
            "fitness": fitness,
            "distance_km": evaluation["total_distance_km"],
            "time_min": evaluation["total_time_min"],
            "co2_kg": evaluation["total_co2_kg"],
            "avg_rating": avg_rating,
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
            "avg_rating": 0.0,
            "feasible": False,
            "violations": [str(e)],
        }


def run_repeated(loader: DataLoader, request: OptimizeRequest, algo_name: str, n_rounds: int) -> dict:
    """Run algorithm n_rounds times and return aggregated stats (mean ± std) + raw per-round data."""
    times, fitnesses, distances, times_min, co2s, ratings = [], [], [], [], [], []
    success_count = 0
    feasible_count = 0
    all_violations = []
    raw_rounds = []  # store each round's full result

    print(f"")
    for i in range(n_rounds):
        print(f"    Round {i+1:>2}/{n_rounds} ", end="", flush=True)
        r = run_single(loader, request, algo_name)
        raw_rounds.append({"round": i + 1, **r})
        if r["success"]:
            success_count += 1
            times.append(r["time_sec"])
            fitnesses.append(r["fitness"])
            distances.append(r["distance_km"])
            times_min.append(r["time_min"])
            co2s.append(r["co2_kg"])
            ratings.append(r["avg_rating"])
            status = "✓" if r["feasible"] and not r["violations"] else "⚠"
            if r["feasible"]:
                feasible_count += 1
            if r["violations"]:
                all_violations.extend(r["violations"])
            print(
                f"{status}  "
                f"time={r['time_sec']:7.3f}s  "
                f"fit={r['fitness']:8.4f}  "
                f"dist={r['distance_km']:7.2f}km  "
                f"time={r['time_min']:6.1f}min  "
                f"co2={r['co2_kg']:6.3f}kg  "
                f"rating={r['avg_rating']:5.2f}"
            )
            if r["violations"]:
                for v in r["violations"]:
                    print(f"           ⚠ {v}")
        else:
            print(f"✗  FAILED: {r['violations']}")

    if not times:
        return {
            "success": False,
            "n_rounds": n_rounds,
            "success_count": 0,
            "time_mean": 0, "time_std": 0,
            "fitness_mean": float("inf"), "fitness_std": 0,
            "distance_mean": 0, "distance_std": 0,
            "time_min_mean": 0, "time_min_std": 0,
            "co2_mean": 0, "co2_std": 0,
            "rating_mean": 0, "rating_std": 0,
            "feasible_count": 0,
            "violations": all_violations,
            "raw_rounds": raw_rounds,
        }

    return {
        "success": True,
        "n_rounds": n_rounds,
        "success_count": success_count,
        "time_mean":     float(np.mean(times)),
        "time_std":      float(np.std(times)),
        "fitness_mean":  float(np.mean(fitnesses)),
        "fitness_std":   float(np.std(fitnesses)),
        "distance_mean": float(np.mean(distances)),
        "distance_std":  float(np.std(distances)),
        "time_min_mean": float(np.mean(times_min)),
        "time_min_std":  float(np.std(times_min)),
        "co2_mean":      float(np.mean(co2s)),
        "co2_std":       float(np.std(co2s)),
        "rating_mean":   float(np.mean(ratings)),
        "rating_std":    float(np.std(ratings)),
        "feasible_count": feasible_count,
        "violations": list(set(all_violations)),
        "raw_rounds": raw_rounds,
    }


def fmt_mean_std(mean: float, std: float, decimals: int = 3) -> str:
    """Format a mean±std string."""
    fmt = f".{decimals}f"
    return f"{mean:{fmt}}±{std:{fmt}}"


def main():
    print("=" * 100)
    print("  BENCHMARK: Travel Route Optimization Algorithms")
    print("=" * 100)
    print(f"  Test cases : {len(TEST_CASES)}")
    print(f"  Algorithms : {', '.join(ALGO_NAMES)}")
    print(f"  Rounds     : {N_ROUNDS} (reporting mean ± std)")
    print("=" * 100)
    print()

    # Results storage: results[case_name][algo_name] = aggregated stats dict
    results = {}
    csv_rows = []
    raw_rows = []

    for case_idx, (case_name, place_ids, trip_days, lifestyle, desc) in enumerate(TEST_CASES):
        print(f"\n{'─'*90}")
        print(f"  Case {case_idx+1}/{len(TEST_CASES)}: {case_name} — {desc}")
        print(f"  trip_days={trip_days}, lifestyle={lifestyle}")

        loader = create_subset_loader(place_ids)
        n_places = len(loader.places)
        n_tourist = len(loader.get_tourist_places())
        n_hotels = len(loader.get_hotels())
        n_otop = len(loader.get_otop_places())
        print(f"  Places: {n_places} total ({n_tourist} tourist, {n_hotels} hotels, {n_otop} OTOP)")
        print(f"{'─'*90}")

        request = OptimizeRequest(
            trip_days=trip_days,
            algorithm=AlgorithmType.SM,  # will be overridden
            lifestyle_type=LifestyleType(lifestyle),
            weight_distance=0.4,
            weight_co2=0.3,
            weight_rating=0.3,
            min_places_per_day=3,
            max_places_per_day=7,
        )

        results[case_name] = {}

        for algo_name in ALGO_NAMES:
            print(f"\n  [{algo_name}] running {N_ROUNDS} rounds...")
            agg = run_repeated(loader, request, algo_name, N_ROUNDS)
            results[case_name][algo_name] = agg

            if agg["success"]:
                feasible_ratio = f"{agg['feasible_count']}/{agg['success_count']}"
                print(
                    f"    {'─'*70}\n"
                    f"    SUMMARY [{algo_name}]  feasible={feasible_ratio}\n"
                    f"      time    = {fmt_mean_std(agg['time_mean'],     agg['time_std'])}s\n"
                    f"      fitness = {fmt_mean_std(agg['fitness_mean'],  agg['fitness_std'], 4)}\n"
                    f"      dist    = {fmt_mean_std(agg['distance_mean'], agg['distance_std'], 2)}km\n"
                    f"      travel  = {fmt_mean_std(agg['time_min_mean'], agg['time_min_std'], 1)}min\n"
                    f"      co2     = {fmt_mean_std(agg['co2_mean'],      agg['co2_std'], 3)}kg\n"
                    f"      rating  = {fmt_mean_std(agg['rating_mean'],   agg['rating_std'], 2)}"
                )
                if agg["violations"]:
                    for v in agg["violations"]:
                        print(f"    ⚠ {v}")
            else:
                print(f"    ✗ ALL FAILED")

            csv_rows.append({
                "case": case_name,
                "description": desc,
                "trip_days": trip_days,
                "lifestyle": lifestyle,
                "n_places": n_places,
                "algorithm": algo_name,
                "n_rounds": N_ROUNDS,
                "success_count": agg["success_count"],
                "feasible_count": agg["feasible_count"],
                "time_mean":     round(agg["time_mean"], 4),
                "time_std":      round(agg["time_std"], 4),
                "fitness_mean":  round(agg["fitness_mean"], 4) if agg["fitness_mean"] < float("inf") else "INF",
                "fitness_std":   round(agg["fitness_std"], 4),
                "distance_mean": round(agg["distance_mean"], 2),
                "distance_std":  round(agg["distance_std"], 2),
                "time_min_mean": round(agg["time_min_mean"], 1),
                "time_min_std":  round(agg["time_min_std"], 1),
                "co2_mean":      round(agg["co2_mean"], 3),
                "co2_std":       round(agg["co2_std"], 3),
                "rating_mean":   round(agg["rating_mean"], 3),
                "rating_std":    round(agg["rating_std"], 3),
                "violations": "; ".join(agg["violations"]) if agg["violations"] else "",
            })

            for rr in agg["raw_rounds"]:
                raw_rows.append({
                    "case": case_name,
                    "description": desc,
                    "trip_days": trip_days,
                    "lifestyle": lifestyle,
                    "n_places": n_places,
                    "algorithm": algo_name,
                    "round": rr["round"],
                    "success": rr["success"],
                    "time_sec":    round(rr["time_sec"], 4),
                    "fitness":     round(rr["fitness"], 4) if rr["fitness"] < float("inf") else "INF",
                    "distance_km": round(rr["distance_km"], 2),
                    "time_min":    round(rr["time_min"], 1),
                    "co2_kg":      round(rr["co2_kg"], 3),
                    "avg_rating":  round(rr["avg_rating"], 3),
                    "feasible":    rr["feasible"],
                    "violations":  "; ".join(rr["violations"]) if rr["violations"] else "",
                })

    # ============================================================
    # Print summary tables  (mean ± std)
    # ============================================================
    col_w = 18   # wide enough for "12.345±0.012"
    case_w = 8

    def print_table(title: str, unit: str, value_key: str, is_lower_better: bool = True):
        print()
        print("=" * (case_w + (col_w + 3) * len(ALGO_NAMES)))
        print(f"  {title} ({unit})  —  mean ± std  [{N_ROUNDS} rounds]")
        print("=" * (case_w + (col_w + 3) * len(ALGO_NAMES)))
        header = f"{'Case':<{case_w}}"
        for algo in ALGO_NAMES:
            header += f" | {algo:^{col_w}}"
        print(header)
        print("-" * len(header))
        
        for case_name, *_ in TEST_CASES:
            row = f"{case_name:<{case_w}}"
            
            # Find the best value for this case across all algorithms
            best_val = float("inf") if is_lower_better else -float("inf")
            for algo in ALGO_NAMES:
                agg = results[case_name][algo]
                if agg["success"] and agg[f"{value_key}_mean"] != float("inf"):
                    val = agg[f"{value_key}_mean"]
                    if (is_lower_better and val < best_val) or (not is_lower_better and val > best_val):
                        best_val = val
            
            for algo in ALGO_NAMES:
                agg = results[case_name][algo]
                if not agg["success"] or agg[f"{value_key}_mean"] == float("inf"):
                    cell = "FAIL"
                else:
                    mean_val = agg[f"{value_key}_mean"]
                    std_val = agg[f"{value_key}_std"]
                    # Use decimals based on key
                    decimals = 4 if value_key == "fitness" else (2 if value_key in ("distance", "rating") else (3 if value_key == "co2" else 1))
                    cell = fmt_mean_std(mean_val, std_val, decimals)
                    
                    # Mark best with a star
                    if mean_val == best_val:
                        cell = f"★ {cell}"
                        
                row += f" | {cell:^{col_w}}"
            print(row)

    print_table("COMPUTATION TIME", "seconds", "time", True)
    print_table("FITNESS", "lower is better", "fitness", True)
    print_table("DISTANCE", "km", "distance", True)
    print_table("TRAVEL TIME", "minutes", "time_min", True)
    print_table("CO2 EMISSIONS", "kg", "co2", True)
    print_table("AVG PLACE RATING", "higher is better", "rating", False)

    # ============================================================
    # Save CSV — summary (mean ± std)
    # ============================================================
    out_dir = PROJECT_ROOT

    csv_path = os.path.join(out_dir, f"benchmark_resultsx{N_ROUNDS}.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "case", "description", "trip_days", "lifestyle", "n_places",
            "algorithm", "n_rounds", "success_count", "feasible_count",
            "time_mean", "time_std",
            "fitness_mean", "fitness_std",
            "distance_mean", "distance_std",
            "time_min_mean", "time_min_std",
            "co2_mean", "co2_std",
            "rating_mean", "rating_std",
            "violations",
        ])
        writer.writeheader()
        writer.writerows(csv_rows)

    # Save CSV — all 10 raw rounds
    raw_path = os.path.join(out_dir, "benchmark_raw.csv")
    with open(raw_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "case", "description", "trip_days", "lifestyle", "n_places",
            "algorithm", "round", "success",
            "time_sec", "fitness", "distance_km", "time_min",
            "co2_kg", "avg_rating", "feasible", "violations",
        ])
        writer.writeheader()
        writer.writerows(raw_rows)

    sep = "=" * (case_w + (col_w + 3) * len(ALGO_NAMES))
    print(f"\n  Summary  saved to: {csv_path}")
    print(f"  Raw data saved to: {raw_path}")
    print(sep)


if __name__ == "__main__":
    main()
