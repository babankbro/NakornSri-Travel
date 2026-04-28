import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.app.services.data_loader import DataLoader
from backend.app.services.result_manager import ResultManager
from backend.app.api.files import router as files_router
from backend.app.api.routes import router as routes_router
from backend.app.api.results import router as results_router
from backend.app.api.map_api import router as map_router

# Load environment variables
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
FRONTEND_DIR = os.path.join(PROJECT_DIR, "frontend")
DATA_DIR = os.path.join(PROJECT_DIR, "data")

app = FastAPI(
    title="Travel Route File-Based System",
    description="ระบบวางแผนเส้นทางท่องเที่ยว แบบ File-Based",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app_state = {}


@app.on_event("startup")
async def startup():
    data_loader = DataLoader()
    csv_path = os.path.join(DATA_DIR, "TravelInfo_v2.csv")
    if os.path.exists(csv_path):
        data_loader.load_places(csv_path)
        print(f"Loaded {len(data_loader.places)} places from {csv_path}")
    else:
        print(f"Warning: {csv_path} not found. Upload CSV via API.")

    if data_loader.places:
        cached = data_loader.load_cached_google_matrices()
        if cached:
            print("[Startup] Using cached Google Distance matrices.")
        else:
            print("[Startup] No Google cache found — using Haversine matrices.")
            
            # ตรวจสอบว่ามี API key ใน .env หรือไม่
            google_api_key = os.getenv("GOOGLE_API_KEY", "").strip()
            if google_api_key:
                print("[Startup] Found GOOGLE_API_KEY in .env — fetching from Google API...")
                try:
                    result = data_loader.load_google_matrices(google_api_key)
                    if result["success"]:
                        print(f"[Startup] ✅ Google matrices loaded successfully ({result['api_calls']} API calls)")
                    else:
                        print(f"[Startup] ⚠️ Google API errors: {result['errors'][:3]}")
                        print("[Startup] Falling back to Haversine matrices.")
                except Exception as e:
                    print(f"[Startup] ❌ Failed to load Google matrices: {e}")
                    print("[Startup] Falling back to Haversine matrices.")
            else:
                print("[Startup] No GOOGLE_API_KEY in .env — add it to auto-fetch on startup.")

    result_manager = ResultManager()

    app_state["data_loader"] = data_loader
    app_state["result_manager"] = result_manager


app.include_router(files_router)
app.include_router(routes_router)
app.include_router(results_router)
app.include_router(map_router)

if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def serve_frontend():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Travel Route File-Based System API", "docs": "/docs"}
