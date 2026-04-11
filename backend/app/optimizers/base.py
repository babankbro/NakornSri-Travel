import time
import numpy as np
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple

from backend.app.schemas.models import Place, PlaceType, OptimizeRequest
from backend.app.services.data_loader import DataLoader


DAY_START_MINUTES = 480   # 08:00
DAY_END_MINUTES = 1020    # 17:00
LUNCH_AFTER_N_PLACES = 3
LUNCH_DURATION_MINUTES = 60


class Route:
    def __init__(self, day1_places: List[str], day2_places: List[str], hotel_id: str):
        self.day1_places = day1_places
        self.day2_places = day2_places
        self.hotel_id = hotel_id

    def copy(self) -> "Route":
        return Route(
            self.day1_places.copy(),
            self.day2_places.copy(),
            self.hotel_id,
        )


class RouteEvaluator:
    def __init__(self, data: DataLoader, request: OptimizeRequest):
        self.data = data
        self.request = request
        self.depot = data.get_depot()

    def evaluate_day(self, sequence: List[str], start_id: str, end_id: str) -> Dict[str, Any]:
        total_dist = 0.0
        total_travel_time = 0.0
        total_co2 = 0.0
        current_time = DAY_START_MINUTES
        places_visited = 0
        schedule = []

        prev_id = start_id
        for pid in sequence:
            travel_dist = self.data.get_distance(prev_id, pid)
            travel_time = self.data.get_travel_time(prev_id, pid)

            total_dist += travel_dist
            total_travel_time += travel_time
            current_time += travel_time

            place = next(p for p in self.data.places if p.id == pid)
            arrival = current_time
            visit_dur = place.visit_time if place.visit_time > 0 else 45
            departure = arrival + visit_dur
            current_time = departure
            places_visited += 1

            total_co2 += place.co2

            schedule.append({
                "id": pid,
                "name": place.name,
                "type": place.type.value,
                "lat": place.lat,
                "lng": place.lng,
                "co2": place.co2,
                "arrival_min": arrival,
                "departure_min": departure,
                "visit_time": visit_dur,
            })

            if places_visited > 0 and places_visited % LUNCH_AFTER_N_PLACES == 0:
                current_time += LUNCH_DURATION_MINUTES

            prev_id = pid

        travel_dist = self.data.get_distance(prev_id, end_id)
        travel_time = self.data.get_travel_time(prev_id, end_id)
        total_dist += travel_dist
        total_travel_time += travel_time
        current_time += travel_time

        return {
            "distance_km": total_dist,
            "time_min": current_time - DAY_START_MINUTES,
            "co2_kg": total_co2,
            "schedule": schedule,
            "end_time_min": current_time,
            "feasible": current_time <= DAY_END_MINUTES,
        }

    def evaluate_route(self, route: Route) -> Dict[str, Any]:
        depot_id = self.depot.id
        hotel_id = route.hotel_id

        day1 = self.evaluate_day(route.day1_places, depot_id, hotel_id)
        day2 = self.evaluate_day(route.day2_places, hotel_id, depot_id)

        total_dist = day1["distance_km"] + day2["distance_km"]
        total_time = day1["time_min"] + day2["time_min"]
        total_co2 = day1["co2_kg"] + day2["co2_kg"]

        return {
            "day1": day1,
            "day2": day2,
            "total_distance_km": total_dist,
            "total_time_min": total_time,
            "total_co2_kg": total_co2,
            "feasible": day1["feasible"] and day2["feasible"],
        }

    def fitness(self, route: Route) -> float:
        ev = self.evaluate_route(route)
        w_d = self.request.weight_distance
        w_t = self.request.weight_time
        w_c = self.request.weight_co2

        dist_norm = ev["total_distance_km"] / 200.0
        time_norm = ev["total_time_min"] / 600.0
        co2_norm = ev["total_co2_kg"] / 30.0

        cost = w_d * dist_norm + w_t * time_norm + w_c * co2_norm

        penalty = 0.0
        if not ev["feasible"]:
            penalty += 10.0

        place_map = {p.id: p for p in self.data.places}
        for day_places in [route.day1_places, route.day2_places]:
            otop_count = sum(
                1 for pid in day_places
                if pid in place_map and place_map[pid].type == PlaceType.OTOP
            )
            if otop_count == 0:
                penalty += 5.0
            elif otop_count > 1:
                penalty += 3.0 * (otop_count - 1)

        return cost + penalty

    def check_constraints(self, route: Route) -> List[str]:
        violations = []
        all_places = route.day1_places + route.day2_places
        if len(all_places) != len(set(all_places)):
            violations.append("Duplicate places across days")

        ev = self.evaluate_route(route)
        if not ev["day1"]["feasible"]:
            violations.append("Day 1 exceeds time window")
        if not ev["day2"]["feasible"]:
            violations.append("Day 2 exceeds time window")

        place_map = {p.id: p for p in self.data.places}
        for day_idx, day_places in enumerate([route.day1_places, route.day2_places], 1):
            otop_count = sum(
                1 for pid in day_places
                if pid in place_map and place_map[pid].type == PlaceType.OTOP
            )
            if otop_count == 0:
                violations.append(f"Day {day_idx}: missing OTOP visit (need exactly 1)")
            elif otop_count > 1:
                violations.append(f"Day {day_idx}: {otop_count} OTOP visits (need exactly 1)")

        return violations


class BaseOptimizer(ABC):
    def __init__(self, data: DataLoader, request: OptimizeRequest):
        self.data = data
        self.request = request
        self.evaluator = RouteEvaluator(data, request)
        self.best_route: Optional[Route] = None
        self.best_fitness: float = float("inf")
        self.computation_time: float = 0.0

    def _get_candidate_places(self) -> List[Place]:
        tourist = self.data.get_tourist_places()
        if self.request.lifestyle_type.value == "culture":
            preferred = [p for p in tourist if p.type == PlaceType.CULTURE]
            others = [p for p in tourist if p.type != PlaceType.CULTURE]
            tourist = preferred + others
        elif self.request.lifestyle_type.value == "cafe":
            preferred = [p for p in tourist if p.type == PlaceType.TRAVEL]
            others = [p for p in tourist if p.type != PlaceType.TRAVEL]
            tourist = preferred + others
        return tourist

    def _generate_random_route(self, rng: np.random.Generator) -> Route:
        all_candidates = self._get_candidate_places()
        hotels = self.data.get_hotels()
        otops = self.data.get_otop_places()

        max_per_day = self.request.max_places_per_day

        non_otop = [p for p in all_candidates if p.type != PlaceType.OTOP]

        def pick_non_otop(n: int, exclude: set) -> List[Place]:
            pool = [p for p in non_otop if p.id not in exclude]
            if not pool:
                return []
            rates = np.array([p.rate for p in pool])
            probs = rates / rates.sum() if rates.sum() > 0 else np.ones(len(pool)) / len(pool)
            size = min(n, len(pool))
            idxs = rng.choice(len(pool), size=size, replace=False, p=probs)
            return [pool[i] for i in idxs]

        otop_pool = list(otops)
        rng.shuffle(otop_pool)

        used_ids: set = set()

        otop1 = otop_pool[0] if len(otop_pool) >= 1 else None
        otop2 = otop_pool[1] if len(otop_pool) >= 2 else (otop_pool[0] if otop_pool else None)

        day1: List[str] = []
        day2: List[str] = []

        if otop1:
            day1.append(otop1.id)
            used_ids.add(otop1.id)
        if otop2 and otop2.id not in used_ids:
            day2.append(otop2.id)
            used_ids.add(otop2.id)

        fill1 = pick_non_otop(max_per_day - len(day1), used_ids)
        for p in fill1:
            day1.append(p.id)
            used_ids.add(p.id)

        fill2 = pick_non_otop(max_per_day - len(day2), used_ids)
        for p in fill2:
            day2.append(p.id)
            used_ids.add(p.id)

        rng.shuffle(day1)
        rng.shuffle(day2)

        hotel = hotels[rng.integers(0, len(hotels))] if hotels else None
        hotel_id = hotel.id if hotel else "H1"

        return Route(day1, day2, hotel_id)

    @abstractmethod
    def optimize(self) -> Route:
        pass
