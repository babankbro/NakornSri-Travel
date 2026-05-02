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
            if p.is_tourist
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

    def _is_protected(self, route: Route, pid: str) -> bool:
        """Return True if removing pid would leave its day with 0 food or 0 OTOP places."""
        place_map = {p.id: p for p in self.data.places}
        p = place_map.get(pid)
        if p is None:
            return False
        for day in route.day_places:
            if pid not in day:
                continue
            if p.is_food:
                food_count = sum(1 for d_pid in day if d_pid in place_map and place_map[d_pid].is_food)
                return food_count <= 1
            if p.type == PlaceType.OTOP:
                otop_count = sum(1 for d_pid in day if d_pid in place_map and place_map[d_pid].type == PlaceType.OTOP)
                return otop_count <= 1
        return False

    # ---- Destroy operators ----

    def random_removal(self, route: Route, n_remove: int = 2) -> Tuple[Route, List[str]]:
        new_route = route.copy()
        removed = []
        for _ in range(n_remove):
            all_places = [pid for pid in self._all_place_ids(new_route) if not self._is_protected(new_route, pid)]
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
                    if self._is_protected(new_route, pid):
                        continue
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
        removable = [pid for pid in self._all_place_ids(new_route) if not self._is_protected(new_route, pid)]
        if len(removable) < 1:
            return new_route, []
        seed_pid = removable[self.rng.integers(0, len(removable))]
        seed_idx = self.data.id_to_index.get(seed_pid, 0)

        similarities = []
        for pid in removable:
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
        place_lookup = {p.id: p for p in self.data.places}

        for pid in removed:
            p_obj = place_lookup.get(pid)
            p_type = p_obj.type if p_obj else None
            day = None

            # For OTOP: prefer a day that has no OTOP yet (exactly-1 constraint)
            # For pure FOOD: prefer a day that has no food yet (≥1 food constraint)
            # For CAFE / FOOD_CAFE / TRAVEL / CULTURE: any day is fine (extras welcome)
            if p_type == PlaceType.OTOP:
                for d in range(num_days):
                    otop_on_day = any(
                        place_lookup[p_id].type == PlaceType.OTOP
                        for p_id in new_route.day_places[d] if p_id in place_lookup
                    )
                    if not otop_on_day:
                        day = d
                        break
            elif p_type == PlaceType.FOOD:
                # Pure FOOD: prefer a day without any food stop
                for d in range(num_days):
                    food_on_day = any(
                        place_lookup[p_id].is_food
                        for p_id in new_route.day_places[d] if p_id in place_lookup
                    )
                    if not food_on_day:
                        day = d
                        break
            # CAFE, FOOD_CAFE, TRAVEL, CULTURE → fall through to random below

            if day is None:
                day = int(self.rng.integers(0, num_days))

            day_list = new_route.day_places[day]
            if len(day_list) >= self.request.max_places_per_day:
                # Try other days with capacity
                inserted = False
                for d in range(num_days):
                    if len(new_route.day_places[d]) < self.request.max_places_per_day:
                        pos = int(self.rng.integers(0, len(new_route.day_places[d]) + 1))
                        new_route.day_places[d].insert(pos, pid)
                        inserted = True
                        break
                if not inserted:
                    # Force-insert even over capacity as last resort
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
