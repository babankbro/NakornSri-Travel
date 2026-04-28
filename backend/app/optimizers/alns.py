import numpy as np
from typing import List, Tuple, Optional

from backend.app.optimizers.base import Route, RouteEvaluator, BaseOptimizer
from backend.app.services.data_loader import DataLoader
from backend.app.schemas.models import OptimizeRequest, PlaceType


class ALNSOperators:
    def __init__(self, data: DataLoader, request: OptimizeRequest, rng: np.random.Generator):
        self.data = data
        self.request = request
        self.rng = rng

    def _get_all_candidate_ids(self) -> List[str]:
        return [
            p.id for p in self.data.places
            if p.type in (PlaceType.TRAVEL, PlaceType.CULTURE, PlaceType.OTOP, PlaceType.FOOD)
        ]

    def _all_place_ids(self, route: Route) -> List[str]:
        """Get flattened list of all place IDs across all days."""
        return [pid for day in route.day_places for pid in day]

    def _remove_from_route(self, route: Route, pid: str):
        """Remove a place ID from whichever day it belongs to."""
        for day in route.day_places:
            if pid in day:
                day.remove(pid)
                return

    # ---- Destroy operators ----

    def random_removal(self, route: Route, n_remove: int = 2) -> Tuple[Route, List[str]]:
        new_route = route.copy()
        removed = []
        for _ in range(n_remove):
            all_places = self._all_place_ids(new_route)
            if not all_places:
                break
            idx = self.rng.integers(0, len(all_places))
            pid = all_places[idx]
            self._remove_from_route(new_route, pid)
            removed.append(pid)
        return new_route, removed

    def worst_removal(self, route: Route, evaluator: RouteEvaluator, n_remove: int = 2) -> Tuple[Route, List[str]]:
        new_route = route.copy()
        removed = []
        for _ in range(n_remove):
            worst_pid = None
            worst_cost = -float("inf")
            base_fitness = evaluator.fitness(new_route)
            for day in new_route.day_places:
                for pid in day:
                    temp = new_route.copy()
                    self._remove_from_route(temp, pid)
                    new_fitness = evaluator.fitness(temp)
                    cost_reduction = base_fitness - new_fitness
                    if cost_reduction > worst_cost:
                        worst_cost = cost_reduction
                        worst_pid = pid
            if worst_pid:
                self._remove_from_route(new_route, worst_pid)
                removed.append(worst_pid)
        return new_route, removed

    def shaw_removal(self, route: Route, n_remove: int = 2) -> Tuple[Route, List[str]]:
        new_route = route.copy()
        all_places = self._all_place_ids(new_route)
        if len(all_places) < 2:
            return new_route, []
        seed_pid = all_places[self.rng.integers(0, len(all_places))]
        seed_idx = self.data.id_to_index.get(seed_pid, 0)

        similarities = []
        for pid in all_places:
            if pid == seed_pid:
                continue
            p_idx = self.data.id_to_index.get(pid, 0)
            dist = self.data.distance_matrix[seed_idx][p_idx] if self.data.distance_matrix is not None else 999
            similarities.append((pid, dist))
        similarities.sort(key=lambda x: x[1])

        removed = [seed_pid]
        for pid, _ in similarities[:n_remove - 1]:
            removed.append(pid)

        for pid in removed:
            self._remove_from_route(new_route, pid)
        return new_route, removed

    # ---- Repair operators ----

    def greedy_insert(self, route: Route, removed: List[str], evaluator: RouteEvaluator) -> Route:
        new_route = route.copy()
        for pid in removed:
            best_fitness = float("inf")
            best_day = None
            best_pos = None
            for day_idx, day_list in enumerate(new_route.day_places):
                if len(day_list) >= self.request.max_places_per_day:
                    continue
                for pos in range(len(day_list) + 1):
                    temp = new_route.copy()
                    temp.day_places[day_idx].insert(pos, pid)
                    f = evaluator.fitness(temp)
                    if f < best_fitness:
                        best_fitness = f
                        best_day = day_idx
                        best_pos = pos
            if best_day is not None:
                new_route.day_places[best_day].insert(best_pos, pid)
        return new_route

    def random_insert(self, route: Route, removed: List[str]) -> Route:
        new_route = route.copy()
        num_days = new_route.num_days
        for pid in removed:
            p_type = next(p.type for p in self.data.places if p.id == pid)
            day = None
            
            # If constrained, force it into the day that is missing this type
            if p_type in (PlaceType.FOOD, PlaceType.OTOP):
                for d in range(num_days):
                    if not any(next(p.type for p in self.data.places if p.id == p_id) == p_type for p_id in new_route.day_places[d]):
                        day = d
                        break
            
            if day is None:
                day = int(self.rng.integers(0, num_days))
                
            day_list = new_route.day_places[day]
            if len(day_list) >= self.request.max_places_per_day:
                # Try other days
                inserted = False
                for d in range(num_days):
                    if p_type in (PlaceType.FOOD, PlaceType.OTOP):
                        # Still must respect type constraint if trying other days
                        has_type = any(next(p.type for p in self.data.places if p.id == p_id) == p_type for p_id in new_route.day_places[d])
                        if has_type:
                            continue
                    
                    if len(new_route.day_places[d]) < self.request.max_places_per_day:
                        pos = int(self.rng.integers(0, len(new_route.day_places[d]) + 1))
                        new_route.day_places[d].insert(pos, pid)
                        inserted = True
                        break
                if not inserted and len(day_list) < self.request.max_places_per_day + 1:
                    pos = int(self.rng.integers(0, len(day_list) + 1))
                    day_list.insert(pos, pid)
            else:
                pos = int(self.rng.integers(0, len(day_list) + 1))
                day_list.insert(pos, pid)
        return new_route

    def regret_insert(self, route: Route, removed: List[str], evaluator: RouteEvaluator) -> Route:
        new_route = route.copy()
        remaining = list(removed)
        while remaining:
            best_regret = -float("inf")
            best_pid = None
            best_day = None
            best_pos = None
            for pid in remaining:
                insert_costs = []
                for day_idx, day_list in enumerate(new_route.day_places):
                    if len(day_list) >= self.request.max_places_per_day:
                        continue
                    for pos in range(len(day_list) + 1):
                        temp = new_route.copy()
                        temp.day_places[day_idx].insert(pos, pid)
                        f = evaluator.fitness(temp)
                        insert_costs.append((f, day_idx, pos))
                if len(insert_costs) >= 2:
                    insert_costs.sort(key=lambda x: x[0])
                    regret = insert_costs[1][0] - insert_costs[0][0]
                    if regret > best_regret:
                        best_regret = regret
                        best_pid = pid
                        best_day = insert_costs[0][1]
                        best_pos = insert_costs[0][2]
                elif len(insert_costs) == 1:
                    if best_pid is None:
                        best_pid = pid
                        best_day = insert_costs[0][1]
                        best_pos = insert_costs[0][2]
            if best_pid and best_day is not None:
                new_route.day_places[best_day].insert(best_pos, best_pid)
                remaining.remove(best_pid)
            else:
                break
        return new_route
