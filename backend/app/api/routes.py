from fastapi import APIRouter, HTTPException
from typing import List, Optional

from backend.app.schemas.models import OptimizeRequest, AlgorithmType
from backend.app.services.route_optimizer import RouteOptimizerService
from backend.app.services.result_manager import ResultManager

router = APIRouter(prefix="/api/v1/routes", tags=["routes"])


def get_services():
    from backend.app.main import app_state
    data_loader = app_state["data_loader"]
    result_manager = app_state["result_manager"]
    optimizer_service = RouteOptimizerService(data_loader)
    return optimizer_service, result_manager, data_loader


@router.post("/optimize")
async def optimize_route(request: OptimizeRequest):
    optimizer_service, result_manager, data_loader = get_services()

    if not data_loader.places:
        raise HTTPException(status_code=400, detail="No places data loaded. Import places CSV first.")

    try:
        result = optimizer_service.optimize(request)
        result_id = result_manager.save_result(result)
        return {
            "result_id": result["result_id"],
            "file_name": f"{result['result_id']}.json",
            "summary": result["summary"],
            "computation_time_sec": result.get("computation_time_sec", 0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/preview-map")
async def preview_map(request: OptimizeRequest):
    optimizer_service, _, data_loader = get_services()

    if not data_loader.places:
        raise HTTPException(status_code=400, detail="No places data loaded.")

    try:
        result = optimizer_service.optimize(request)
        return {
            "preview": True,
            "map_data": result["map_data"],
            "summary": result["summary"],
            "days": result["days"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compare")
async def compare_algorithms(
    algorithms: str = "ga,sa",
    trip_days: int = 2,
    lifestyle_type: str = "all",
    weight_distance: float = 0.4,
    weight_co2: float = 0.3,
    weight_rating: float = 0.3,
    min_places_per_day: int = 4,
    max_places_per_day: int = 6,
):
    optimizer_service, result_manager, data_loader = get_services()

    if not data_loader.places:
        raise HTTPException(status_code=400, detail="No places data loaded.")

    algo_list = [a.strip() for a in algorithms.split(",")]
    request = OptimizeRequest(
        trip_days=trip_days,
        algorithm=AlgorithmType(algo_list[0]),
        lifestyle_type=lifestyle_type,
        weight_distance=weight_distance,
        weight_co2=weight_co2,
        weight_rating=weight_rating,
        min_places_per_day=min_places_per_day,
        max_places_per_day=max_places_per_day,
    )

    try:
        results = optimizer_service.compare(request, algo_list)
        for r in results:
            full_result = optimizer_service.optimize(
                request.model_copy(update={"algorithm": AlgorithmType(r["algorithm"])})
            )
            result_manager.save_result(full_result)
        return {"items": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
