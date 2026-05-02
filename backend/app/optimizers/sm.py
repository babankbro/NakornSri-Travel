import time
import numpy as np
from typing import List, Optional, Tuple

from backend.app.optimizers.base import BaseOptimizer, Route
from backend.app.services.data_loader import DataLoader
from backend.app.schemas.models import OptimizeRequest, PlaceType


class SMOptimizer(BaseOptimizer):
    """Clarke-Wright Saving Method adapted for multi-day travel route optimization."""

    def __init__(
        self,
        data: DataLoader,
        request: OptimizeRequest,
        seed: Optional[int] = None,
        verbose: bool = True,
    ):
        super().__init__(data, request)
        self.rng = np.random.default_rng(seed)
        self.verbose = verbose

    def _select_hotels(self) -> List[str]:
        """Select the best hotels for overnight stays.

        Returns a list of (trip_days - 1) hotel IDs.
        For 1-day trips, returns empty list.
        """
        num_hotels_needed = self.request.trip_days - 1
        if num_hotels_needed <= 0:
            return []

        hotels = self.data.get_hotels()
        depot = self.data.get_depot()
        candidates = self._get_candidate_places()

        if not hotels:
            raise ValueError("No hotels available")

        # Score each hotel by distance to depot + avg distance to candidates
        scored = []
        for hotel in hotels:
            dist_to_depot = self.data.get_distance(depot.id, hotel.id)
            avg_to_candidates = np.mean([
                self.data.get_distance(hotel.id, p.id) for p in candidates
            ]) if candidates else 0
            score = dist_to_depot + avg_to_candidates
            scored.append((hotel.id, score))

        scored.sort(key=lambda x: x[1])

        # Pick the top N distinct hotels
        selected = []
        for hotel_id, _ in scored:
            if len(selected) >= num_hotels_needed:
                break
            selected.append(hotel_id)

        # If not enough unique hotels, repeat the best one
        while len(selected) < num_hotels_needed:
            selected.append(scored[0][0])

        return selected

    def _compute_savings(self, hub_id: str, place_ids: List[str]) -> List[Tuple[str, str, float]]:
        """Compute Clarke-Wright savings for all pairs relative to hub.

        savings(i, j) = d(hub, i) + d(hub, j) - d(i, j)
        """
        savings = []
        for i in range(len(place_ids)):
            for j in range(i + 1, len(place_ids)):
                pid_i = place_ids[i]
                pid_j = place_ids[j]
                d_hub_i = self.data.get_distance(hub_id, pid_i)
                d_hub_j = self.data.get_distance(hub_id, pid_j)
                d_i_j = self.data.get_distance(pid_i, pid_j)
                s = d_hub_i + d_hub_j - d_i_j
                savings.append((pid_i, pid_j, s))
        savings.sort(key=lambda x: x[2], reverse=True)
        return savings

    def _build_day_route(
        self,
        hub_id: str,
        end_id: str,
        available_ids: List[str],
        otop_ids: List[str],
        food_ids: List[str],
        max_places: int,
    ) -> List[str]:
        """Build a day's route using savings-based greedy construction."""
        route: List[str] = []
        used: set = set()

        # Step 1: Add exactly 1 OTOP place
        available_otop = [oid for oid in otop_ids if oid in available_ids]
        if available_otop:
            # Pick the OTOP with best savings relative to hub
            best_otop = min(
                available_otop,
                key=lambda oid: self.data.get_distance(hub_id, oid),
            )
            route.append(best_otop)
            used.add(best_otop)

        # Step 2: Add exactly 1 FOOD place
        available_food = [fid for fid in food_ids if fid in available_ids]
        if available_food:
            # Pick the FOOD with best savings relative to hub
            best_food = min(
                available_food,
                key=lambda fid: self.data.get_distance(hub_id, fid),
            )
            route.append(best_food)
            used.add(best_food)

        # Step 3: Compute savings for non-OTOP, non-pure-FOOD candidates.
        # FOOD_CAFE places are allowed as extra tourist slots (beyond the mandatory lunch),
        # so we only exclude pure FOOD from food_ids here.
        pure_food_ids = set(food_ids) - set(
            p.id for p in self.data.places if p.type == PlaceType.FOOD_CAFE
        )
        non_otop_food = [pid for pid in available_ids if pid not in used and pid not in otop_ids and pid not in pure_food_ids]
        savings = self._compute_savings(hub_id, non_otop_food)

        # Step 4: Greedily add places based on savings
        for pid_i, pid_j, saving_val in savings:
            if len(route) >= max_places:
                break
            for pid in [pid_i, pid_j]:
                if pid in used or len(route) >= max_places:
                    continue
                # Check time feasibility before adding
                trial = route + [pid]
                trial_ordered = self._nearest_neighbor_order(hub_id, end_id, trial)
                ev = self.evaluator.evaluate_day(trial_ordered, hub_id, end_id)
                if ev["feasible"]:
                    route.append(pid)
                    used.add(pid)

        # Step 5: Fill remaining slots with best-rated unused places
        # Same exclusion rule: skip OTOP and pure FOOD (FOOD_CAFE allowed as extra slot)
        if len(route) < max_places:
            remaining = [
                pid for pid in available_ids
                if pid not in used and pid not in otop_ids and pid not in pure_food_ids
            ]
            place_map = {p.id: p for p in self.data.places}
            remaining.sort(key=lambda pid: place_map[pid].rate, reverse=True)
            for pid in remaining:
                if len(route) >= max_places:
                    break
                trial = route + [pid]
                trial_ordered = self._nearest_neighbor_order(hub_id, end_id, trial)
                ev = self.evaluator.evaluate_day(trial_ordered, hub_id, end_id)
                if ev["feasible"]:
                    route.append(pid)
                    used.add(pid)

        # Step 6: Order by nearest-neighbor
        route = self._nearest_neighbor_order(hub_id, end_id, route)

        return route

    def _nearest_neighbor_order(self, start_id: str, end_id: str, place_ids: List[str]) -> List[str]:
        """Order places using nearest-neighbor heuristic starting from start_id."""
        if len(place_ids) <= 1:
            return list(place_ids)

        remaining = set(place_ids)
        ordered = []
        current = start_id

        while remaining:
            nearest = min(remaining, key=lambda pid: self.data.get_distance(current, pid))
            ordered.append(nearest)
            remaining.remove(nearest)
            current = nearest

        return ordered

    def optimize(self) -> Route:
        start_time = time.time()
        num_days = self.request.trip_days

        print(f"\n{'='*60}")
        print(f"[SM] START  Saving Method (Clarke-Wright)")
        print(f"[SM] trip_days={num_days}  max_places_per_day={self.request.max_places_per_day}")
        print(f"{'='*60}")

        # Select hotels
        hotel_ids = self._select_hotels()
        depot = self.data.get_depot()

        if self.verbose and hotel_ids:
            hotel_names = []
            for hid in hotel_ids:
                h = next((p for p in self.data.places if p.id == hid), None)
                hotel_names.append(f"{h.name} ({hid})" if h else hid)
            print(f"[SM] Selected hotels: {', '.join(hotel_names)}")

        # Build day endpoint chain: depot -> hotel1 -> hotel2 -> ... -> depot
        endpoints = []
        for day_idx in range(num_days):
            if num_days == 1:
                start_id = depot.id
                end_id = depot.id
            elif day_idx == 0:
                start_id = depot.id
                end_id = hotel_ids[0]
            elif day_idx == num_days - 1:
                start_id = hotel_ids[-1]
                end_id = depot.id
            else:
                start_id = hotel_ids[day_idx - 1]
                end_id = hotel_ids[day_idx]
            endpoints.append((start_id, end_id))

        # Get all candidate place IDs
        candidates = self._get_candidate_places()
        all_candidate_ids = [p.id for p in candidates]
        otop_ids = [p.id for p in self.data.get_otop_places()]
        food_ids = [p.id for p in candidates if p.is_food]

        # Build each day's route sequentially
        used_ids: set = set()
        day_places: List[List[str]] = []

        for day_idx in range(num_days):
            start_id, end_id = endpoints[day_idx]
            available = [pid for pid in all_candidate_ids if pid not in used_ids]

            day_route = self._build_day_route(
                hub_id=start_id,
                end_id=end_id,
                available_ids=available,
                otop_ids=otop_ids,
                food_ids=food_ids,
                max_places=self.request.max_places_per_day,
            )
            day_places.append(day_route)
            used_ids.update(day_route)

            if self.verbose:
                ev = self.evaluator.evaluate_day(day_route, start_id, end_id)
                print(f"[SM] Day {day_idx+1}: {day_route}  dist={ev['distance_km']:.2f}km  time={ev['time_min']:.1f}min  feasible={ev['feasible']}")

        route = Route(day_places, hotel_ids)
        self.best_route = route
        self.best_fitness = self.evaluator.fitness(route)
        self.computation_time = time.time() - start_time

        ev = self.evaluator.evaluate_route(route)
        print(f"[SM] DONE  fitness={self.best_fitness:.4f}  dist={ev['total_distance_km']:.2f}km  time={ev['total_time_min']:.1f}min  co2={ev['total_co2_kg']:.3f}kg  elapsed={self.computation_time:.3f}s\n")

        return self.best_route
