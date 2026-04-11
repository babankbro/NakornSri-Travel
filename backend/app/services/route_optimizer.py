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
        elif algo == AlgorithmType.SM_ALNS:
            optimizer = SMAlnsOptimizer(self.data, request)
        elif algo == AlgorithmType.SA_ALNS:
            optimizer = SAAlnsOptimizer(self.data, request)
        elif algo == AlgorithmType.GA_ALNS:
            optimizer = GAAlnsOptimizer(self.data, request)
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

        hotel = next((p for p in self.data.places if p.id == route.hotel_id), None)
        hotel_name = hotel.name if hotel else "Unknown"

        days = []
        map_days = []
        depot = self.data.get_depot()

        for day_idx, (day_key, day_places, start_place, end_place) in enumerate([
            ("day1", route.day1_places, depot, hotel),
            ("day2", route.day2_places, hotel, depot),
        ], 1):
            day_eval = evaluation[day_key]
            color = DAY_COLORS[(day_idx - 1) % len(DAY_COLORS)]

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
                # คำนวณเวลาเดินทางไปสถานที่ถัดไป
                travel_time_to_next = None
                if i < len(day_eval["schedule"]) - 1:
                    # ไปสถานที่ถัดไป
                    next_sched = day_eval["schedule"][i + 1]
                    travel_time_to_next = self.data.get_travel_time(sched["id"], next_sched["id"])
                else:
                    # สถานที่สุดท้าย ไปที่พัก/depot
                    travel_time_to_next = self.data.get_travel_time(sched["id"], end_place.id)
                
                place_details.append({
                    "order": i + 1,
                    "id": sched["id"],
                    "name": sched["name"],
                    "type": sched["type"],
                    "lat": sched["lat"],
                    "lng": sched["lng"],
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
                "day_no": day_idx,
                "places": place_details,
                "distance_km": round(day_eval["distance_km"], 2),
                "time_min": round(day_eval["time_min"], 1),
                "co2_kg": round(day_eval["co2_kg"], 3),
                "start": {"id": start_place.id, "name": start_place.name, "lat": start_place.lat, "lng": start_place.lng},
                "end": {"id": end_place.id, "name": end_place.name, "lat": end_place.lat, "lng": end_place.lng},
            })

            map_days.append({
                "day_no": day_idx,
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
                "selected_hotel": hotel_name,
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
