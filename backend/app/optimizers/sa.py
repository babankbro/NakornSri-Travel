import time
import math
import numpy as np
from typing import Optional

from backend.app.optimizers.base import BaseOptimizer, Route
from backend.app.services.data_loader import DataLoader
from backend.app.schemas.models import OptimizeRequest


class SAOptimizer(BaseOptimizer):
    def __init__(
        self,
        data: DataLoader,
        request: OptimizeRequest,
        initial_temp: float = 100.0,
        cooling_rate: float = 0.995,
        min_temp: float = 0.01,
        iterations_per_temp: int = 50,
        seed: Optional[int] = None,
        verbose: bool = True,
    ):
        super().__init__(data, request)
        self.initial_temp = initial_temp
        self.cooling_rate = cooling_rate
        self.min_temp = min_temp
        self.iterations_per_temp = iterations_per_temp
        self.rng = np.random.default_rng(seed)
        self.verbose = verbose

    def _neighbor(self, route: Route) -> Route:
        new_route = route.copy()
        move_type = self.rng.integers(0, 5)

        if move_type == 0:
            day = self.rng.integers(0, 2)
            places = new_route.day1_places if day == 0 else new_route.day2_places
            if len(places) >= 2:
                i, j = self.rng.choice(len(places), size=2, replace=False)
                places[i], places[j] = places[j], places[i]

        elif move_type == 1:
            day = self.rng.integers(0, 2)
            places = new_route.day1_places if day == 0 else new_route.day2_places
            if len(places) >= 2:
                i, j = sorted(self.rng.choice(len(places), size=2, replace=False))
                places[i:j + 1] = reversed(places[i:j + 1])

        elif move_type == 2:
            if new_route.day1_places and new_route.day2_places:
                i1 = self.rng.integers(0, len(new_route.day1_places))
                i2 = self.rng.integers(0, len(new_route.day2_places))
                new_route.day1_places[i1], new_route.day2_places[i2] = (
                    new_route.day2_places[i2],
                    new_route.day1_places[i1],
                )

        elif move_type == 3:
            day = self.rng.integers(0, 2)
            places = new_route.day1_places if day == 0 else new_route.day2_places
            other = new_route.day2_places if day == 0 else new_route.day1_places
            used_ids = set(places + other)
            candidates = [p for p in self._get_candidate_places() if p.id not in used_ids]
            if places and candidates:
                idx = self.rng.integers(0, len(places))
                new_place = candidates[self.rng.integers(0, len(candidates))]
                places[idx] = new_place.id

        elif move_type == 4:
            hotels = self.data.get_hotels()
            if hotels:
                new_route.hotel_id = hotels[self.rng.integers(0, len(hotels))].id

        return new_route

    def optimize(self) -> Route:
        start_time = time.time()

        current = self._generate_random_route(self.rng)
        current_fitness = self.evaluator.fitness(current)
        self.best_route = current.copy()
        self.best_fitness = current_fitness

        temp = self.initial_temp
        iteration = 0
        accepted = 0
        total_iters = 0

        print(f"\n{'='*60}")
        print(f"[SA] START  T0={self.initial_temp}  cool={self.cooling_rate}  Tmin={self.min_temp}")
        print(f"[SA] iter_per_temp={self.iterations_per_temp}")
        print(f"{'='*60}")

        while temp > self.min_temp:
            for _ in range(self.iterations_per_temp):
                neighbor = self._neighbor(current)
                neighbor_fitness = self.evaluator.fitness(neighbor)
                delta = neighbor_fitness - current_fitness
                total_iters += 1

                if delta < 0:
                    current = neighbor
                    current_fitness = neighbor_fitness
                    accepted += 1
                else:
                    acceptance_prob = math.exp(-delta / temp) if temp > 0 else 0
                    if self.rng.random() < acceptance_prob:
                        current = neighbor
                        current_fitness = neighbor_fitness
                        accepted += 1

                if current_fitness < self.best_fitness:
                    self.best_fitness = current_fitness
                    self.best_route = current.copy()

            if self.verbose:
                ev = self.evaluator.evaluate_route(self.best_route)
                accept_rate = accepted / total_iters if total_iters > 0 else 0
                print(
                    f"[SA] T={temp:>8.4f}"
                    f"  iter={total_iters:>5}"
                    f"  best_fit={self.best_fitness:.4f}"
                    f"  cur_fit={current_fitness:.4f}"
                    f"  accept%={accept_rate*100:.1f}"
                    f"  dist={ev['total_distance_km']:.2f}km"
                    f"  time={ev['total_time_min']:.1f}min"
                    f"  co2={ev['total_co2_kg']:.3f}kg"
                )
            iteration += 1
            temp *= self.cooling_rate

        print(f"[SA] DONE  best_fit={self.best_fitness:.4f}  total_iter={total_iters}  time={time.time()-start_time:.2f}s\n")
        self.computation_time = time.time() - start_time
        return self.best_route
