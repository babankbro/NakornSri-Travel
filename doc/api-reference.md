# API Reference

Base URL: `http://localhost:8000`

Interactive Swagger docs: `http://localhost:8000/docs`

---

## File Import APIs (`/api/v1/files`)

### POST `/api/v1/files/places/import`

Upload a places CSV file (TravelInfo.csv format).

**Request**: `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | CSV file with columns: Order, ID, Name, LAT, LNG, VisitTime, RATE, CO2, TYPE |

**Response** `200`:

```json
{
  "message": "Places imported successfully",
  "total_records": 44,
  "valid": true,
  "errors": []
}
```

**curl**:

```bash
curl -X POST http://localhost:8000/api/v1/files/places/import \
  -F "file=@TravelInfo.csv"
```

---

### POST `/api/v1/files/matrix/import`

Upload custom distance and/or travel time matrix CSV files.

**Request**: `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `distance_file` | File | No | Square matrix CSV (place IDs as row/column headers, values in km) |
| `time_file` | File | No | Square matrix CSV (values in minutes) |

**Response** `200`:

```json
{
  "message": "Matrix files imported",
  "files": ["distance_matrix.csv", "travel_time_matrix.csv"],
  "valid": true
}
```

---

### POST `/api/v1/files/matrix/google`

Fetch real driving distances and travel times from Google Distance Matrix API.

**Request**: `application/json`

```json
{
  "api_key": "AIza..."
}
```

If `api_key` is empty or omitted, falls back to the `GOOGLE_API_KEY` environment variable.

**Response** `200`:

```json
{
  "message": "Google Distance Matrix loaded successfully",
  "api_calls": 25,
  "matrix_size": 44,
  "using_google": true
}
```

**curl**:

```bash
curl -X POST http://localhost:8000/api/v1/files/matrix/google \
  -H "Content-Type: application/json" \
  -d '{"api_key": "AIza..."}'
```

---

### GET `/api/v1/files/matrix/google/env-key-exists`

Check if `GOOGLE_API_KEY` is set in the environment.

**Response** `200`:

```json
{
  "has_env_key": true
}
```

---

### GET `/api/v1/files/matrix/google/status`

Check Google matrix cache status.

**Response** `200`:

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

**Response** `200`:

```json
{
  "message": "Google cache cleared",
  "deleted": ["google_distance_matrix.csv", "google_travel_time_matrix.csv"]
}
```

---

### POST `/api/v1/files/validate`

Validate the currently loaded places data. Checks for the presence of a depot, hotels, tourist places, and OTOP places.

**Response** `200`:

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

Run an optimization algorithm and save the result.

**Request**: `application/json`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `trip_days` | int (1-2) | `2` | Number of trip days |
| `algorithm` | string | `"ga"` | Algorithm: `sm`, `ga`, `sa`, `sm_alns`, `sa_alns`, `ga_alns`, `lingo` |
| `lifestyle_type` | string | `"all"` | Lifestyle filter: `all`, `culture`, `cafe`, `food` |
| `weight_distance` | float (0-1) | `0.4` | Weight for distance in fitness function |
| `weight_time` | float (0-1) | `0.3` | Weight for time in fitness function |
| `weight_co2` | float (0-1) | `0.3` | Weight for CO2 in fitness function |
| `max_places_per_day` | int (1-10) | `6` | Maximum tourist places to visit per day |
| `start_place_type` | string | `"airport"` | Start point type |
| `end_place_type` | string | `"airport"` | End point type |

**Response** `200`:

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

**curl**:

```bash
curl -X POST http://localhost:8000/api/v1/routes/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "trip_days": 2,
    "algorithm": "sa",
    "lifestyle_type": "culture",
    "weight_distance": 0.4,
    "weight_time": 0.3,
    "weight_co2": 0.3,
    "max_places_per_day": 5
  }'
```

---

### POST `/api/v1/routes/preview-map`

Run optimization and return map data without saving the result to storage.

**Request**: Same as `/optimize`.

**Response** `200`:

```json
{
  "preview": true,
  "map_data": {
    "center": [8.5396, 99.9447],
    "zoom": 11,
    "days": [...]
  },
  "summary": { ... },
  "days": [ ... ]
}
```

---

### GET `/api/v1/routes/compare`

Compare multiple optimization algorithms with the same parameters.

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `algorithms` | string | `"ga,sa"` | Comma-separated algorithm names |
| `trip_days` | int | `2` | Number of trip days |
| `lifestyle_type` | string | `"all"` | Lifestyle filter |
| `weight_distance` | float | `0.4` | Distance weight |
| `weight_time` | float | `0.3` | Time weight |
| `weight_co2` | float | `0.3` | CO2 weight |
| `max_places_per_day` | int | `6` | Max places per day |

**Response** `200`:

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

**curl**:

```bash
curl "http://localhost:8000/api/v1/routes/compare?algorithms=ga,sa,sa_alns&trip_days=2&max_places_per_day=6"
```

> **Note**: The compare endpoint runs each algorithm sequentially and saves all results. This can take significant time with multiple algorithms.

---

## Result APIs (`/api/v1/results`)

### GET `/api/v1/results`

List all saved results (from the manifest file).

**Response** `200`:

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

Get the full result including day-by-day itinerary and map data.

**Response** `200`: Full `RouteResult` object (see [Data Formats](data-formats.md#result-json)).

**Response** `404`: `{"detail": "Result not found"}`

---

### POST `/api/v1/results/import`

Import a previously exported result JSON file.

**Request**: `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | JSON file containing a RouteResult object |

**Response** `200`:

```json
{
  "message": "Result imported",
  "result_id": "route_result_2026-04-11_143025",
  "valid": true
}
```

---

### DELETE `/api/v1/results/{result_id}`

Delete a saved result and remove it from the manifest.

**Response** `200`: `{"message": "Result deleted"}`

**Response** `404`: `{"detail": "Result not found"}`

---

### GET `/api/v1/results/{result_id}/export`

Export a result as a downloadable file.

**Query Parameters**:

| Parameter | Type | Default | Options |
|-----------|------|---------|---------|
| `format` | string | `"json"` | `json`, `csv` |

**curl**:

```bash
# Export as JSON
curl -O http://localhost:8000/api/v1/results/route_result_2026-04-11_143025/export?format=json

# Export as CSV
curl -O http://localhost:8000/api/v1/results/route_result_2026-04-11_143025/export?format=csv
```

---

## Map APIs (`/api/v1`)

### GET `/api/v1/results/{result_id}/map`

Get map visualization data for a specific result.

**Response** `200`:

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
      "polyline": [[8.5396, 99.9447], [8.4321, 99.9612], ...]
    }
  ]
}
```

---

### GET `/api/v1/map/points`

Get all loaded places as map points.

**Response** `200`:

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

Get the map legend with colors and icons for each place type.

**Response** `200`:

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

---

## Error Responses

All endpoints return errors in this format:

```json
{
  "detail": "Error description"
}
```

| Status | Meaning |
|--------|---------|
| `400` | Bad request (missing data, invalid file format, validation error) |
| `404` | Resource not found |
| `500` | Internal server error (algorithm failure, Google API error) |
