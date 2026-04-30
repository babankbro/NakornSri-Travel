from fastapi import APIRouter, HTTPException

from backend.app.services.result_manager import ResultManager
from backend.app.services.data_loader import DataLoader

router = APIRouter(prefix="/api/v1", tags=["map"])


def get_deps():
    from backend.app.main import app_state
    return app_state["data_loader"], app_state["result_manager"]


@router.get("/results/{result_id}/map")
async def get_result_map(result_id: str):
    data_loader, result_manager = get_deps()
    result = result_manager.get_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result.get("map_data", {})


@router.get("/map/points")
async def get_all_points():
    data_loader, _ = get_deps()
    if not data_loader.places:
        raise HTTPException(status_code=400, detail="No places loaded")
    items = []
    for p in data_loader.places:
        items.append({
            "id": p.id,
            "name": p.name,
            "lat": p.lat,
            "lng": p.lng,
            "type": p.type.value,
            "rate": p.rate,
            "visit_time": p.visit_time,
            "co2": p.co2,
        })
    return {"items": items}


@router.get("/map/legend")
async def get_legend():
    return {
        "items": [
            {"type": "Depot", "color": "#6366F1", "icon": "plane", "label": "สนามบิน"},
            {"type": "Hotel", "color": "#F59E0B", "icon": "bed", "label": "ที่พัก"},
            {"type": "Travel", "color": "#10B981", "icon": "camera", "label": "แหล่งท่องเที่ยว"},
            {"type": "Culture", "color": "#8B5CF6", "icon": "landmark", "label": "วัฒนธรรม"},
            {"type": "OTOP", "color": "#EF4444", "icon": "shopping-bag", "label": "ผลิตภัณฑ์ชุมชน"},
            {"type": "Food", "color": "#EC4899", "icon": "utensils", "label": "ร้านอาหาร"},
            {"type": "Food and Café", "color": "#F43F5E", "icon": "coffee", "label": "ร้านอาหารและคาเฟ่"},
            {"type": "Café", "color": "#14B8A6", "icon": "mug-hot", "label": "คาเฟ่"},
        ]
    }
