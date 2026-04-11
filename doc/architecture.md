# System Architecture

## High-Level Overview

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (index.html + app.js)                         │
│  Tailwind CSS · Leaflet Maps · Vanilla JS               │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP (fetch)
┌────────────────────────▼────────────────────────────────┐
│  FastAPI Application (main.py)                          │
│  CORS · Static Files · Startup Hooks                    │
├─────────────┬──────────┬──────────┬─────────────────────┤
│  files.py   │ routes.py│results.py│ map_api.py          │
│  /files/*   │ /routes/*│/results/*│ /map/*              │
└──────┬──────┴────┬─────┴────┬─────┴──────┬──────────────┘
       │           │          │            │
┌──────▼───────────▼──────────▼────────────▼──────────────┐
│  Services Layer                                          │
│  ┌─────────────┐ ┌──────────────────┐ ┌──────────────┐  │
│  │ DataLoader   │ │RouteOptimizerSvc │ │ResultManager │  │
│  │ CSV + Google │ │ Orchestration    │ │ File CRUD    │  │
│  └──────┬──────┘ └────────┬─────────┘ └──────┬───────┘  │
│         │                 │                   │          │
│  ┌──────▼─────────────────▼──────┐    ┌──────▼───────┐  │
│  │  Optimizers                    │    │  storage/    │  │
│  │  GA · SA · ALNS · Hybrids     │    │  results/    │  │
│  │  base.py (Route, Evaluator)   │    │  manifests/  │  │
│  └───────────────────────────────┘    │  exports/    │  │
│                                       └──────────────┘  │
└─────────────────────────────────────────────────────────┘
       │                                       │
┌──────▼───────┐                       ┌───────▼──────┐
│  data/       │                       │  storage/    │
│  CSV files   │                       │  JSON files  │
└──────────────┘                       └──────────────┘
```

## Request Flow: Optimization

1. User configures parameters in the frontend and clicks "Calculate"
2. Frontend sends `POST /api/v1/routes/optimize` with `OptimizeRequest` body
3. `routes.py` retrieves `DataLoader` and `ResultManager` from `app_state`
4. `RouteOptimizerService.optimize()` is called:
   - Instantiates the appropriate optimizer (GA, SA, SA_ALNS, GA_ALNS)
   - Optimizer generates/evolves routes using the loaded distance/time matrices
   - Returns the best `Route` found
5. `_build_result()` evaluates the best route, generates map data, builds the full result dict
6. `ResultManager.save_result()` writes the result to `storage/results/` and updates the manifest
7. API returns `result_id`, `summary`, and `computation_time_sec`
8. Frontend fetches the full result via `GET /api/v1/results/{result_id}` and renders it

## Backend Layers

### API Layer (`backend/app/api/`)

Four routers, each with a distinct prefix:

| Router | Prefix | Responsibility |
|--------|--------|----------------|
| `files.py` | `/api/v1/files` | CSV import, Google Distance Matrix API, data validation |
| `routes.py` | `/api/v1/routes` | Route optimization, preview, algorithm comparison |
| `results.py` | `/api/v1/results` | Result CRUD, import/export |
| `map_api.py` | `/api/v1` | Map points, route map data, legend |

### Services Layer (`backend/app/services/`)

| Service | Responsibility |
|---------|----------------|
| `DataLoader` | Loads places from CSV, computes distance/time matrices (Haversine or Google API), provides query methods for distances and place lookups |
| `RouteOptimizerService` | Instantiates optimizers, runs optimization, builds result structure with day details and map data |
| `ResultManager` | Saves/loads/deletes results as JSON files, maintains the results manifest, handles JSON and CSV export |

### Optimizers Layer (`backend/app/optimizers/`)

| Module | Class | Description |
|--------|-------|-------------|
| `base.py` | `Route` | Solution representation: `day1_places`, `day2_places`, `hotel_id` |
| `base.py` | `RouteEvaluator` | Evaluates routes: distance, time, CO2, feasibility, fitness score |
| `base.py` | `BaseOptimizer` | Abstract base class with common methods (candidate generation, random route) |
| `ga.py` | `GAOptimizer` | Genetic Algorithm with tournament selection, order crossover, 4 mutation types |
| `sa.py` | `SAOptimizer` | Simulated Annealing with 5 neighborhood move types |
| `alns.py` | `ALNSOperators` | Destroy (random, worst, Shaw) and repair (greedy, random, regret) operators |
| `ga_alns.py` | `GAAlnsOptimizer` | Hybrid: GA evolution + ALNS local search on elite solutions |
| `sa_alns.py` | `SAAlnsOptimizer` | Hybrid: SA acceptance + ALNS destroy/repair with adaptive weights |

### Schemas (`backend/app/schemas/models.py`)

Pydantic models for validation and serialization:

- `Place` — individual location with id, name, lat/lng, visit_time, rate, co2, type
- `PlaceType` — enum: `Depot`, `Hotel`, `Travel`, `Culture`, `OTOP`
- `AlgorithmType` — enum: `sa`, `ga`, `sa_alns`, `ga_alns`, `lingo`
- `LifestyleType` — enum: `all`, `culture`, `cafe`, `food`
- `OptimizeRequest` — request body for optimization
- `RouteResult`, `RouteSummary`, `DayRoute` — result structures
- `MapMarker`, `MapDay` — map visualization data
- `CompareItem` — algorithm comparison result entry

### Utils (`backend/app/utils/distance.py`)

- `haversine(lat1, lng1, lat2, lng2)` — great-circle distance in km
- `compute_distance_matrix(lats, lngs)` — NxN distance matrix
- `compute_travel_time_matrix(distance_matrix)` — converts distance to time at 60 km/h average

## State Management

The application uses a module-level `app_state` dict in `main.py` to hold singleton instances:

```python
app_state = {}

@app.on_event("startup")
async def startup():
    data_loader = DataLoader()
    # ... load data ...
    result_manager = ResultManager()
    app_state["data_loader"] = data_loader
    app_state["result_manager"] = result_manager
```

Routers access these via helper functions:

```python
def get_services():
    from backend.app.main import app_state
    data_loader = app_state["data_loader"]
    result_manager = app_state["result_manager"]
    return ...
```

## File-Based Storage Layout

No database. All persistence uses the filesystem:

```
data/
├── TravelInfo.csv                      # Primary place data (loaded on startup)
└── inputs/
    ├── TravelInfo.csv                  # Uploaded via API
    ├── google_distance_matrix.csv      # Cached Google distances (auto-saved)
    └── google_travel_time_matrix.csv   # Cached Google travel times (auto-saved)

storage/
├── results/
│   ├── route_result_2026-04-11_143025.json   # Individual result files
│   └── ...
├── manifests/
│   └── results_manifest.json           # Index of all results (for quick listing)
└── exports/
    ├── route_result_2026-04-11_143025.json   # Exported copies
    └── route_result_2026-04-11_143025.csv
```

## Distance Matrix Strategy

The system supports three tiers of distance data, with automatic fallback:

```
1. Google Distance Matrix API (most accurate — real driving distances & times)
       │ fallback if no API key or API fails
       ▼
2. Cached Google matrices (CSV files from a previous API fetch)
       │ fallback if no cache exists
       ▼
3. Haversine (straight-line distance, travel time at 60 km/h average)
```

On startup:
- If cached Google matrices exist and match the number of places → use them
- If `GOOGLE_API_KEY` is set in `.env` → fetch from Google API and cache the results
- Otherwise → compute Haversine matrices from lat/lng coordinates

Google API requests are batched (10 origins x 10 destinations per call) to stay within API limits. If individual pairs fail, Haversine is used as a per-pair fallback.

## Frontend Architecture

Single HTML page (`frontend/index.html`) served by FastAPI:

- **Styles**: Tailwind CSS via CDN
- **Maps**: Leaflet 1.9.4 via CDN (OpenStreetMap tiles)
- **Icons**: Font Awesome 6.5 via CDN
- **Logic**: `frontend/js/app.js` (706 lines, vanilla JavaScript)
- **No build step** — served directly as static files

FastAPI mounts the frontend directory and serves `index.html` on `GET /`:

```python
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
async def serve_frontend():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
```
