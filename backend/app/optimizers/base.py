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
    def __init__(self, day_places: List[List[str]], hotel_ids: List[str]):
        self.day_places = day_places    # day_places[i] = ordered place IDs for day i+1
        self.hotel_ids = hotel_ids      # hotel_ids[i] = hotel after day i+1 (len = num_days - 1)

    @property
    def num_days(self) -> int:
        return len(self.day_places)

    def copy(self) -> "Route":
        return Route(
            [dp.copy() for dp in self.day_places],
            self.hotel_ids.copy(),
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

    def _get_day_endpoints(self, route: Route) -> List[Tuple[str, str]]:
        """Return (start_id, end_id) for each day in the route."""
        depot_id = self.depot.id
        n = route.num_days
        endpoints = []
        for day_idx in range(n):
            if n == 1:
                start_id = depot_id
                end_id = depot_id
            elif day_idx == 0:
                start_id = depot_id
                end_id = route.hotel_ids[0]
            elif day_idx == n - 1:
                start_id = route.hotel_ids[-1]
                end_id = depot_id
            else:
                start_id = route.hotel_ids[day_idx - 1]
                end_id = route.hotel_ids[day_idx]
            endpoints.append((start_id, end_id))
        return endpoints

    def evaluate_route(self, route: Route) -> Dict[str, Any]:
        endpoints = self._get_day_endpoints(route)
        days = []
        total_dist = 0.0
        total_time = 0.0
        total_co2 = 0.0
        all_feasible = True

        for day_idx, (start_id, end_id) in enumerate(endpoints):
            day_eval = self.evaluate_day(route.day_places[day_idx], start_id, end_id)
            days.append(day_eval)
            total_dist += day_eval["distance_km"]
            total_time += day_eval["time_min"]
            total_co2 += day_eval["co2_kg"]
            if not day_eval["feasible"]:
                all_feasible = False

        return {
            "days": days,
            "total_distance_km": total_dist,
            "total_time_min": total_time,
            "total_co2_kg": total_co2,
            "feasible": all_feasible,
        }

    def fitness(self, route: Route) -> float:
        ev = self.evaluate_route(route)
        w_d = self.request.weight_distance
        w_c = self.request.weight_co2
        w_r = getattr(self.request, 'weight_rating', 0.0)

        num_data = len(route.day_places)
        factor1 = 1
        factor2 = 2
        if num_data == 1:
            factor1 = 2
        if num_data == 3:
            factor1 = 0.5
            factor2 = 0.5
        
        dist_norm = ev["total_distance_km"] / (300.0 * factor1)
        # TODO: add number of data to concern
        co2_norm = ev["total_co2_kg"] / (200.0 * factor2)

        # Calculate Collective Rating Benefit (Total Rating relative to Max Capacity)
        place_map = {p.id: p for p in self.data.places}
        all_place_ids = [pid for day in route.day_places for pid in day]
        ratings = [place_map[pid].rate for pid in all_place_ids if pid in place_map]
        avg_rating = float(np.mean(ratings)) if ratings else 0.0
        rating_norm = (5.0 - avg_rating) / 5.0

        cost = w_d * dist_norm + w_c * co2_norm + w_r * rating_norm

        penalty = 0.0
        if not ev["feasible"]:
            penalty += 10.0

        place_map = {p.id: p for p in self.data.places}
        for day_places in route.day_places:
            num_places = len(day_places)
            if num_places < self.request.min_places_per_day:
                penalty += 50.0 * (self.request.min_places_per_day - num_places)
            elif num_places > self.request.max_places_per_day:
                penalty += 50.0 * (num_places - self.request.max_places_per_day)

            otop_count = sum(
                1 for pid in day_places
                if pid in place_map and place_map[pid].type == PlaceType.OTOP
            )
            if otop_count == 0:
                penalty += 50.0
            elif otop_count > 1:
                penalty += 30.0 * (otop_count - 1)

            food_count = sum(
                1 for pid in day_places
                if pid in place_map and place_map[pid].type == PlaceType.FOOD
            )
            if food_count == 0:
                penalty += 50.0

        for day_eval in ev["days"]:
            for sched in day_eval["schedule"]:
                if sched["type"] in (PlaceType.FOOD.value, PlaceType.FOOD_CAFE.value):
                    arrival = sched["arrival_min"]
                    if arrival < 660:
                        penalty += ((660 - arrival) / 10.0) * 2.0
                    elif arrival > 780:
                        penalty += ((arrival - 780) / 10.0) * 2.0

        # Bonus for cafe lifestyle: reward visiting CAFE / FOOD_CAFE places
        if getattr(self.request, 'lifestyle_type', None) and self.request.lifestyle_type.value == "cafe":
            cafe_count = sum(
                1 for pid in all_place_ids
                if pid in place_map and place_map[pid].type in (PlaceType.CAFE, PlaceType.FOOD_CAFE)
            )
            penalty -= 0.05 * cafe_count  # each cafe visit reduces cost (bonus)

        return cost + penalty

    def check_constraints(self, route: Route) -> List[str]:
        violations = []
        all_places = [pid for day in route.day_places for pid in day]
        if len(all_places) != len(set(all_places)):
            violations.append("Duplicate places across days")

        ev = self.evaluate_route(route)
        for day_idx, day_eval in enumerate(ev["days"], 1):
            if not day_eval["feasible"]:
                violations.append(f"Day {day_idx} exceeds time window")

        place_map = {p.id: p for p in self.data.places}
        for day_idx, day_places in enumerate(route.day_places, 1):
            otop_count = sum(
                1 for pid in day_places
                if pid in place_map and place_map[pid].type == PlaceType.OTOP
            )
            if otop_count == 0:
                violations.append(f"Day {day_idx}: missing OTOP visit (need exactly 1)")
            elif otop_count > 1:
                violations.append(f"Day {day_idx}: {otop_count} OTOP visits (need exactly 1)")

            food_count = sum(
                1 for pid in day_places
                if pid in place_map and place_map[pid].type == PlaceType.FOOD
            )
            if food_count == 0:
                violations.append(f"Day {day_idx}: missing Food visit (need at least 1)")

        for day_idx, day_eval in enumerate(ev["days"], 1):
            for sched in day_eval["schedule"]:
                if sched["type"] == PlaceType.FOOD.value:
                    arrival = sched["arrival_min"]
                    if arrival < 660 or arrival > 780:
                        violations.append(f"Day {day_idx}: Food arrival outside 11:00-13:00 window")

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
            preferred = [p for p in tourist if p.type in (PlaceType.CAFE, PlaceType.FOOD_CAFE)]
            others = [p for p in tourist if p.type not in (PlaceType.CAFE, PlaceType.FOOD_CAFE)]
            tourist = preferred + others
        return tourist

    def _generate_random_route(self, rng: np.random.Generator) -> Route:
        all_candidates = self._get_candidate_places()
        hotels = self.data.get_hotels()
        otops = self.data.get_otop_places()
        foods = [p for p in all_candidates if p.type == PlaceType.FOOD]
        num_days = self.request.trip_days

        min_per_day = self.request.min_places_per_day
        max_per_day = self.request.max_places_per_day

        # CAFE = tourist slot; FOOD_CAFE = food slot (mandatory lunch) but also cafe
        non_otop_food = [p for p in all_candidates if p.type not in (PlaceType.OTOP, PlaceType.FOOD, PlaceType.FOOD_CAFE)]

        def pick_non_otop_food(n: int, exclude: set) -> List[Place]:
            pool = [p for p in non_otop_food if p.id not in exclude]
            if not pool:
                return []
            rates = np.array([p.rate for p in pool])
            probs = rates / rates.sum() if rates.sum() > 0 else np.ones(len(pool)) / len(pool)
            size = min(n, len(pool))
            idxs = rng.choice(len(pool), size=size, replace=False, p=probs)
            return [pool[i] for i in idxs]

        otop_pool = list(otops)
        rng.shuffle(otop_pool)

        # FOOD_CAFE counts as food for the mandatory lunch slot
        food_cafe = [p for p in all_candidates if p.type == PlaceType.FOOD_CAFE]
        food_pool = list(foods) + food_cafe
        rng.shuffle(food_pool)

        used_ids: set = set()
        day_places: List[List[str]] = [[] for _ in range(num_days)]

        # Assign 1 OTOP and 1 FOOD per day
        for d in range(num_days):
            if d < len(otop_pool):
                otop = otop_pool[d]
            elif otop_pool:
                otop = otop_pool[d % len(otop_pool)]
            else:
                otop = None
            if otop and otop.id not in used_ids:
                day_places[d].append(otop.id)
                used_ids.add(otop.id)

            if d < len(food_pool):
                food = food_pool[d]
            elif food_pool:
                food = food_pool[d % len(food_pool)]
            else:
                food = None
            if food and food.id not in used_ids:
                day_places[d].append(food.id)
                used_ids.add(food.id)

        # Fill remaining slots per day
        for d in range(num_days):
            target_length = rng.integers(min_per_day, max_per_day + 1)
            fill_count = target_length - len(day_places[d])
            if fill_count > 0:
                fill = pick_non_otop_food(fill_count, used_ids)
                for p in fill:
                    day_places[d].append(p.id)
                    used_ids.add(p.id)
            rng.shuffle(day_places[d])

        # Select hotels (num_days - 1 hotels needed)
        hotel_ids: List[str] = []
        if hotels and num_days > 1:
            for _ in range(num_days - 1):
                h = hotels[rng.integers(0, len(hotels))]
                hotel_ids.append(h.id)

        return Route(day_places, hotel_ids)

    @abstractmethod
    def optimize(self) -> Route:
        pass
        pass
