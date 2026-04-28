import time
import numpy as np
from typing import Optional

from backend.app.optimizers.base import BaseOptimizer, Route
from backend.app.optimizers.alns import ALNSOperators
from backend.app.services.data_loader import DataLoader
from backend.app.schemas.models import OptimizeRequest


class PureALNSOptimizer(BaseOptimizer):
    """Pure ALNS: Constructs an initial random solution, then ALNS improves it."""

    def __init__(
        self,
        data: DataLoader,
        request: OptimizeRequest,
        alns_iterations: int = 150,
        n_remove: int = 2,
        seed: Optional[int] = None,
        verbose: bool = True,
    ):
        super().__init__(data, request)
        self.alns_iterations = alns_iterations
        self.n_remove = n_remove
        self.rng = np.random.default_rng(seed)
        self.verbose = verbose
        self.alns = ALNSOperators(data, request, self.rng)

    def _alns_improve(self, route: Route) -> Route:
        """Apply ALNS destroy/repair iterations to improve the route."""
        best = route.copy()
        best_fitness = self.evaluator.fitness(best)
        current = route.copy()
        current_fitness = best_fitness

        improved_count = 0

        for it in range(self.alns_iterations):
            # Select destroy operator
            destroy_choice = self.rng.integers(0, 3)
            if destroy_choice == 0:
                destroyed, removed = self.alns.random_removal(current, self.n_remove)
            elif destroy_choice == 1:
                destroyed, removed = self.alns.worst_removal(current, self.evaluator, self.n_remove)
            else:
                destroyed, removed = self.alns.shaw_removal(current, self.n_remove)

            if not removed:
                continue

            # Select repair operator
            repair_choice = self.rng.integers(0, 3)
            if repair_choice == 0:
                repaired = self.alns.greedy_insert(destroyed, removed, self.evaluator)
            elif repair_choice == 1:
                repaired = self.alns.random_insert(destroyed, removed)
            else:
                repaired = self.alns.regret_insert(destroyed, removed, self.evaluator)

            new_fitness = self.evaluator.fitness(repaired)

            # Accept only improvements (greedy)
            if new_fitness < current_fitness:
                current = repaired
                current_fitness = new_fitness
                if new_fitness < best_fitness:
                    best = repaired.copy()
                    best_fitness = new_fitness
                    improved_count += 1

            if self.verbose and (it + 1) % 20 == 0:
                ev = self.evaluator.evaluate_route(best)
                print(
                    f"[ALNS] iter={it+1:>4}/{self.alns_iterations}"
                    f"  best_fit={best_fitness:.4f}"
                    f"  cur_fit={current_fitness:.4f}"
                    f"  dist={ev['total_distance_km']:.2f}km"
                    f"  time={ev['total_time_min']:.1f}min"
                    f"  co2={ev['total_co2_kg']:.3f}kg"
                    f"  improvements={improved_count}"
                )

        return best

    def optimize(self) -> Route:
        start_time = time.time()

        print(f"\n{'='*60}")
        print(f"[ALNS] START  Random construction + ALNS improvement")
        print(f"[ALNS] alns_iterations={self.alns_iterations}  n_remove={self.n_remove}")
        print(f"{'='*60}")

        # Phase 1: Construct initial solution randomly
        initial_route = self._generate_random_route(self.rng)
        initial_fitness = self.evaluator.fitness(initial_route)

        if self.verbose:
            ev = self.evaluator.evaluate_route(initial_route)
            print(
                f"[ALNS] Random initial: fitness={initial_fitness:.4f}"
                f"  dist={ev['total_distance_km']:.2f}km"
                f"  time={ev['total_time_min']:.1f}min"
                f"  co2={ev['total_co2_kg']:.3f}kg"
            )
            print(f"[ALNS] Starting ALNS improvement ({self.alns_iterations} iterations)...")

        # Phase 2: Improve with ALNS
        improved_route = self._alns_improve(initial_route)
        self.best_route = improved_route
        self.best_fitness = self.evaluator.fitness(improved_route)
        self.computation_time = time.time() - start_time

        ev = self.evaluator.evaluate_route(self.best_route)
        improvement = ((initial_fitness - self.best_fitness) / initial_fitness * 100) if initial_fitness > 0 else 0

        print(
            f"[ALNS] DONE  fitness={self.best_fitness:.4f}"
            f"  improvement={improvement:.1f}%"
            f"  dist={ev['total_distance_km']:.2f}km"
            f"  time={ev['total_time_min']:.1f}min"
            f"  co2={ev['total_co2_kg']:.3f}kg"
            f"  elapsed={self.computation_time:.3f}s\n"
        )

        return self.best_route