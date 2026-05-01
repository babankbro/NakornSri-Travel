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

        # Repair constraints:
        #   OTOP — exactly 1 per day (hard)
        #   FOOD — at least 1 per day (≥1); extra food/cafe places are ALLOWED
        # FOOD_CAFE counts as food (is_food covers Food and Food and Café)
        place_lookup = {p.id: p for p in self.data.places}
        for d in range(num_days):
            day_places = child_day_places[d]

            # --- OTOP: exactly 1 ---
            otop_pids = [pid for pid in day_places if pid in place_lookup and place_lookup[pid].type == PlaceType.OTOP]
            while len(otop_pids) > 1:
                pid_to_remove = otop_pids.pop()
                candidates = self._get_candidate_places()
                replacements = [p.id for p in candidates if p.id not in seen and p.type != PlaceType.OTOP]
                if replacements:
                    rep = replacements[self.rng.integers(0, len(replacements))]
                    day_places[day_places.index(pid_to_remove)] = rep
                    seen.discard(pid_to_remove)
                    seen.add(rep)
                else:
                    day_places.remove(pid_to_remove)
                    seen.discard(pid_to_remove)
            if len(otop_pids) == 0:
                replacements = [p.id for p in self.data.places if p.id not in seen and p.type == PlaceType.OTOP]
                if replacements:
                    rep = replacements[self.rng.integers(0, len(replacements))]
                    non_otop = [pid for pid in day_places if pid in place_lookup and place_lookup[pid].type != PlaceType.OTOP]
                    if non_otop:
                        seen.discard(non_otop[0])
                        day_places[day_places.index(non_otop[0])] = rep
                    else:
                        day_places.append(rep)
                    seen.add(rep)

            # --- FOOD: at least 1 (extras are welcome — they become extra cafe visits) ---
            food_pids = [pid for pid in day_places if pid in place_lookup and place_lookup[pid].is_food]
            if len(food_pids) == 0:
                replacements = [p.id for p in self.data.places if p.id not in seen and p.is_food]
                if replacements:
                    rep = replacements[self.rng.integers(0, len(replacements))]
                    non_special = [pid for pid in day_places if pid in place_lookup
                                   and place_lookup[pid].type != PlaceType.OTOP
                                   and not place_lookup[pid].is_food]
                    if non_special:
                        seen.discard(non_special[0])
                        day_places[day_places.index(non_special[0])] = rep
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
                    
                    # Swap compatibility rules:
                    #   OTOP ↔ OTOP only (exactly-1 constraint is hard)
                    #   FOOD ↔ food-type (keep at least 1 food on each side)
                    #   FOOD_CAFE / CAFE / TRAVEL / CULTURE ↔ anything except OTOP
                    #   (multiple food-type places per day is now allowed)
                    place_lookup_m = {p.id: p for p in self.data.places}
                    p1_obj = place_lookup_m.get(pid1)
                    valid_i2s = []
                    for i2, pid2 in enumerate(route.day_places[d2]):
                        p2_obj = place_lookup_m.get(pid2)
                        if p2_obj is None:
                            continue
                        if p1_type == PlaceType.OTOP:
                            # OTOP must swap with OTOP to keep exactly-1 rule
                            if p2_obj.type == PlaceType.OTOP:
                                valid_i2s.append(i2)
                        elif p1_type == PlaceType.FOOD:
                            # Pure FOOD: swap with any food-type to maintain ≥1 food per day
                            if p2_obj.is_food:
                                valid_i2s.append(i2)
                        else:
                            # CAFE, FOOD_CAFE, TRAVEL, CULTURE: freely swap with non-OTOP
                            if p2_obj.type != PlaceType.OTOP:
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

        best_avg_rate = 0.0
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
                
                # Calculate avg rating for log
                place_map = {p.id: p for p in self.data.places}
                best_pids = [pid for day in population[best_idx].day_places for pid in day]
                best_ratings = [place_map[pid].rate for pid in best_pids if pid in place_map]
                best_avg_rate = np.mean(best_ratings) if best_ratings else 0.0

                hotels_str = ",".join(self.best_route.hotel_ids) if self.best_route.hotel_ids else "none"
                print(
                    f"[GA] Gen {gen+1:>4}/{self.generations}"
                    f"  best_fit={self.best_fitness:.4f}"
                    f"  avg_fit={avg_fit:.4f}"
                    f"  dist={ev['total_distance_km']:.2f}km"
                    f"  time={ev['total_time_min']:.1f}min"
                    f"  co2={ev['total_co2_kg']:.3f}kg"
                    f"  rate={best_avg_rate:.2f}"
                    f"  hotels={hotels_str}"
                )

        print(f"[GA] DONE  best_fit={self.best_fitness:.4f}  rate={best_avg_rate:.2f}  time={time.time()-start_time:.2f}s\n")
        self.computation_time = time.time() - start_time
        return self.best_route
