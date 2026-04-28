import time
import numpy as np
from typing import List, Optional

from backend.app.optimizers.base import BaseOptimizer, Route
from backend.app.optimizers.ga import GAOptimizer
from backend.app.optimizers.alns import ALNSOperators
from backend.app.services.data_loader import DataLoader
from backend.app.schemas.models import OptimizeRequest


class GAAlnsOptimizer(BaseOptimizer):
    def __init__(
        self,
        data: DataLoader,
        request: OptimizeRequest,
        population_size: int = 50,
        generations: int = 80,
        crossover_rate: float = 0.8,
        mutation_rate: float = 0.3,
        tournament_size: int = 5,
        elite_size: int = 5,
        alns_iterations: int = 10,
        n_remove: int = 2,
        seed: Optional[int] = None,
        verbose: bool = True,
    ):
        super().__init__(data, request)
        self.verbose = verbose
        self.population_size = population_size
        self.generations = generations
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.tournament_size = tournament_size
        self.elite_size = elite_size
        self.alns_iterations = alns_iterations
        self.n_remove = n_remove
        self.rng = np.random.default_rng(seed)
        self.alns = ALNSOperators(data, request, self.rng)
        self._ga = GAOptimizer(data, request, population_size, generations, crossover_rate, mutation_rate, tournament_size, elite_size, seed)

    def _alns_local_search(self, route: Route) -> Route:
        best = route.copy()
        best_fitness = self.evaluator.fitness(best)
        current = route.copy()

        for _ in range(self.alns_iterations):
            op_choice = self.rng.integers(0, 3)
            if op_choice == 0:
                destroyed, removed = self.alns.random_removal(current, self.n_remove)
            elif op_choice == 1:
                destroyed, removed = self.alns.worst_removal(current, self.evaluator, self.n_remove)
            else:
                destroyed, removed = self.alns.shaw_removal(current, self.n_remove)

            if not removed:
                continue

            repair_choice = self.rng.integers(0, 3)
            if repair_choice == 0:
                repaired = self.alns.greedy_insert(destroyed, removed, self.evaluator)
            elif repair_choice == 1:
                repaired = self.alns.random_insert(destroyed, removed)
            else:
                repaired = self.alns.regret_insert(destroyed, removed, self.evaluator)

            f = self.evaluator.fitness(repaired)
            if f < best_fitness:
                best = repaired.copy()
                best_fitness = f
                current = repaired
            else:
                current = repaired

        return best

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

    def optimize(self) -> Route:
        start_time = time.time()

        population = self._init_population()
        fitnesses = [self.evaluator.fitness(r) for r in population]

        print(f"\n{'='*60}")
        print(f"[GA+ALNS] START  pop={self.population_size}  gen={self.generations}")
        print(f"[GA+ALNS] alns_iter={self.alns_iterations}  n_remove={self.n_remove}")
        print(f"{'='*60}")

        for gen in range(self.generations):
            sorted_indices = np.argsort(fitnesses)
            new_population = []

            for i in range(self.elite_size):
                elite = population[sorted_indices[i]].copy()
                new_population.append(elite)

            while len(new_population) < self.population_size:
                p1 = self._tournament_select(population, fitnesses)
                p2 = self._tournament_select(population, fitnesses)
                child = self._ga._crossover(p1, p2)
                child = self._ga._mutate(child)

                if self.rng.random() < 0.3:
                    child = self._alns_local_search(child)

                new_population.append(child)

            population = new_population
            fitnesses = [self.evaluator.fitness(r) for r in population]

            best_idx = int(np.argmin(fitnesses))
            if fitnesses[best_idx] < self.best_fitness:
                self.best_fitness = fitnesses[best_idx]
                self.best_route = population[best_idx].copy()

            if self.verbose:
                ev = self.evaluator.evaluate_route(population[best_idx])
                avg_fit = sum(fitnesses) / len(fitnesses)
                worst_fit = max(fitnesses)
                hotels_str = ",".join(self.best_route.hotel_ids) if self.best_route.hotel_ids else "none"
                print(
                    f"[GA+ALNS] Gen {gen+1:>4}/{self.generations}"
                    f"  best_fit={self.best_fitness:.4f}"
                    f"  avg_fit={avg_fit:.4f}"
                    f"  worst_fit={worst_fit:.4f}"
                    f"  dist={ev['total_distance_km']:.2f}km"
                    f"  time={ev['total_time_min']:.1f}min"
                    f"  co2={ev['total_co2_kg']:.3f}kg"
                    f"  hotels={hotels_str}"
                )

        print(f"[GA+ALNS] DONE  best_fit={self.best_fitness:.4f}  time={time.time()-start_time:.2f}s\n")
        self.computation_time = time.time() - start_time
        return self.best_route
