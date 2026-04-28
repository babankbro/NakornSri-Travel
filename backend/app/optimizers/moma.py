import time
import numpy as np
from typing import List, Tuple, Dict, Any, Optional

from backend.app.optimizers.base import BaseOptimizer, Route
from backend.app.optimizers.ga import GAOptimizer
from backend.app.optimizers.sm import SMOptimizer
from backend.app.optimizers.alns import ALNSOperators
from backend.app.services.data_loader import DataLoader
from backend.app.schemas.models import OptimizeRequest

class MOMAOptimizer(BaseOptimizer):
    """
    Mixed SM-GA-ALNS with NSGA-II Backbone (MOMA).
    Optimizes for:
    f1: Distance (minimize)
    f2: Time + CO2 (minimize)
    f3: -Rating (minimize, equivalent to maximizing rating)
    """

    def __init__(
        self,
        data: DataLoader,
        request: OptimizeRequest,
        population_size: int = 50,
        generations: int = 80,
        sm_seed_ratio: float = 0.1,
        alns_mutation_rate: float = 0.2,
        standard_mutation_rate: float = 0.3,
        alns_iterations: int = 5,
        n_remove: int = 2,
        elite_size: int = 5,
        seed: Optional[int] = None,
        verbose: bool = True,
    ):
        super().__init__(data, request)
        self.verbose = verbose
        self.population_size = population_size
        self.generations = generations
        self.sm_seed_ratio = sm_seed_ratio
        self.alns_mutation_rate = alns_mutation_rate
        self.standard_mutation_rate = standard_mutation_rate
        self.alns_iterations = alns_iterations
        self.n_remove = n_remove
        self.elite_size = elite_size
        self.rng = np.random.default_rng(seed)
        self.alns = ALNSOperators(data, request, self.rng)
        self._ga = GAOptimizer(data, request, population_size, generations, seed=seed)

    def _evaluate_objectives(self, route: Route) -> Tuple[float, float, float, float]:
        ev = self.evaluator.evaluate_route(route)
        
        # Base objectives: distance, co2, -rating
        f1 = ev["total_distance_km"]
        f2 = ev["total_co2_kg"]
        
        # Calculate avg rating
        place_map = {p.id: p for p in self.data.places}
        all_place_ids = [pid for day in route.day_places for pid in day]
        ratings = [place_map[pid].rate for pid in all_place_ids if pid in place_map]
        avg_rating = float(np.mean(ratings)) if ratings else 0.0
        f3 = -avg_rating  # minimize

        # Constraint penalty (calculated via evaluator.fitness which includes penalty logic)
        # We can extract penalty by doing fitness - cost
        w_d = self.request.weight_distance
        w_c = self.request.weight_co2

        dist_norm = ev["total_distance_km"] / 200.0
        co2_norm = ev["total_co2_kg"] / 150.0

        cost = w_d * dist_norm + w_c * co2_norm
        fitness_val = self.evaluator.fitness(route)
        penalty = fitness_val - cost

        return (f1, f2, f3, penalty)

    def _constrained_dominates(self, obj_a: Tuple[float, float, float, float], obj_b: Tuple[float, float, float, float]) -> bool:
        """Returns True if A constrained-dominates B"""
        # obj = (f1, f2, f3, penalty)
        penalty_a = obj_a[3]
        penalty_b = obj_b[3]

        # 1. A is feasible, B is not
        if penalty_a == 0 and penalty_b > 0:
            return True
        # 2. B is feasible, A is not
        if penalty_a > 0 and penalty_b == 0:
            return False
        # 3. Both infeasible, A has smaller penalty
        if penalty_a > 0 and penalty_b > 0:
            if penalty_a < penalty_b:
                return True
            if penalty_a > penalty_b:
                return False

        # 4. Both have same feasibility (e.g. both 0 penalty), check Pareto dominance
        # A dominates B if A is no worse than B in all objectives and strictly better in at least one
        better_in_any = False
        for i in range(3):
            if obj_a[i] > obj_b[i]:
                return False
            if obj_a[i] < obj_b[i]:
                better_in_any = True
        return better_in_any

    def _fast_non_dominated_sort(self, population_objs: List[Tuple[float, float, float, float]]) -> List[List[int]]:
        S = [[] for _ in range(len(population_objs))]
        fronts = [[]]
        n = [0] * len(population_objs)
        rank = [0] * len(population_objs)

        for p in range(len(population_objs)):
            for q in range(len(population_objs)):
                if p == q:
                    continue
                if self._constrained_dominates(population_objs[p], population_objs[q]):
                    S[p].append(q)
                elif self._constrained_dominates(population_objs[q], population_objs[p]):
                    n[p] += 1
            if n[p] == 0:
                rank[p] = 0
                fronts[0].append(p)

        i = 0
        while i < len(fronts):
            Q = []
            for p in fronts[i]:
                for q in S[p]:
                    n[q] -= 1
                    if n[q] == 0:
                        rank[q] = i + 1
                        Q.append(q)
            if len(Q) > 0:
                fronts.append(Q)
            i += 1
                
        return fronts

    def _crowding_distance_assignment(self, front: List[int], population_objs: List[Tuple[float, float, float, float]]) -> List[float]:
        l = len(front)
        distances = {i: 0.0 for i in front}
        if l == 0:
            return [0.0 for _ in front]
        if l <= 2:
            for i in front:
                distances[i] = float('inf')
            return [distances[i] for i in front]
            
        for m in range(3): # For each objective (ignoring penalty)
            # Sort front by objective m
            sorted_front = sorted(front, key=lambda i: population_objs[i][m])
            distances[sorted_front[0]] = float('inf')
            distances[sorted_front[-1]] = float('inf')
            
            f_min = population_objs[sorted_front[0]][m]
            f_max = population_objs[sorted_front[-1]][m]
            
            if f_max - f_min > 0:
                for j in range(1, l - 1):
                    distances[sorted_front[j]] += (population_objs[sorted_front[j+1]][m] - population_objs[sorted_front[j-1]][m]) / (f_max - f_min)
                    
        return [distances[i] for i in front]

    def _tournament_select(self, pop_indices: List[int], ranks: List[int], distances: List[float], tournament_size: int = 2) -> int:
        indices = self.rng.choice(len(pop_indices), size=tournament_size, replace=False)
        best_idx = indices[0]
        
        for idx in indices[1:]:
            # Prefer lower rank
            if ranks[idx] < ranks[best_idx]:
                best_idx = idx
            # If same rank, prefer larger crowding distance
            elif ranks[idx] == ranks[best_idx] and distances[idx] > distances[best_idx]:
                best_idx = idx
                
        return pop_indices[best_idx]

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

    def optimize(self) -> Route:
        start_time = time.time()

        print(f"\n{'='*60}")
        print(f"[MOMA] START  pop={self.population_size}  gen={self.generations}")
        print(f"[MOMA] SM Seed={self.sm_seed_ratio*100:.0f}%  ALNS_Mut={self.alns_mutation_rate}")
        print(f"{'='*60}")

        # 1. Initialization (Phase 1: Hybrid Seed)
        population = []
        num_sm = int(self.population_size * self.sm_seed_ratio)
        
        # Add SM routes
        if num_sm > 0:
            sm_opt = SMOptimizer(self.data, self.request, verbose=False)
            sm_route = sm_opt.optimize()
            population.append(sm_route)
            # Add variations of SM route
            for _ in range(num_sm - 1):
                population.append(self._ga._mutate(sm_route.copy()))
                
        # Fill remaining randomly
        while len(population) < self.population_size:
            population.append(self._generate_random_route(self.rng))

        population_objs = [self._evaluate_objectives(r) for r in population]

        for gen in range(self.generations):
            # Phase 2 & 3: NSGA-II Evaluation and Selection
            fronts = self._fast_non_dominated_sort(population_objs)
            
            ranks = [0] * len(population)
            for r, front in enumerate(fronts):
                for idx in front:
                    ranks[idx] = r
                    
            distances = [0.0] * len(population)
            for front in fronts:
                front_dists = self._crowding_distance_assignment(front, population_objs)
                for i, d in zip(front, front_dists):
                    distances[i] = d

            new_population = []

            # Elitism: carry over the top `elite_size` individuals directly from the 1st Pareto front
            for i in fronts[0][:self.elite_size]:
                new_population.append(population[i].copy())

            # Reproduction
            while len(new_population) < self.population_size:
                p1_idx = self._tournament_select(list(range(len(population))), ranks, distances)
                p2_idx = self._tournament_select(list(range(len(population))), ranks, distances)
                
                child = self._ga._crossover(population[p1_idx], population[p2_idx])
                
                # Memetic Local Search
                if self.rng.random() < self.alns_mutation_rate:
                    child = self._alns_local_search(child)
                elif self.rng.random() < self.standard_mutation_rate:
                    child = self._ga._mutate(child)
                    
                new_population.append(child)

            # Combine and Select Top N
            combined_pop = population + new_population
            combined_objs = population_objs + [self._evaluate_objectives(r) for r in new_population]
            
            combined_fronts = self._fast_non_dominated_sort(combined_objs)
            
            next_pop = []
            next_objs = []
            
            for front in combined_fronts:
                if len(next_pop) + len(front) <= self.population_size:
                    for i in front:
                        next_pop.append(combined_pop[i])
                        next_objs.append(combined_objs[i])
                else:
                    # Need to select subset based on crowding distance
                    front_dists = self._crowding_distance_assignment(front, combined_objs)
                    sorted_front = [x for _, x in sorted(zip(front_dists, front), reverse=True)]
                    needed = self.population_size - len(next_pop)
                    for i in sorted_front[:needed]:
                        next_pop.append(combined_pop[i])
                        next_objs.append(combined_objs[i])
                    break
                    
            population = next_pop
            population_objs = next_objs

            # Tracking best scalar fitness for simple reporting
            scalar_fitnesses = [self.evaluator.fitness(r) for r in population]
            best_idx = int(np.argmin(scalar_fitnesses))
            if scalar_fitnesses[best_idx] < self.best_fitness:
                self.best_fitness = scalar_fitnesses[best_idx]
                self.best_route = population[best_idx].copy()

            if self.verbose:
                ev = self.evaluator.evaluate_route(population[best_idx])
                avg_fit = sum(scalar_fitnesses) / len(scalar_fitnesses)
                print(
                    f"[MOMA] Gen {gen+1:>4}/{self.generations}"
                    f"  best_fit={self.best_fitness:.4f}"
                    f"  avg_fit={avg_fit:.4f}"
                    f"  dist={ev['total_distance_km']:.2f}km"
                    f"  time={ev['total_time_min']:.1f}min"
                    f"  co2={ev['total_co2_kg']:.3f}kg"
                    f"  pareto_fronts={len(combined_fronts)}"
                )

        # Final Selection: pick the single best scalar fitness route from the 1st Pareto front
        scalar_fitnesses = [self.evaluator.fitness(r) for r in population]
        best_front_indices = combined_fronts[0] if 'combined_fronts' in locals() and len(combined_fronts) > 0 else list(range(len(population)))
        
        # Of the items in the first front, find the one with the lowest scalar fitness
        best_front_fitnesses = [scalar_fitnesses[i] for i in best_front_indices if i < len(population)]
        if best_front_fitnesses:
            best_idx_in_front = best_front_indices[int(np.argmin(best_front_fitnesses))]
            self.best_fitness = scalar_fitnesses[best_idx_in_front]
            self.best_route = population[best_idx_in_front].copy()
        
        print(f"[MOMA] DONE  best_fit={self.best_fitness:.4f}  time={time.time()-start_time:.2f}s\n")
        self.computation_time = time.time() - start_time
        
        return self.best_route
