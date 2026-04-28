import time
import math
import numpy as np
from typing import Optional

from backend.app.optimizers.base import BaseOptimizer, Route
from backend.app.services.data_loader import DataLoader
from backend.app.schemas.models import OptimizeRequest, PlaceType


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
        num_days = new_route.num_days
        move_type = self.rng.integers(0, 5)

        if move_type == 0:
            # Swap two places within a random day
            day = int(self.rng.integers(0, num_days))
            places = new_route.day_places[day]
            if len(places) >= 2:
                i, j = self.rng.choice(len(places), size=2, replace=False)
                places[i], places[j] = places[j], places[i]

        elif move_type == 1:
            # Reverse a segment within a random day
            day = int(self.rng.integers(0, num_days))
            places = new_route.day_places[day]
            if len(places) >= 2:
                i, j = sorted(self.rng.choice(len(places), size=2, replace=False))
                places[i:j + 1] = reversed(places[i:j + 1])

        elif move_type == 2:
            # Swap places between two different days
            if num_days >= 2:
                d1, d2 = self.rng.choice(num_days, size=2, replace=False)
                if new_route.day_places[d1] and new_route.day_places[d2]:
                    i1 = int(self.rng.integers(0, len(new_route.day_places[d1])))
                    pid1 = new_route.day_places[d1][i1]
                    p1_type = next(p.type for p in self.data.places if p.id == pid1)
                    
                    valid_i2s = []
                    for i2, pid2 in enumerate(new_route.day_places[d2]):
                        p2_type = next(p.type for p in self.data.places if p.id == pid2)
                        if p1_type in (PlaceType.FOOD, PlaceType.OTOP):
                            if p2_type == p1_type:
                                valid_i2s.append(i2)
                        else:
                            if p2_type not in (PlaceType.FOOD, PlaceType.OTOP):
                                valid_i2s.append(i2)
                    
                    if valid_i2s:
                        i2 = int(self.rng.choice(valid_i2s))
                        new_route.day_places[d1][i1], new_route.day_places[d2][i2] = (
                            new_route.day_places[d2][i2],
                            new_route.day_places[d1][i1],
                        )

        elif move_type == 3:
            # Replace a place with an unused candidate
            day = int(self.rng.integers(0, num_days))
            places = new_route.day_places[day]
            all_used = set(pid for d in new_route.day_places for pid in d)
            if places:
                idx = int(self.rng.integers(0, len(places)))
                pid = places[idx]
                p_type = next(p.type for p in self.data.places if p.id == pid)
                
                if p_type in (PlaceType.FOOD, PlaceType.OTOP):
                    candidates = [p for p in self._get_candidate_places() if p.id not in all_used and p.type == p_type]
                else:
                    candidates = [p for p in self._get_candidate_places() if p.id not in all_used and p.type not in (PlaceType.FOOD, PlaceType.OTOP)]
                
                if candidates:
                    new_place = candidates[self.rng.integers(0, len(candidates))]
                    places[idx] = new_place.id

        elif move_type == 4:
            # Change a random hotel
            hotels = self.data.get_hotels()
            if hotels and new_route.hotel_ids:
                h_idx = int(self.rng.integers(0, len(new_route.hotel_ids)))
                new_route.hotel_ids[h_idx] = hotels[self.rng.integers(0, len(hotels))].id

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
