# Data Formats

## Input Files

### TravelInfo.csv (Places Data)

The primary input file containing all locations. Loaded on startup from `data/TravelInfo.csv` or uploaded via the API.

#### Columns

| Column | Type | Description |
|--------|------|-------------|
| `Order` | int | Sequential ordering number |
| `ID` | string | Unique place identifier (e.g., `D1`, `H1`, `T1`, `C1`, `O1`) |
| `Name` | string | Place name (Thai or English) |
| `LAT` | float | Latitude coordinate |
| `LNG` | float | Longitude coordinate |
| `VisitTime` | int | Average visit duration in minutes (0 for non-visitable like Depot) |
| `RATE` | float | Popularity/preference rating (higher = more likely to be selected) |
| `CO2` | float | CO2 emission value associated with the place (kg) |
| `TYPE` | string | Place type (see below) |

#### Place Types

| Type | ID Prefix | Description | Role in Route |
|------|-----------|-------------|---------------|
| `Depot` | D | Airport / start-end point | Fixed start and end of the trip |
| `Hotel` | H | Accommodation | Overnight stay between Day 1 and Day 2 |
| `Travel` | T | Tourist attraction | Visitable place (general tourism) |
| `Culture` | C | Cultural site | Visitable place (cultural tourism) |
| `OTOP` | O | Community product shop | Visitable place (must visit exactly 1 per day) |
| `Food` | F | Restaurant | Satisfies lunch constraint |
| `Café` | CF | Coffee shop | Prioritized in Cafe Lifestyle |
| `Food and Café` | FC | Restaurant & Café | Satisfies lunch AND prioritized in Cafe Lifestyle |

#### Example

```csv
Order,ID,Name,LAT,LNG,VisitTime,RATE,CO2,TYPE
1,D1,สนามบินนครศรีธรรมราช,8.5396,99.9447,0,0,0,Depot
2,H1,โรงแรม A,8.4321,99.9612,0,4.5,0.5,Hotel
3,T1,วัดพระมหาธาตุ,8.4113,99.9668,45,4.8,1.2,Travel
4,FC1,คาเฟ่ริมน้ำ,8.3987,99.9534,60,4.2,0.8,Food and Café
5,O1,ผ้าทอนาหมื่นศรี,8.3654,99.9123,45,3.9,0.6,OTOP
```

#### Validation Requirements

The system validates that the CSV contains:
- At least **1 Depot** (airport)
- At least **1 Hotel**
- At least **1 tourist place** (Travel, Culture, or OTOP)
- At least **1 OTOP place** (required by the constraint: 1 OTOP per day)
- At least **1 food place** (Food or Food and Café)

---

### Distance Matrix CSV

Optional. Square matrix with place IDs as both row and column headers. Values represent driving distance in **kilometers**.

```csv
,D1,H1,T1,FC1,O1
D1,0,12.5,8.3,15.2,22.1
H1,12.5,0,5.1,9.8,18.4
T1,8.3,5.1,0,7.2,14.6
FC1,15.2,9.8,7.2,0,11.3
O1,22.1,18.4,14.6,11.3,0
```

### Travel Time Matrix CSV

Optional. Same format as distance matrix but values represent travel time in **minutes**.

If these matrices are not provided, the system computes them from coordinates using Haversine distance and an assumed average speed of 60 km/h.

---

### Google Cache Files

When the Google Distance Matrix API is used, results are automatically cached as:

- `data/inputs/google_distance_matrix.csv` — real driving distances (km)
- `data/inputs/google_travel_time_matrix.csv` — real driving times (min)

Same format as the manual matrix CSVs. Auto-loaded on server startup if present. If the number of places changes (CSV re-import), the cache becomes invalid and is ignored.

---

## Output Files

### Result JSON

Each optimization run produces a JSON file saved to `storage/results/`.

#### Full Schema

```json
{
  "result_id": "route_result_2026-04-11_143025",
  "created_at": "2026-04-11T14:30:25.123456",
  "request": {
    "trip_days": 2,
    "algorithm": "ga",
    "lifestyle_type": "all",
    "weight_distance": 0.4,
    "weight_co2": 0.3,
    "weight_rating": 0.3,
    "min_places_per_day": 5,
    "max_places_per_day": 7,
    "start_place_type": "airport",
    "end_place_type": "airport"
  },
  "summary": {
    "total_distance_km": 124.80,
    "total_time_min": 390.0,
    "total_co2_kg": 17.500,
    "average_rating": 4.65,
    "total_rating_score": 62.4,
    "max_rating_score": 70.0,
    "selected_hotel": "โรงแรม A",
    "algorithm": "ga",
    "lifestyle_type": "all"
  },
  "days": [
    {
      "day_no": 1,
      "places": [
        {
          "order": 1,
          "id": "T1",
          "name": "วัดพระมหาธาตุ",
          "type": "Travel",
          "lat": 8.4113,
          "lng": 99.9668,
          "rate": 4.8,
          "arrival": "08:25",
          "departure": "09:10",
          "visit_time": 45,
          "visit_time_min": 45,
          "travel_time_to_next": 12.3
        }
      ],
      "distance_km": 62.40,
      "time_min": 195.0,
      "co2_kg": 8.750,
      "start": {"id": "D1", "name": "สนามบินนครศรีธรรมราช", "lat": 8.5396, "lng": 99.9447},
      "end": {"id": "H1", "name": "โรงแรม A", "lat": 8.4321, "lng": 99.9612}
    },
    {
      "day_no": 2,
      "places": [...],
      "distance_km": 62.40,
      "time_min": 195.0,
      "co2_kg": 8.750,
      "start": {"id": "H1", "name": "โรงแรม A", "lat": 8.4321, "lng": 99.9612},
      "end": {"id": "D1", "name": "สนามบินนครศรีธรรมราช", "lat": 8.5396, "lng": 99.9447}
    }
  ],
  "map_data": {
    "center": [8.45, 99.95],
    "zoom": 11,
    "days": [
      {
        "day_no": 1,
        "color": "#3B82F6",
        "markers": [
          {
            "id": "D1",
            "name": "สนามบินนครศรีธรรมราช",
            "lat": 8.5396,
            "lng": 99.9447,
            "type": "Depot",
            "order_in_day": 0,
            "arrival_time": "08:00",
            "departure_time": "08:00"
          }
        ],
        "polyline": [[8.5396, 99.9447], [8.4113, 99.9668], ...]
      }
    ]
  },
  "computation_time_sec": 5.123
}
```

#### Key Fields

| Field | Description |
|-------|-------------|
| `result_id` | Unique ID: `route_result_YYYY-MM-DD_HHMMSS` |
| `created_at` | ISO 8601 timestamp |
| `request` | Echo of the `OptimizeRequest` that produced this result |
| `summary` | Aggregated metrics across all days |
| `summary.average_rating` | Mean rating across all visited places |
| `summary.total_rating_score` | Sum of ratings across all visited places |
| `summary.max_rating_score` | Capacity-based max rating (`trip_days * max_places_per_day * 5.0`) |
| `days[].places[]` | Ordered list of visited places with arrival/departure times |
| `days[].places[].rate` | The popularity rating of this specific place |
| `days[].places[].travel_time_to_next` | Travel time in minutes to the next place (or to the day's end point) |
| `days[].start` / `days[].end` | Day start point (Depot or Hotel) and end point |
| `map_data` | Pre-computed data for Leaflet map rendering |
| `map_data.days[].polyline` | Array of `[lat, lng]` pairs for drawing route lines |
| `computation_time_sec` | Time taken by the optimizer (excludes result building) |

---

### Results Manifest

`storage/manifests/results_manifest.json` — an index of all saved results for quick listing.

```json
{
  "results": [
    {
      "result_id": "route_result_2026-04-11_143025",
      "file_name": "route_result_2026-04-11_143025.json",
      "created_at": "2026-04-11T14:30:25.123456",
      "algorithm": "ga",
      "total_distance_km": 124.80,
      "total_time_min": 390.0,
      "total_co2_kg": 17.500,
      "average_rating": 4.65,
      "total_rating_score": 62.4,
      "max_rating_score": 70.0
    }
  ]
}
```

This file is maintained automatically by `ResultManager`. New results are appended; deleted results are removed.

---

### Export CSV

When exporting a result as CSV (`GET /api/v1/results/{id}/export?format=csv`), the format is:

```csv
Day,Order,ID,Name,Type,Arrival,Departure,Visit_Time_Min
1,1,T1,วัดพระมหาธาตุ,Travel,08:25,09:10,45
1,2,C1,หนังตะลุง,Culture,09:22,10:22,60
1,3,O1,ผ้าทอนาหมื่นศรี,OTOP,10:40,11:25,45
2,1,T5,...

Summary
Total Distance (km),124.80
Total Time (min),390.0
Total CO2 (kg),17.500
Average Rating,4.65
Total Rating Score,62.4
Hotel,โรงแรม A
Algorithm,ga
```

The CSV uses UTF-8 with BOM encoding (`utf-8-sig`) for proper Thai character display in Excel.
