import time
import numpy as np
from typing import List, Optional

from backend.app.optimizers.base import BaseOptimizer, Route, RouteEvaluator
from backend.app.services.data_loader import DataLoader
from backend.app.schemas.models import OptimizeRequest


class GAOptimizer(BaseOptimizer):
    def __init__(
        self,
        data: DataLoader,
        request: OptimizeRequest,
        population_size: int = 100,
        generations: int = 200,
        crossover_rate: float = 0.8,
        mutation_rate: float = 0.3,
        tournament_size: int = 5,
        elite_size: int = 5,
        seed: Optional[int] = None,
        verbose: bool = True,
    ):
        super().__init__(data, request)
        self.population_size = population_size
        self.generations = generations
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.tournament_size = tournament_size
        self.elite_size = elite_size
        self.rng = np.random.default_rng(seed)
        self.verbose = verbose

    def _init_population(self) -> List[Route]:
        population = []
        for _ in range(self.population_size):
            route = self._generate_random_route(self.rng)
            population.append(route)
        return population

    def _tournament_select(self, population: List[Route], fitnesses: List[float]) -> Route:
        indices = self.rng.choice(len(population), size=self.tournament_size, replace=False)
        best_idx = indices[0]
        for idx in indices[1:]:
            if fitnesses[idx] < fitnesses[best_idx]:
                best_idx = idx
        return population[best_idx].copy()

    def _order_crossover(self, parent1: List[str], parent2: List[str]) -> List[str]:
        if len(parent1) <= 2 or len(parent2) <= 2:
            return parent1.copy()

        size = len(parent1)
        start, end = sorted(self.rng.choice(size, size=2, replace=False))

        child = [None] * size
        child[start:end + 1] = parent1[start:end + 1]

        fill_values = [g for g in parent2 if g not in child[start:end + 1]]
        fill_idx = 0
        for i in range(size):
            if child[i] is None and fill_idx < len(fill_values):
                child[i] = fill_values[fill_idx]
                fill_idx += 1

        child = [x for x in child if x is not None]
        return child

    def _crossover(self, p1: Route, p2: Route) -> Route:
        if self.rng.random() > self.crossover_rate:
            return p1.copy()

        child_day1 = self._order_crossover(p1.day1_places, p2.day1_places)
        child_day2 = self._order_crossover(p1.day2_places, p2.day2_places)

        all_ids = set(child_day1 + child_day2)
        if len(all_ids) < len(child_day1) + len(child_day2):
            seen = set()
            new_day2 = []
            for pid in child_day2:
                if pid not in set(child_day1):
                    if pid not in seen:
                        new_day2.append(pid)
                        seen.add(pid)
                else:
                    candidates = self._get_candidate_places()
                    used = set(child_day1) | seen
                    replacements = [p.id for p in candidates if p.id not in used]
                    if replacements:
                        rep = replacements[self.rng.integers(0, len(replacements))]
                        new_day2.append(rep)
                        seen.add(rep)
            child_day2 = new_day2

        hotel = self.rng.choice([p1.hotel_id, p2.hotel_id])
        return Route(child_day1, child_day2, hotel)

    def _mutate(self, route: Route) -> Route:
        if self.rng.random() > self.mutation_rate:
            return route

        mutation_type = self.rng.integers(0, 4)

        if mutation_type == 0:
            day = self.rng.integers(0, 2)
            places = route.day1_places if day == 0 else route.day2_places
            if len(places) >= 2:
                i, j = self.rng.choice(len(places), size=2, replace=False)
                places[i], places[j] = places[j], places[i]

        elif mutation_type == 1:
            day = self.rng.integers(0, 2)
            places = route.day1_places if day == 0 else route.day2_places
            if len(places) >= 2:
                i, j = sorted(self.rng.choice(len(places), size=2, replace=False))
                places[i:j + 1] = reversed(places[i:j + 1])

        elif mutation_type == 2:
            if route.day1_places and route.day2_places:
                i1 = self.rng.integers(0, len(route.day1_places))
                i2 = self.rng.integers(0, len(route.day2_places))
                route.day1_places[i1], route.day2_places[i2] = (
                    route.day2_places[i2],
                    route.day1_places[i1],
                )

        elif mutation_type == 3:
            hotels = self.data.get_hotels()
            if hotels:
                route.hotel_id = hotels[self.rng.integers(0, len(hotels))].id

        return route

    def optimize(self) -> Route:
        start_time = time.time()

        population = self._init_population()
        fitnesses = [self.evaluator.fitness(r) for r in population]

        print(f"\n{'='*60}")
        print(f"[GA] START  pop={self.population_size}  gen={self.generations}")
        print(f"[GA] crossover={self.crossover_rate}  mutation={self.mutation_rate}")
        print(f"{'='*60}")

        for gen in range(self.generations):
            sorted_indices = np.argsort(fitnesses)
            new_population = []
            for i in range(self.elite_size):
                new_population.append(population[sorted_indices[i]].copy())

            while len(new_population) < self.population_size:
                parent1 = self._tournament_select(population, fitnesses)
                parent2 = self._tournament_select(population, fitnesses)
                child = self._crossover(parent1, parent2)
                child = self._mutate(child)
                new_population.append(child)

            population = new_population
            fitnesses = [self.evaluator.fitness(r) for r in population]

            best_idx = np.argmin(fitnesses)
            if fitnesses[best_idx] < self.best_fitness:
                self.best_fitness = fitnesses[best_idx]
                self.best_route = population[best_idx].copy()

            if self.verbose:
                ev = self.evaluator.evaluate_route(population[best_idx])
                avg_fit = sum(fitnesses) / len(fitnesses)
                print(
                    f"[GA] Gen {gen+1:>4}/{self.generations}"
                    f"  best_fit={self.best_fitness:.4f}"
                    f"  avg_fit={avg_fit:.4f}"
                    f"  dist={ev['total_distance_km']:.2f}km"
                    f"  time={ev['total_time_min']:.1f}min"
                    f"  co2={ev['total_co2_kg']:.3f}kg"
                    f"  hotel={self.best_route.hotel_id}"
                )

        print(f"[GA] DONE  best_fit={self.best_fitness:.4f}  time={time.time()-start_time:.2f}s\n")
        self.computation_time = time.time() - start_time
        return self.best_route
