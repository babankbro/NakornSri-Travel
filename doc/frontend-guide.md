# Frontend Guide

## Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| HTML5 | - | Single page (`frontend/index.html`) |
| Tailwind CSS | CDN | Utility-first styling |
| Leaflet | 1.9.4 (CDN) | Interactive map (OpenStreetMap tiles) |
| Font Awesome | 6.5.0 (CDN) | Icons |
| Vanilla JavaScript | ES2020+ | All logic (`frontend/js/app.js`) |

No build step, no bundler, no framework. Files are served directly by FastAPI as static files.

## File Structure

```
frontend/
├── index.html        # Full page layout, Tailwind classes, all HTML structure
└── js/
    └── app.js        # All JavaScript logic (706 lines)
```

## How It's Served

FastAPI mounts the frontend directory and serves `index.html` on the root path:

```python
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
async def serve_frontend():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
```

Static assets (JS, images) are accessible under `/static/`.

## Tab Structure

The UI has 4 main tabs:

| Tab | ID | Description |
|-----|-----|-------------|
| **Optimize** | `tab-optimize` | Main workflow: configure parameters, run optimization, view results on map |
| **Past Results** | `tab-results` | List of all saved results, click to view any past result |
| **Algorithm Comparison** | `tab-compare` | Select multiple algorithms, run comparison, view metrics table |
| **Data Import** | `tab-import` | Upload CSV files, manage Google Distance Matrix API, import result JSON |

Tab switching is handled by `switchTab(tabName)` which hides all `.tab-content` divs and shows the selected one.

## Map Integration

### Initialization

```javascript
map = L.map('map').setView([8.40, 99.78], 11);  // Centered on Nakhon Si Thammarat
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
markersLayer = L.layerGroup().addTo(map);
polylinesLayer = L.layerGroup().addTo(map);
```

### Marker Types

**Type-based markers** (for showing all points):

```javascript
const TYPE_COLORS = {
    Depot: '#6366F1', Hotel: '#F59E0B', Travel: '#10B981',
    Culture: '#8B5CF6', OTOP: '#EF4444'
};
const TYPE_ICONS = {
    Depot: 'fa-plane', Hotel: 'fa-bed', Travel: 'fa-camera',
    Culture: 'fa-landmark', OTOP: 'fa-shopping-bag'
};
```

Markers are created as `L.divIcon` with colored circles and Font Awesome icons inside.

**Numbered markers** (for route visualization): Circles with sequential numbers, colored by day.

**Day colors**:

```javascript
const DAY_COLORS = ['#3B82F6', '#EF4444', '#10B981', '#F59E0B'];
//                   Blue       Red        Green      Amber
//                   Day 1      Day 2      Day 3      Day 4
```

### Route Display

When a result is displayed:

1. Clear existing markers and polylines
2. Center map on `map_data.center` with `map_data.zoom`
3. For each day:
   - Draw polyline connecting all points (dashed for Day 2+)
   - Add numbered markers for visited places
   - Add type-based markers for start/end points (Depot/Hotel)
   - Bind popups with place details (name, type, day, arrival/departure times)

### Google Maps Integration

Each day's route includes a "View on Google Maps" button that opens an external Google Maps directions URL:

```
https://www.google.com/maps/dir/?api=1
  &origin=lat,lng
  &destination=lat,lng
  &waypoints=lat1,lng1|lat2,lng2|...
  &travelmode=driving
```

A mini Leaflet map is also rendered below the main map showing the route with Start (S) and End (E) markers.

## Key JavaScript Functions

### Core

| Function | Description |
|----------|-------------|
| `initMap()` | Initialize Leaflet map with OpenStreetMap tiles |
| `checkDataStatus()` | Call `/api/v1/files/validate` and update status indicator |
| `loadAllPoints()` | Fetch all places and display as markers + load legend |
| `switchTab(tabName)` | Show/hide tab content panels |

### Optimization

| Function | Description |
|----------|-------------|
| `runOptimize()` | Read form values, POST to `/api/v1/routes/optimize`, fetch full result, display |
| `displayResult(result)` | Render summary cards, map markers/polylines, day-by-day itinerary, export buttons |
| `runCompare()` | Collect selected algorithms, call `/api/v1/routes/compare`, render comparison table |

### Google Distance Matrix

| Function | Description |
|----------|-------------|
| `checkGoogleStatus()` | Fetch cache status, update badges and buttons |
| `loadGoogleMatrix()` | Send API key to backend, show progress bar, refresh status |
| `loadCachedMatrix()` | Inform user cache is auto-loaded on server restart |
| `clearGoogleCache()` | Confirm and DELETE cache, revert to Haversine |
| `toggleApiKeyVisibility()` | Toggle API key input between password and text |

### Data Import

| Function | Description |
|----------|-------------|
| `uploadPlaces()` | Upload CSV via FormData to `/api/v1/files/places/import`, refresh map |
| `importResult()` | Upload result JSON via FormData to `/api/v1/results/import` |

### Results

| Function | Description |
|----------|-------------|
| `loadResultsList()` | Fetch `/api/v1/results`, render clickable list items |
| `viewResult(resultId)` | Fetch full result, switch to optimize tab, display |
| `exportResult(format)` | Open export URL in new tab (`json` or `csv`) |

### Map Helpers

| Function | Description |
|----------|-------------|
| `createIcon(type, dayColor)` | Create a circular div icon with Font Awesome icon |
| `createNumberedIcon(num, color)` | Create a circular div icon with a number |
| `buildGoogleMapsUrl(day, result)` | Build Google Maps directions URL for a day |
| `showGoogleMapsEmbed(result)` | Render day tabs and mini-map for Google Maps view |
| `renderGmapsIframe(start, end, places, url)` | Render Leaflet mini-map with route overlay |

## API Communication

All API calls use the browser's native `fetch()` API. The base URL is set to empty string (same origin):

```javascript
const API = '';
```

Requests use relative paths like `${API}/api/v1/routes/optimize`.

## Extending the Frontend

### Adding a New Tab

1. Add a tab button in `index.html` inside the tab navigation:
   ```html
   <button class="tab-btn bg-gray-200 text-gray-700 px-4 py-2 rounded-lg"
           onclick="switchTab('newtab')">New Tab</button>
   ```

2. Add a content div:
   ```html
   <div id="tab-newtab" class="tab-content hidden">
       <!-- Tab content here -->
   </div>
   ```

3. Update `switchTab()` in `app.js` to include the new tab index:
   ```javascript
   const idx = { optimize: 0, results: 1, compare: 2, import: 3, newtab: 4 }[tabName];
   ```

4. Add any initialization logic that should run when the tab is selected:
   ```javascript
   if (tabName === 'newtab') loadNewTabData();
   ```

### Adding a New API Integration

Follow the existing pattern:

```javascript
async function myNewFeature() {
    const btn = document.getElementById('myButton');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Loading...';
    try {
        const res = await fetch(`${API}/api/v1/my-endpoint`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ... })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Failed');
        // Handle success
    } catch (e) {
        alert('Error: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Original Text';
    }
}
```
