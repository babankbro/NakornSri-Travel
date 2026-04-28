import time
from datetime import datetime
from typing import Dict, Any, List

from backend.app.schemas.models import (
    OptimizeRequest, AlgorithmType, RouteResult, RouteSummary,
    DayRoute, MapDay, MapMarker,
)
from backend.app.services.data_loader import DataLoader
from backend.app.optimizers.base import Route, RouteEvaluator
from backend.app.optimizers.ga import GAOptimizer
from backend.app.optimizers.sa import SAOptimizer
from backend.app.optimizers.sm import SMOptimizer
from backend.app.optimizers.sa_alns import SAAlnsOptimizer
from backend.app.optimizers.ga_alns import GAAlnsOptimizer
from backend.app.optimizers.sm_alns import SMAlnsOptimizer
from backend.app.optimizers.pure_alns import PureALNSOptimizer
from backend.app.optimizers.moma import MOMAOptimizer

DAY_COLORS = ["#3B82F6", "#EF4444", "#10B981", "#F59E0B"]

def minutes_to_time_str(minutes: float) -> str:
    h = int(minutes) // 60
    m = int(minutes) % 60
    return f"{h:02d}:{m:02d}"


class RouteOptimizerService:
    def __init__(self, data: DataLoader):
        self.data = data

    def optimize(self, request: OptimizeRequest) -> Dict[str, Any]:
        algo = request.algorithm

        if algo == AlgorithmType.SM:
            optimizer = SMOptimizer(self.data, request)
        elif algo == AlgorithmType.GA:
            optimizer = GAOptimizer(self.data, request)
        elif algo == AlgorithmType.SA:
            optimizer = SAOptimizer(self.data, request)
        elif algo == AlgorithmType.ALNS:
            optimizer = PureALNSOptimizer(self.data, request)
        elif algo == AlgorithmType.SM_ALNS:
            optimizer = SMAlnsOptimizer(self.data, request)
        elif algo == AlgorithmType.SA_ALNS:
            optimizer = SAAlnsOptimizer(self.data, request)
        elif algo == AlgorithmType.GA_ALNS:
            optimizer = GAAlnsOptimizer(self.data, request)
        elif algo == AlgorithmType.MOMA:
            optimizer = MOMAOptimizer(self.data, request)
        else:
            raise ValueError(f"Algorithm '{algo}' is not supported")
        
        best_route = optimizer.optimize()
        evaluator = optimizer.evaluator
        evaluation = evaluator.evaluate_route(best_route)

        result = self._build_result(request, best_route, evaluation, optimizer.computation_time)
        return result

    def compare(self, request: OptimizeRequest, algorithms: List[str]) -> List[Dict[str, Any]]:
        results = []
        for algo_str in algorithms:
            req = request.model_copy()
            req.algorithm = AlgorithmType(algo_str)
            result = self.optimize(req)
            results.append({
                "algorithm": algo_str,
                "result_id": result["result_id"],
                "total_distance_km": result["summary"]["total_distance_km"],
                "total_time_min": result["summary"]["total_time_min"],
                "total_co2_kg": result["summary"]["total_co2_kg"],
                "computation_time_sec": result["computation_time_sec"],
            })
        return results

    def _build_result(
        self, request: OptimizeRequest, route: Route,
        evaluation: Dict, computation_time: float
    ) -> Dict[str, Any]:
        now = datetime.now()
        result_id = f"route_result_{now.strftime('%Y-%m-%d_%H%M%S')}"

        # Build hotel name string
        hotel_names = []
        for hid in route.hotel_ids:
            hotel = next((p for p in self.data.places if p.id == hid), None)
            hotel_names.append(hotel.name if hotel else "Unknown")
        selected_hotel = ", ".join(hotel_names) if hotel_names else None

        # Build endpoint chain for each day
        depot = self.data.get_depot()
        num_days = route.num_days
        day_endpoints = []  # (start_place, end_place) for each day
        for day_idx in range(num_days):
            if num_days == 1:
                start_place = depot
                end_place = depot
            elif day_idx == 0:
                start_place = depot
                end_place = next((p for p in self.data.places if p.id == route.hotel_ids[0]), depot)
            elif day_idx == num_days - 1:
                start_place = next((p for p in self.data.places if p.id == route.hotel_ids[-1]), depot)
                end_place = depot
            else:
                start_place = next((p for p in self.data.places if p.id == route.hotel_ids[day_idx - 1]), depot)
                end_place = next((p for p in self.data.places if p.id == route.hotel_ids[day_idx]), depot)
            day_endpoints.append((start_place, end_place))

        days = []
        map_days = []

        for day_idx in range(num_days):
            start_place, end_place = day_endpoints[day_idx]
            day_eval = evaluation["days"][day_idx]
            color = DAY_COLORS[day_idx % len(DAY_COLORS)]

            place_details = []
            markers = []
            polyline = []

            polyline.append([start_place.lat, start_place.lng])
            markers.append(MapMarker(
                id=start_place.id,
                name=start_place.name,
                lat=start_place.lat,
                lng=start_place.lng,
                type=start_place.type.value,
                order_in_day=0,
                arrival_time=minutes_to_time_str(480),
                departure_time=minutes_to_time_str(480),
            ).model_dump())

            for i, sched in enumerate(day_eval["schedule"]):
                # Calculate travel time to next place
                travel_time_to_next = None
                if i < len(day_eval["schedule"]) - 1:
                    next_sched = day_eval["schedule"][i + 1]
                    travel_time_to_next = self.data.get_travel_time(sched["id"], next_sched["id"])
                else:
                    travel_time_to_next = self.data.get_travel_time(sched["id"], end_place.id)

                place_details.append({
                    "order": i + 1,
                    "id": sched["id"],
                    "name": sched["name"],
                    "type": sched["type"],
                    "lat": sched["lat"],
                    "lng": sched["lng"],
                    "co2": sched["co2"],
                    "arrival": minutes_to_time_str(sched["arrival_min"]),
                    "departure": minutes_to_time_str(sched["departure_min"]),
                    "visit_time": sched["visit_time"],
                    "visit_time_min": sched["visit_time"],
                    "travel_time_to_next": round(travel_time_to_next, 1) if travel_time_to_next else None,
                })
                polyline.append([sched["lat"], sched["lng"]])
                markers.append(MapMarker(
                    id=sched["id"],
                    name=sched["name"],
                    lat=sched["lat"],
                    lng=sched["lng"],
                    type=sched["type"],
                    order_in_day=i + 1,
                    arrival_time=minutes_to_time_str(sched["arrival_min"]),
                    departure_time=minutes_to_time_str(sched["departure_min"]),
                ).model_dump())

            polyline.append([end_place.lat, end_place.lng])
            markers.append(MapMarker(
                id=end_place.id,
                name=end_place.name,
                lat=end_place.lat,
                lng=end_place.lng,
                type=end_place.type.value,
                order_in_day=len(day_eval["schedule"]) + 1,
            ).model_dump())

            days.append({
                "day_no": day_idx + 1,
                "places": place_details,
                "distance_km": round(day_eval["distance_km"], 2),
                "time_min": round(day_eval["time_min"], 1),
                "co2_kg": round(day_eval["co2_kg"], 3),
                "start": {"id": start_place.id, "name": start_place.name, "lat": start_place.lat, "lng": start_place.lng},
                "end": {"id": end_place.id, "name": end_place.name, "lat": end_place.lat, "lng": end_place.lng},
            })

            map_days.append({
                "day_no": day_idx + 1,
                "color": color,
                "markers": markers,
                "polyline": polyline,
            })

        all_lats = [p.lat for p in self.data.places]
        all_lngs = [p.lng for p in self.data.places]
        center = [(min(all_lats) + max(all_lats)) / 2, (min(all_lngs) + max(all_lngs)) / 2]

        return {
            "result_id": result_id,
            "created_at": now.isoformat(),
            "request": request.model_dump(),
            "summary": {
                "total_distance_km": round(evaluation["total_distance_km"], 2),
                "total_time_min": round(evaluation["total_time_min"], 1),
                "total_co2_kg": round(evaluation["total_co2_kg"], 3),
                "selected_hotel": selected_hotel,
                "algorithm": request.algorithm.value,
                "lifestyle_type": request.lifestyle_type.value,
            },
            "days": days,
            "map_data": {
                "center": center,
                "zoom": 11,
                "days": map_days,
            },
            "computation_time_sec": round(computation_time, 3),
        }