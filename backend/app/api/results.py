import json
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from backend.app.services.result_manager import ResultManager

router = APIRouter(prefix="/api/v1/results", tags=["results"])


def get_result_manager() -> ResultManager:
    from backend.app.main import app_state
    return app_state["result_manager"]


@router.get("")
async def list_results():
    rm = get_result_manager()
    items = rm.get_results_list()
    return {"items": items}


@router.get("/{result_id}")
async def get_result(result_id: str):
    rm = get_result_manager()
    result = rm.get_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result


@router.post("/import")
async def import_result(file: UploadFile = File(...)):
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only JSON files accepted")
    content = await file.read()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    rm = get_result_manager()
    result_id = rm.import_result(data)
    return {"message": "Result imported", "result_id": result_id, "valid": True}


@router.delete("/{result_id}")
async def delete_result(result_id: str):
    rm = get_result_manager()
    deleted = rm.delete_result(result_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Result not found")
    return {"message": "Result deleted"}


@router.get("/{result_id}/export")
async def export_result(result_id: str, format: str = "json"):
    rm = get_result_manager()
    if format == "json":
        filepath = rm.export_json(result_id)
    elif format == "csv":
        filepath = rm.export_csv(result_id)
    else:
        raise HTTPException(status_code=400, detail="Supported formats: json, csv")

    if not filepath:
        raise HTTPException(status_code=404, detail="Result not found")

    media_type = "application/json" if format == "json" else "text/csv"
    return FileResponse(filepath, media_type=media_type, filename=f"{result_id}.{format}")
