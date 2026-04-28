# API Reference

Base URL: `http://localhost:8000`

Interactive Swagger docs: `http://localhost:8000/docs`

---

## Core Principles & Error Semantics

This API follows consistent design principles to ensure stability and predictability:

1. **Validate at Boundaries:** All external data entering the system via the API is immediately validated against strongly-typed Pydantic schemas (e.g., `OptimizeRequest`). Internal services trust the data after it passes the boundary.
2. **Predictable Naming:** Endpoints use RESTful conventions with predictable path segments (e.g., `/api/v1/routes`, `/api/v1/results`).
3. **Consistent Error Semantics:** All API-level errors are returned with standard HTTP status codes and a consistent JSON shape provided by FastAPI.

**Standard Error Response Format:**
```json
{
  "detail": "Error description or validation message string/array"
}
```

**Common Status Codes:**
- `400 Bad Request`: Client sent invalid data (e.g., wrong file type, missing places).
- `404 Not Found`: Requested resource does not exist (e.g., result ID not found).
- `422 Unprocessable Entity`: Data failed structural validation against the Pydantic schema.
- `500 Internal Server Error`: Server failure (e.g., Google API failure, algorithm crash).

---

## File Import APIs (`/api/v1/files`)

### POST `/api/v1/files/places/import`

Upload a places CSV file (TravelInfo.csv format). Validates data structure and checks for the existence of required place types (Depot, Hotel, OTOP).

**Request**: `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | CSV file containing place details |

**Response** `200 OK`:

```json
{
  "message": "Places imported successfully",
  "total_records": 44,
  "valid": true,
  "errors": []
}
```

---

### POST `/api/v1/files/matrix/import`

Upload custom distance and/or travel time matrix CSV files.

**Request**: `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `distance_file` | File | No | Square matrix CSV (values in km) |
| `time_file` | File | No | Square matrix CSV (values in minutes) |

**Response** `200 OK`:

```json
{
  "message": "Matrix files imported",
  "files": ["distance_matrix.csv", "travel_time_matrix.csv"],
  "valid": true
}
```

---

### POST `/api/v1/files/matrix/google`

Fetch real driving distances and travel times from Google Distance Matrix API. Falls back to Haversine on failure.

**Request**: `application/json`

```json
{
  "api_key": "AIza..." 
}
```

*Note: `api_key` is optional if it is set via the `GOOGLE_API_KEY` environment variable in the backend.*

**Response** `200 OK`:

```json
{
  "message": "Google Distance Matrix loaded successfully",
  "api_calls": 25,
  "matrix_size": 44,
  "using_google": true
}
```

---

### GET `/api/v1/files/matrix/google/env-key-exists`

Check if `GOOGLE_API_KEY` is set in the backend environment.

**Response** `200 OK`:

```json
{
  "has_env_key": true
}
```

---

### GET `/api/v1/files/matrix/google/status`

Check Google matrix cache status.

**Response** `200 OK`:

```json
{
  "cached": true,
  "last_updated": "2026-04-11 14:30:25",
  "using_google": true
}
```

---

### DELETE `/api/v1/files/matrix/google/cache`

Clear cached Google matrices and revert to Haversine calculations.

**Response** `200 OK`:

```json
{
  "message": "Google cache cleared",
  "deleted": ["google_distance_matrix.csv", "google_travel_time_matrix.csv"]
}
```

---

### POST `/api/v1/files/validate`

Validate the currently loaded places data.

**Response** `200 OK`:

```json
{
  "valid": true,
  "errors": [],
  "total_records": 44
}
```

---

## Route Optimization APIs (`/api/v1/routes`)

### POST `/api/v1/routes/optimize`

Run an optimization algorithm based on user constraints and save the generated result.

**Input Schema (`OptimizeRequest`)**: `application/json`

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `trip_days` | integer | `2` | 1-3 | Number of trip days |
| `algorithm` | string | `"ga"` | `sm`, `sa`, `ga`, etc. | Algorithm to run |
| `lifestyle_type` | string | `"all"` | `all`, `culture`, `cafe`, `food` | Lifestyle filter |
| `weight_distance` | float | `0.4` | 0-1 | Fitness distance weight |
| `weight_co2` | float | `0.3` | 0-1 | Fitness CO2 weight |
| `weight_rating` | float | `0.3` | 0-1 | Fitness rating weight |
| `min_places_per_day` | integer | `3` | 1-10 | Minimum attractions per day |
| `max_places_per_day` | integer | `7` | 1-10 | Max attractions per day |
| `start_place_type` | string | `"airport"` | | Fixed starting point type |
| `end_place_type` | string | `"airport"` | | Fixed ending point type |

**Response Schema (`RouteSummary` meta)** `200 OK`:

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

---

### POST `/api/v1/routes/preview-map`

Run optimization and return full map data without saving the result to disk. Useful for quick previews.

**Input Schema (`OptimizeRequest`)**: Same as `/optimize`.

**Response Schema (`RouteResult` subset)** `200 OK`:

```json
{
  "preview": true,
  "map_data": {
    "center": [8.5396, 99.9447],
    "zoom": 11,
    "days": [
      {
        "day_no": 1,
        "color": "#3B82F6",
        "markers": [
          {
            "id": "D1",
            "name": "Nakhon Si Thammarat Airport",
            "lat": 8.5396,
            "lng": 99.9447,
            "type": "Depot",
            "order_in_day": 0,
            "arrival_time": "08:00",
            "departure_time": "08:00"
          }
        ],
        "polyline": [[8.5396, 99.9447], [8.4321, 99.9612]]
      }
    ]
  },
  "summary": {
    "total_distance_km": 124.8,
    "total_time_min": 390.0,
    "total_co2_kg": 17.5,
    "selected_hotel": "ABC Resort",
    "algorithm": "ga",
    "lifestyle_type": "all"
  },
  "days": [
    {
      "day_no": 1,
      "places": [],
      "distance_km": 62.4,
      "time_min": 195.0,
      "co2_kg": 8.75,
      "start": { "id": "D1", "name": "Nakhon Si Thammarat Airport", "lat": 8.5396, "lng": 99.9447 },
      "end": { "id": "H1", "name": "ABC Resort", "lat": 8.4321, "lng": 99.9612 }
    }
  ]
}
```

---

### GET `/api/v1/routes/compare`

Compare multiple optimization algorithms with the same parameters.

**Input Schema (Query Parameters)**:
Same parameters as `OptimizeRequest`, mapped to query string fields, plus an `algorithms` comma-separated list.

**Response Schema (List of `CompareItem`)** `200 OK`:

```json
{
  "items": [
    {
      "algorithm": "ga",
      "result_id": "route_result_2026-04-11_143025",
      "total_distance_km": 124.8,
      "total_time_min": 390.0,
      "total_co2_kg": 17.5,
      "computation_time_sec": 5.123
    },
    {
      "algorithm": "sa",
      "result_id": "route_result_2026-04-11_143030",
      "total_distance_km": 118.2,
      "total_time_min": 405.0,
      "total_co2_kg": 16.8,
      "computation_time_sec": 3.456
    }
  ]
}
```

---

## Result APIs (`/api/v1/results`)

### GET `/api/v1/results`

List all saved results.

**Response** `200 OK`:

```json
{
  "items": [
    {
      "result_id": "route_result_2026-04-11_143025",
      "file_name": "route_result_2026-04-11_143025.json",
      "created_at": "2026-04-11T14:30:25",
      "algorithm": "ga",
      "total_distance_km": 124.8,
      "total_time_min": 390.0,
      "total_co2_kg": 17.5
    }
  ]
}
```

---

### GET `/api/v1/results/{result_id}`

Get the full `RouteResult` object including the day-by-day itinerary and map data.

**Response** `200 OK`: Full `RouteResult` object (see `Data Formats` documentation).
**Response** `404 Not Found`: `{"detail": "Result not found"}`

---

### POST `/api/v1/results/import`

Import a previously exported `RouteResult` JSON file.

**Request**: `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | JSON file containing a `RouteResult` payload |

**Response** `200 OK`:

```json
{
  "message": "Result imported",
  "result_id": "route_result_2026-04-11_143025",
  "valid": true
}
```
**Response** `400 Bad Request`: `{"detail": "Invalid JSON file"}`

---

### DELETE `/api/v1/results/{result_id}`

Delete a saved result and remove it from the manifest.

**Response** `200 OK`: `{"message": "Result deleted"}`
**Response** `404 Not Found`: `{"detail": "Result not found"}`

---

### GET `/api/v1/results/{result_id}/export`

Export a result as a downloadable file.

**Input Schema (Query Parameters)**:

| Parameter | Type | Default | Options |
|-----------|------|---------|---------|
| `format` | string | `"json"` | `json`, `csv` |

**Response** `200 OK`: Raw File Stream (`application/json` or `text/csv`)
**Response** `404 Not Found`: `{"detail": "Result not found"}`

---

## Map APIs (`/api/v1`)

### GET `/api/v1/results/{result_id}/map`

Get map visualization data for a specific result. Extracts `map_data` from the `RouteResult`.

**Response Schema (`MapDay` array inside `map_data`)** `200 OK`:

```json
{
  "center": [8.5396, 99.9447],
  "zoom": 11,
  "days": [
    {
      "day_no": 1,
      "color": "#3B82F6",
      "markers": [
        {
          "id": "D1",
          "name": "Nakhon Si Thammarat Airport",
          "lat": 8.5396,
          "lng": 99.9447,
          "type": "Depot",
          "order_in_day": 0,
          "arrival_time": "08:00",
          "departure_time": "08:00"
        }
      ],
      "polyline": [[8.5396, 99.9447], [8.4321, 99.9612]]
    }
  ]
}
```

---

### GET `/api/v1/map/points`

Get all currently loaded places formatted for map rendering.

**Response Schema (`MapMarker`-like representation of `Place`)** `200 OK`:

```json
{
  "items": [
    {
      "id": "D1",
      "name": "Nakhon Si Thammarat Airport",
      "lat": 8.5396,
      "lng": 99.9447,
      "type": "Depot",
      "rate": 0.0,
      "visit_time": 0,
      "co2": 0.0
    }
  ]
}
```

---

### GET `/api/v1/map/legend`

Get the map legend with standard colors and icons for each place type.

**Response** `200 OK`:

```json
{
  "items": [
    {"type": "Depot",   "color": "#6366F1", "icon": "plane",        "label": "สนามบิน"},
    {"type": "Hotel",   "color": "#F59E0B", "icon": "bed",          "label": "ที่พัก"},
    {"type": "Travel",  "color": "#10B981", "icon": "camera",       "label": "แหล่งท่องเที่ยว"},
    {"type": "Culture", "color": "#8B5CF6", "icon": "landmark",     "label": "วัฒนธรรม"},
    {"type": "OTOP",    "color": "#EF4444", "icon": "shopping-bag", "label": "ผลิตภัณฑ์ชุมชน"}
  ]
}
```