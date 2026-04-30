import time
import numpy as np
from typing import List, Optional

from backend.app.optimizers.base import BaseOptimizer, Route, RouteEvaluator
from backend.app.services.data_loader import DataLoader
from backend.app.schemas.models import OptimizeRequest, PlaceType


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

        # Get values from parent2 that are not in the segment
        segment_set = set(parent1[start:end + 1])
        fill_values = [g for g in parent2 if g not in segment_set]
        
        fill_idx = 0
        for i in range(size):
            if child[i] is None and fill_idx < len(fill_values):
                child[i] = fill_values[fill_idx]
                fill_idx += 1

        # CRITICAL: If child still has None, it means parent2 didn't have enough unique values
        # Fill with random available places from the global pool to maintain size
        if None in child:
            candidates = self._get_candidate_places()
            # We don't know which IDs are "seen" globally here, but we can at least avoid
            # duplicates within this specific day. The cross-day deduplication happens later.
            pool = [p.id for p in candidates if p.id not in segment_set and p.id not in fill_values]
            self.rng.shuffle(pool)
            pool_idx = 0
            for i in range(size):
                if child[i] is None and pool_idx < len(pool):
                    child[i] = pool[pool_idx]
                    pool_idx += 1

        # Final safety filter
        final_child = [x for x in child if x is not None]
        return final_child

    def _crossover(self, p1: Route, p2: Route) -> Route:
        if self.rng.random() > self.crossover_rate:
            return p1.copy()

        num_days = p1.num_days
        child_day_places = []

        for d in range(num_days):
            child_day = self._order_crossover(p1.day_places[d], p2.day_places[d])
            child_day_places.append(child_day)

        # Remove cross-day duplicates
        seen = set()
        for d in range(num_days):
            new_day = []
            for pid in child_day_places[d]:
                if pid not in seen:
                    new_day.append(pid)
                    seen.add(pid)
                else:
                    # Replace with an unused candidate
                    candidates = self._get_candidate_places()
                    replacements = [p.id for p in candidates if p.id not in seen]
                    if replacements:
                        rep = replacements[self.rng.integers(0, len(replacements))]
                        new_day.append(rep)
                        seen.add(rep)
            child_day_places[d] = new_day

        # FOOD_CAFE counts as FOOD for constraint purposes
        FOOD_TYPES = (PlaceType.FOOD, PlaceType.FOOD_CAFE)
        MANDATORY_TYPES = (PlaceType.OTOP, PlaceType.FOOD, PlaceType.FOOD_CAFE)

        # Repair OTOP and FOOD constraints (exactly 1 per day)
        for d in range(num_days):
            day_places = child_day_places[d]
            place_map = {p.id: p for p in self.data.places}

            # OTOP: exactly 1
            otop_pids = [pid for pid in day_places if place_map.get(pid) and place_map[pid].type == PlaceType.OTOP]
            while len(otop_pids) > 1:
                pid_to_remove = otop_pids.pop()
                candidates = self._get_candidate_places()
                replacements = [p.id for p in candidates if p.id not in seen and p.type not in MANDATORY_TYPES]
                if replacements:
                    rep = replacements[self.rng.integers(0, len(replacements))]
                    day_places[day_places.index(pid_to_remove)] = rep
                    seen.discard(pid_to_remove)
                    seen.add(rep)
                else:
                    day_places.remove(pid_to_remove)
                    seen.discard(pid_to_remove)
            if len(otop_pids) == 0:
                candidates = self._get_candidate_places()
                replacements = [p.id for p in candidates if p.id not in seen and p.type == PlaceType.OTOP]
                if replacements:
                    rep = replacements[self.rng.integers(0, len(replacements))]
                    non_mandatory = [pid for pid in day_places if place_map.get(pid) and place_map[pid].type not in MANDATORY_TYPES]
                    if non_mandatory:
                        day_places[day_places.index(non_mandatory[0])] = rep
                        seen.discard(non_mandatory[0])
                    else:
                        day_places.append(rep)
                    seen.add(rep)

            # FOOD (including FOOD_CAFE): at least 1
            food_pids = [pid for pid in day_places if place_map.get(pid) and place_map[pid].type in FOOD_TYPES]
            while len(food_pids) > 1:
                pid_to_remove = food_pids.pop()
                candidates = self._get_candidate_places()
                replacements = [p.id for p in candidates if p.id not in seen and p.type not in MANDATORY_TYPES]
                if replacements:
                    rep = replacements[self.rng.integers(0, len(replacements))]
                    day_places[day_places.index(pid_to_remove)] = rep
                    seen.discard(pid_to_remove)
                    seen.add(rep)
                else:
                    day_places.remove(pid_to_remove)
                    seen.discard(pid_to_remove)
            if len(food_pids) == 0:
                candidates = self._get_candidate_places()
                replacements = [p.id for p in candidates if p.id not in seen and p.type in FOOD_TYPES]
                if replacements:
                    rep = replacements[self.rng.integers(0, len(replacements))]
                    non_mandatory = [pid for pid in day_places if place_map.get(pid) and place_map[pid].type not in MANDATORY_TYPES]
                    if non_mandatory:
                        day_places[day_places.index(non_mandatory[0])] = rep
                        seen.discard(non_mandatory[0])
                    else:
                        day_places.append(rep)
                    seen.add(rep)

        # Hotel selection: randomly pick from either parent
        child_hotel_ids = []
        for i in range(len(p1.hotel_ids)):
            if i < len(p2.hotel_ids):
                child_hotel_ids.append(
                    self.rng.choice([p1.hotel_ids[i], p2.hotel_ids[i]])
                )
            else:
                child_hotel_ids.append(p1.hotel_ids[i])

        return Route(child_day_places, child_hotel_ids)

    def _mutate(self, route: Route) -> Route:
        if self.rng.random() > self.mutation_rate:
            return route

        num_days = route.num_days
        mutation_type = self.rng.integers(0, 4)

        if mutation_type == 0:
            # Swap two places within a random day
            day = int(self.rng.integers(0, num_days))
            places = route.day_places[day]
            if len(places) >= 2:
                i, j = self.rng.choice(len(places), size=2, replace=False)
                places[i], places[j] = places[j], places[i]

        elif mutation_type == 1:
            # Reverse a segment within a random day
            day = int(self.rng.integers(0, num_days))
            places = route.day_places[day]
            if len(places) >= 2:
                i, j = sorted(self.rng.choice(len(places), size=2, replace=False))
                places[i:j + 1] = reversed(places[i:j + 1])

        elif mutation_type == 2:
            # Swap places between two different days
            if num_days >= 2:
                d1, d2 = self.rng.choice(num_days, size=2, replace=False)
                if route.day_places[d1] and route.day_places[d2]:
                    i1 = int(self.rng.integers(0, len(route.day_places[d1])))
                    pid1 = route.day_places[d1][i1]
                    p1_type = next(p.type for p in self.data.places if p.id == pid1)
                    
                    # Find a place in d2 with a compatible type to swap
                    # If it's FOOD or OTOP, must swap with FOOD or OTOP respectively to keep counts 1 per day.
                    # If Travel/Culture, swap with any non-Food/non-OTOP
                    FOOD_TYPES = (PlaceType.FOOD, PlaceType.FOOD_CAFE)
                    PROTECTED = (PlaceType.FOOD, PlaceType.FOOD_CAFE, PlaceType.OTOP)
                    valid_i2s = []
                    for i2, pid2 in enumerate(route.day_places[d2]):
                        p2_type = next(p.type for p in self.data.places if p.id == pid2)
                        if p1_type == PlaceType.OTOP:
                            if p2_type == PlaceType.OTOP:
                                valid_i2s.append(i2)
                        elif p1_type in FOOD_TYPES:
                            if p2_type in FOOD_TYPES:
                                valid_i2s.append(i2)
                        else:
                            if p2_type not in PROTECTED:
                                valid_i2s.append(i2)
                    
                    if valid_i2s:
                        i2 = int(self.rng.choice(valid_i2s))
                        route.day_places[d1][i1], route.day_places[d2][i2] = (
                            route.day_places[d2][i2],
                            route.day_places[d1][i1],
                        )

        elif mutation_type == 3:
            # Change a random hotel
            hotels = self.data.get_hotels()
            if hotels and route.hotel_ids:
                h_idx = int(self.rng.integers(0, len(route.hotel_ids)))
                route.hotel_ids[h_idx] = hotels[self.rng.integers(0, len(hotels))].id

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
                hotels_str = ",".join(self.best_route.hotel_ids) if self.best_route.hotel_ids else "none"
                print(
                    f"[GA] Gen {gen+1:>4}/{self.generations}"
                    f"  best_fit={self.best_fitness:.4f}"
                    f"  avg_fit={avg_fit:.4f}"
                    f"  dist={ev['total_distance_km']:.2f}km"
                    f"  time={ev['total_time_min']:.1f}min"
                    f"  co2={ev['total_co2_kg']:.3f}kg"
                    f"  hotels={hotels_str}"
                )

        print(f"[GA] DONE  best_fit={self.best_fitness:.4f}  time={time.time()-start_time:.2f}s\n")
        self.computation_time = time.time() - start_time
        return self.best_route
