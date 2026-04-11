import time
import math
import numpy as np
from typing import Optional, List, Callable, Tuple

from backend.app.optimizers.base import BaseOptimizer, Route
from backend.app.optimizers.alns import ALNSOperators
from backend.app.services.data_loader import DataLoader
from backend.app.schemas.models import OptimizeRequest


class SAAlnsOptimizer(BaseOptimizer):
    def __init__(
        self,
        data: DataLoader,
        request: OptimizeRequest,
        initial_temp: float = 50.0,
        cooling_rate: float = 0.99,
        min_temp: float = 0.1,
        iterations_per_temp: int = 15,
        n_remove: int = 2,
        seed: Optional[int] = None,
        verbose: bool = True,
    ):
        super().__init__(data, request)
        self.verbose = verbose
        self.initial_temp = initial_temp
        self.cooling_rate = cooling_rate
        self.min_temp = min_temp
        self.iterations_per_temp = iterations_per_temp
        self.n_remove = n_remove
        self.rng = np.random.default_rng(seed)
        self.alns = ALNSOperators(data, request, self.rng)

        self.destroy_ops: List[Callable] = [
            self._destroy_random,
            self._destroy_worst,
            self._destroy_shaw,
        ]
        self.repair_ops: List[Callable] = [
            self._repair_greedy,
            self._repair_random,
            self._repair_regret,
        ]
        self.destroy_weights = np.ones(len(self.destroy_ops))
        self.repair_weights = np.ones(len(self.repair_ops))
        self.destroy_counts = np.zeros(len(self.destroy_ops))
        self.repair_counts = np.zeros(len(self.repair_ops))
        self.destroy_scores = np.zeros(len(self.destroy_ops))
        self.repair_scores = np.zeros(len(self.repair_ops))

    def _destroy_random(self, route: Route) -> Tuple[Route, List[str]]:
        return self.alns.random_removal(route, self.n_remove)

    def _destroy_worst(self, route: Route) -> Tuple[Route, List[str]]:
        return self.alns.worst_removal(route, self.evaluator, self.n_remove)

    def _destroy_shaw(self, route: Route) -> Tuple[Route, List[str]]:
        return self.alns.shaw_removal(route, self.n_remove)

    def _repair_greedy(self, route: Route, removed: List[str]) -> Route:
        return self.alns.greedy_insert(route, removed, self.evaluator)

    def _repair_random(self, route: Route, removed: List[str]) -> Route:
        return self.alns.random_insert(route, removed)

    def _repair_regret(self, route: Route, removed: List[str]) -> Route:
        return self.alns.regret_insert(route, removed, self.evaluator)

    def _select_op(self, weights: np.ndarray) -> int:
        probs = weights / weights.sum()
        return int(self.rng.choice(len(weights), p=probs))

    def _update_weights(self, decay: float = 0.8, reward_best: float = 3.0, reward_better: float = 2.0, reward_accept: float = 1.0):
        for i in range(len(self.destroy_weights)):
            if self.destroy_counts[i] > 0:
                self.destroy_weights[i] = (
                    decay * self.destroy_weights[i]
                    + (1 - decay) * self.destroy_scores[i] / self.destroy_counts[i]
                )
            self.destroy_weights[i] = max(self.destroy_weights[i], 0.1)

        for i in range(len(self.repair_weights)):
            if self.repair_counts[i] > 0:
                self.repair_weights[i] = (
                    decay * self.repair_weights[i]
                    + (1 - decay) * self.repair_scores[i] / self.repair_counts[i]
                )
            self.repair_weights[i] = max(self.repair_weights[i], 0.1)

        self.destroy_scores[:] = 0
        self.repair_scores[:] = 0
        self.destroy_counts[:] = 0
        self.repair_counts[:] = 0

    def optimize(self) -> Route:
        start_time = time.time()

        current = self._generate_random_route(self.rng)
        current_fitness = self.evaluator.fitness(current)
        self.best_route = current.copy()
        self.best_fitness = current_fitness

        temp = self.initial_temp
        segment_iter = 0
        total_iters = 0
        accepted = 0
        temp_step = 0

        print(f"\n{'='*60}")
        print(f"[SA+ALNS] START  T0={self.initial_temp}  cool={self.cooling_rate}  Tmin={self.min_temp}")
        print(f"[SA+ALNS] iter_per_temp={self.iterations_per_temp}  n_remove={self.n_remove}")
        print(f"{'='*60}")

        while temp > self.min_temp:
            for _ in range(self.iterations_per_temp):
                d_idx = self._select_op(self.destroy_weights)
                r_idx = self._select_op(self.repair_weights)

                destroyed, removed = self.destroy_ops[d_idx](current)
                if not removed:
                    continue
                neighbor = self.repair_ops[r_idx](destroyed, removed)
                neighbor_fitness = self.evaluator.fitness(neighbor)

                self.destroy_counts[d_idx] += 1
                self.repair_counts[r_idx] += 1

                delta = neighbor_fitness - current_fitness
                accept = False

                if delta < 0:
                    accept = True
                    if neighbor_fitness < self.best_fitness:
                        self.destroy_scores[d_idx] += 3
                        self.repair_scores[r_idx] += 3
                    else:
                        self.destroy_scores[d_idx] += 2
                        self.repair_scores[r_idx] += 2
                else:
                    acceptance_prob = math.exp(-delta / temp) if temp > 0 else 0
                    if self.rng.random() < acceptance_prob:
                        accept = True
                        self.destroy_scores[d_idx] += 1
                        self.repair_scores[r_idx] += 1

                if accept:
                    current = neighbor
                    current_fitness = neighbor_fitness
                    accepted += 1
                    if current_fitness < self.best_fitness:
                        self.best_fitness = current_fitness
                        self.best_route = current.copy()

                segment_iter += 1
                total_iters += 1
                if segment_iter % 100 == 0:
                    self._update_weights()

            temp_step += 1
            if self.verbose:
                ev = self.evaluator.evaluate_route(self.best_route)
                accept_rate = accepted / total_iters if total_iters > 0 else 0
                dw = self.destroy_weights / self.destroy_weights.sum()
                rw = self.repair_weights / self.repair_weights.sum()
                print(
                    f"[SA+ALNS] step={temp_step:>4}"
                    f"  T={temp:>7.4f}"
                    f"  iter={total_iters:>5}"
                    f"  best_fit={self.best_fitness:.4f}"
                    f"  cur_fit={current_fitness:.4f}"
                    f"  accept%={accept_rate*100:.1f}"
                    f"  dist={ev['total_distance_km']:.2f}km"
                    f"  co2={ev['total_co2_kg']:.3f}kg"
                    f"  D-w=[{dw[0]:.2f},{dw[1]:.2f},{dw[2]:.2f}]"
                    f"  R-w=[{rw[0]:.2f},{rw[1]:.2f},{rw[2]:.2f}]"
                )
            temp *= self.cooling_rate

        print(f"[SA+ALNS] DONE  best_fit={self.best_fitness:.4f}  total_iter={total_iters}  time={time.time()-start_time:.2f}s\n")
        self.computation_time = time.time() - start_time
        return self.best_route
