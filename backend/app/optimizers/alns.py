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
            if p.type in (PlaceType.TRAVEL, PlaceType.CULTURE, PlaceType.OTOP)
        ]

    # ---- Destroy operators ----

    def random_removal(self, route: Route, n_remove: int = 2) -> Tuple[Route, List[str]]:
        new_route = route.copy()
        removed = []
        for _ in range(n_remove):
            all_places = new_route.day1_places + new_route.day2_places
            if not all_places:
                break
            idx = self.rng.integers(0, len(all_places))
            pid = all_places[idx]
            if pid in new_route.day1_places:
                new_route.day1_places.remove(pid)
            else:
                new_route.day2_places.remove(pid)
            removed.append(pid)
        return new_route, removed

    def worst_removal(self, route: Route, evaluator: RouteEvaluator, n_remove: int = 2) -> Tuple[Route, List[str]]:
        new_route = route.copy()
        removed = []
        for _ in range(n_remove):
            worst_pid = None
            worst_cost = -float("inf")
            base_fitness = evaluator.fitness(new_route)
            for day_list in [new_route.day1_places, new_route.day2_places]:
                for pid in day_list:
                    temp = new_route.copy()
                    if pid in temp.day1_places:
                        temp.day1_places.remove(pid)
                    else:
                        temp.day2_places.remove(pid)
                    new_fitness = evaluator.fitness(temp)
                    cost_reduction = base_fitness - new_fitness
                    if cost_reduction > worst_cost:
                        worst_cost = cost_reduction
                        worst_pid = pid
            if worst_pid:
                if worst_pid in new_route.day1_places:
                    new_route.day1_places.remove(worst_pid)
                else:
                    new_route.day2_places.remove(worst_pid)
                removed.append(worst_pid)
        return new_route, removed

    def shaw_removal(self, route: Route, n_remove: int = 2) -> Tuple[Route, List[str]]:
        new_route = route.copy()
        all_places = new_route.day1_places + new_route.day2_places
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
            if pid in new_route.day1_places:
                new_route.day1_places.remove(pid)
            elif pid in new_route.day2_places:
                new_route.day2_places.remove(pid)
        return new_route, removed

    # ---- Repair operators ----

    def greedy_insert(self, route: Route, removed: List[str], evaluator: RouteEvaluator) -> Route:
        new_route = route.copy()
        for pid in removed:
            best_fitness = float("inf")
            best_day = None
            best_pos = None
            for day_idx, day_list in enumerate([new_route.day1_places, new_route.day2_places]):
                if len(day_list) >= self.request.max_places_per_day:
                    continue
                for pos in range(len(day_list) + 1):
                    temp = new_route.copy()
                    target = temp.day1_places if day_idx == 0 else temp.day2_places
                    target.insert(pos, pid)
                    f = evaluator.fitness(temp)
                    if f < best_fitness:
                        best_fitness = f
                        best_day = day_idx
                        best_pos = pos
            if best_day is not None:
                target = new_route.day1_places if best_day == 0 else new_route.day2_places
                target.insert(best_pos, pid)
        return new_route

    def random_insert(self, route: Route, removed: List[str]) -> Route:
        new_route = route.copy()
        for pid in removed:
            day = self.rng.integers(0, 2)
            day_list = new_route.day1_places if day == 0 else new_route.day2_places
            if len(day_list) >= self.request.max_places_per_day:
                day_list = new_route.day2_places if day == 0 else new_route.day1_places
            if len(day_list) < self.request.max_places_per_day:
                pos = self.rng.integers(0, len(day_list) + 1)
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
                for day_idx, day_list in enumerate([new_route.day1_places, new_route.day2_places]):
                    if len(day_list) >= self.request.max_places_per_day:
                        continue
                    for pos in range(len(day_list) + 1):
                        temp = new_route.copy()
                        target = temp.day1_places if day_idx == 0 else temp.day2_places
                        target.insert(pos, pid)
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
                target = new_route.day1_places if best_day == 0 else new_route.day2_places
                target.insert(best_pos, best_pid)
                remaining.remove(best_pid)
            else:
                break
        return new_route
