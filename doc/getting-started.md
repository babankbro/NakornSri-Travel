# Getting Started

## Prerequisites

- **Python 3.11** (recommended via conda or standalone)
- **pip** or **conda** for package management
- **Google API Key** (optional) — for real-world distance/time data from Google Distance Matrix API

## Installation

### Option A: conda (recommended)

```bash
conda env create -f environment.yml
conda activate travel-route
```

### Option B: pip

```bash
pip install -r requirements.txt
```

### Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | 0.111.0 | Web framework |
| uvicorn | 0.30.1 | ASGI server |
| pandas | 2.2.2 | CSV data processing |
| numpy | 1.26.4 | Matrix operations |
| pydantic | 2.7.4 | Data validation |
| python-multipart | 0.0.9 | File upload handling |
| jinja2 | 3.1.4 | Template engine |
| aiofiles | 24.1.0 | Async file I/O |
| python-dotenv | 1.0.0 | Environment variable loading |

## Environment Setup

Copy the example environment file and edit it:

```bash
cp .env.example .env
```

The `.env` file supports:

```env
# Google Distance Matrix API Key (optional)
# Get yours at: https://console.cloud.google.com/apis/credentials
# Enable "Distance Matrix API" in your Google Cloud project
GOOGLE_API_KEY=your_api_key_here

# Auto-load cached Google matrices on startup
AUTO_LOAD_GOOGLE_CACHE=true
```

Without a Google API key, the system uses **Haversine** (straight-line) distances as a fallback. Google API provides real driving distances and times.

## Running the Server

```bash
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

On startup, the server:

1. Loads `data/TravelInfo.csv` if it exists (the primary places dataset)
2. Attempts to load cached Google matrices from `data/inputs/`
3. If `GOOGLE_API_KEY` is set in `.env` and no cache exists, fetches from Google API
4. Falls back to Haversine distance matrices if no Google data is available

## Accessing the Application

| URL | Description |
|-----|-------------|
| http://localhost:8000 | Web frontend (main UI) |
| http://localhost:8000/docs | Swagger API documentation (interactive) |
| http://localhost:8000/redoc | ReDoc API documentation (read-only) |

## First Optimization

### Via the Web UI

1. Open http://localhost:8000
2. Ensure the status indicator shows places are loaded (green dot)
3. In the **Optimize** tab, configure:
   - Trip days: 2
   - Algorithm: GA (Genetic Algorithm)
   - Lifestyle: All
   - Places per day (Min-Max): 3-7
   - Weights: Distance 0.4, CO2 0.3, Rating 0.3
4. Click **"คำนวณเส้นทาง"** (Calculate Route)
5. View the optimized route on the map and in the day-by-day itinerary

### Via curl

```bash
curl -X POST http://localhost:8000/api/v1/routes/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "trip_days": 2,
    "algorithm": "ga",
    "lifestyle_type": "all",
    "weight_distance": 0.4,
    "weight_co2": 0.3,
    "weight_rating": 0.3,
    "min_places_per_day": 3,
    "max_places_per_day": 7
  }'
```

Response:

```json
{
  "result_id": "route_result_2026-04-11_143025",
  "file_name": "route_result_2026-04-11_143025.json",
  "summary": {
    "total_distance_km": 124.8,
    "total_time_min": 390.0,
    "total_co2_kg": 17.5,
    "selected_hotel": "ABC Resort",
    "algorithm": "ga",
    "lifestyle_type": "all"
  },
  "computation_time_sec": 5.123
}
```

## Loading Data

### Automatic (on startup)

Place your `TravelInfo.csv` in the `data/` directory. The server loads it automatically on startup.

### Manual (via API)

Upload a CSV file through the **Data Import** tab in the UI, or via API:

```bash
curl -X POST http://localhost:8000/api/v1/files/places/import \
  -F "file=@TravelInfo.csv"
```

## Testing

A basic test script is provided:

```bash
# Start the server first, then in another terminal:
python test_api.py
```

This runs optimization with GA and SA algorithms and validates OTOP constraints and CO2 calculations.

## Project Directory Layout

```
travel-route-file-system/
├── backend/
│   └── app/
│       ├── main.py              # FastAPI app, startup, state management
│       ├── api/                  # API endpoint routers
│       │   ├── routes.py         #   /api/v1/routes/* (optimize, preview, compare)
│       │   ├── files.py          #   /api/v1/files/*  (CSV import, Google API)
│       │   ├── results.py        #   /api/v1/results/* (CRUD, export)
│       │   └── map_api.py        #   /api/v1/map/*    (points, legend)
│       ├── optimizers/           # Optimization algorithms
│       │   ├── base.py           #   Route, RouteEvaluator, BaseOptimizer
│       │   ├── ga.py             #   Genetic Algorithm
│       │   ├── sa.py             #   Simulated Annealing
│       │   ├── alns.py           #   ALNS destroy/repair operators
│       │   ├── ga_alns.py        #   GA + ALNS hybrid
│       │   └── sa_alns.py        #   SA + ALNS hybrid
│       ├── services/             # Business logic
│       │   ├── data_loader.py    #   CSV loading, matrix computation, Google API
│       │   ├── route_optimizer.py#   Optimization orchestration
│       │   └── result_manager.py #   File-based result storage
│       ├── schemas/
│       │   └── models.py         #   Pydantic models (Place, OptimizeRequest, etc.)
│       └── utils/
│           └── distance.py       #   Haversine distance, travel time calculation
├── frontend/
│   ├── index.html                # Single-page UI (Tailwind CSS)
│   └── js/app.js                 # All frontend logic (Leaflet maps, API calls)
├── data/                         # Runtime data (created automatically)
│   ├── TravelInfo.csv            #   Primary places dataset
│   └── inputs/                   #   Uploaded CSVs, Google matrix cache
├── storage/                      # Runtime storage (created automatically)
│   ├── results/                  #   Individual result JSON files
│   ├── manifests/                #   results_manifest.json (result index)
│   └── exports/                  #   Exported JSON/CSV files
├── doc/                          # Documentation
├── .env.example                  # Environment variable template
├── requirements.txt              # pip dependencies
├── environment.yml               # conda environment spec
└── test_api.py                   # Basic API test script
```
