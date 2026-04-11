import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Optional

from backend.app.services.data_loader import DataLoader

router = APIRouter(prefix="/api/v1/files", tags=["files"])

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
INPUTS_DIR = os.path.join(DATA_DIR, "inputs")


def get_data_loader() -> DataLoader:
    from backend.app.main import app_state
    return app_state["data_loader"]


@router.post("/places/import")
async def import_places(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    os.makedirs(INPUTS_DIR, exist_ok=True)
    filepath = os.path.join(INPUTS_DIR, "TravelInfo.csv")
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    loader = get_data_loader()
    places = loader.load_places(filepath)
    validation = loader.validate()

    return {
        "message": "Places imported successfully",
        "total_records": len(places),
        "valid": validation["valid"],
        "errors": validation.get("errors", []),
    }


@router.post("/matrix/import")
async def import_matrix(
    distance_file: Optional[UploadFile] = File(None),
    time_file: Optional[UploadFile] = File(None),
):
    os.makedirs(INPUTS_DIR, exist_ok=True)
    loader = get_data_loader()
    files_imported = []

    for upload, name, mtype in [
        (distance_file, "distance_matrix.csv", "distance"),
        (time_file, "travel_time_matrix.csv", "time"),
    ]:
        if upload:
            filepath = os.path.join(INPUTS_DIR, name)
            content = await upload.read()
            with open(filepath, "wb") as f:
                f.write(content)
            loader.load_matrix_from_csv(filepath, mtype)
            files_imported.append(name)

    return {
        "message": "Matrix files imported",
        "files": files_imported,
        "valid": True,
    }


@router.post("/matrix/google")
async def load_google_matrix(body: dict):
    import re
    
    api_key = body.get("api_key", "").strip()
    
    # Fallback to environment variable if not provided
    if not api_key:
        api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    
    # ทำความสะอาด API key - ลบ whitespace, newline, control characters ทั้งหมด
    api_key = re.sub(r'[\s\r\n\t\x00-\x1f\x7f-\x9f]+', '', api_key)
    
    print(f"[API] Google API Key length: {len(api_key)}")
    print(f"[API] Google API Key preview: {api_key[:20]}...{api_key[-10:] if len(api_key) > 30 else ''}")
    
    if not api_key:
        raise HTTPException(status_code=400, detail="api_key is required (provide in request body or set GOOGLE_API_KEY in .env)")

    loader = get_data_loader()
    if not loader.places:
        raise HTTPException(status_code=400, detail="No places loaded. Import places CSV first.")

    result = loader.load_google_matrices(api_key)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=f"Google API errors: {result['errors'][:3]}")

    return {
        "message": "Google Distance Matrix loaded successfully",
        "api_calls": result["api_calls"],
        "matrix_size": result["matrix_size"],
        "using_google": result["using_google"],
    }


@router.get("/matrix/google/env-key-exists")
async def check_env_key():
    """Check if GOOGLE_API_KEY is set in environment."""
    has_key = bool(os.getenv("GOOGLE_API_KEY", "").strip())
    return {"has_env_key": has_key}


@router.get("/matrix/google/status")
async def google_matrix_status():
    loader = get_data_loader()
    return loader.google_cache_info()


@router.delete("/matrix/google/cache")
async def clear_google_cache():
    import glob
    deleted = []
    for pattern in ["google_distance_matrix.csv", "google_travel_time_matrix.csv"]:
        path = os.path.join(INPUTS_DIR, pattern)
        if os.path.exists(path):
            os.remove(path)
            deleted.append(pattern)
    loader = get_data_loader()
    loader.using_google_api = False
    if loader.places:
        loader._compute_matrices()
    return {"message": "Google cache cleared", "deleted": deleted}


@router.post("/validate")
async def validate_files():
    loader = get_data_loader()
    if not loader.places:
        csv_path = os.path.join(DATA_DIR, "TravelInfo.csv")
        if not os.path.exists(csv_path):
            csv_path = os.path.join(INPUTS_DIR, "TravelInfo.csv")
        if os.path.exists(csv_path):
            loader.load_places(csv_path)

    validation = loader.validate()
    return validation
