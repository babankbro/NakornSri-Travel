# Workflow: Lifestyle Selection → GA-ALNS Place Selection

This document traces the complete call chain from the moment a user picks a lifestyle in the UI through every layer of the system, ending at the exact point where it changes which places appear in a GA-ALNS route.

---

## 1. UI Layer — `frontend/js/app.js`

The user selects a lifestyle from a dropdown (`#lifestyle`) and clicks **คำนวณเส้นทาง**.

```
[User picks "สายคาเฟ่ติดแกรม" from #lifestyle dropdown]
        ↓
runOptimize()  (app.js:511)
```

`runOptimize()` reads every form control and POSTs to the backend:

```javascript
// app.js:516-532
const body = {
  trip_days:          parseInt(document.getElementById('trip-days').value),
  algorithm:          document.getElementById('algorithm').value,   // "ga_alns"
  lifestyle_type:     document.getElementById('lifestyle').value,   // "cafe" | "culture" | "food" | "all"
  min_places_per_day: parseInt(document.getElementById('min-places').value),
  max_places_per_day: parseInt(document.getElementById('max-places').value),
  weight_distance:    parseFloat(document.getElementById('w-dist').value),
  weight_co2:         parseFloat(document.getElementById('w-co2').value),
  weight_rating:      parseFloat(document.getElementById('w-rating').value),
};

fetch('/api/v1/routes/optimize', { method: 'POST', body: JSON.stringify(body) });
```

**lifestyle_type values:**

| UI Label | Value sent |
|---|---|
| ทั้งหมด | `"all"` |
| สายวัฒนธรรม | `"culture"` |
| สายคาเฟ่ติดแกรม | `"cafe"` |
| สายกิน | `"food"` |

---

## 2. API Layer — `backend/app/api/routes.py`

```
POST /api/v1/routes/optimize
        ↓
optimize(request: OptimizeRequest)  (routes.py:19)
        ↓
optimizer_service.optimize(request)  (routes.py:27)
```

FastAPI validates the incoming JSON against `OptimizeRequest` (Pydantic). The field `lifestyle_type` becomes a `LifestyleType` enum:

```python
# schemas/models.py:27-31
class LifestyleType(str, Enum):
    ALL     = "all"
    CULTURE = "culture"
    CAFE    = "cafe"
    FOOD    = "food"

# schemas/models.py:46-54
class OptimizeRequest(BaseModel):
    trip_days:          int           = 2
    algorithm:          AlgorithmType = AlgorithmType.GA
    lifestyle_type:     LifestyleType = LifestyleType.ALL
    weight_distance:    float         = 0.4
    weight_co2:         float         = 0.3
    weight_rating:      float         = 0.3
    min_places_per_day: int           = 5
    max_places_per_day: int           = 7
```

The fully-validated `OptimizeRequest` object is passed unchanged through every layer below.

---

## 3. Service Layer — `backend/app/services/route_optimizer.py`

```
RouteOptimizerService.optimize(request)  (route_optimizer.py:32)
        ↓
  algo = request.algorithm   →  AlgorithmType.GA_ALNS
        ↓
  GAAlnsOptimizer(self.data, request)    (route_optimizer.py:48)
        ↓
  optimizer.optimize()
```

The service dispatches by `AlgorithmType`. The `request` object (including `lifestyle_type`) is forwarded directly to the optimizer constructor.

---

## 4. GA-ALNS Optimizer — `backend/app/optimizers/ga_alns.py`

```python
class GAAlnsOptimizer(BaseOptimizer):
    def __init__(self, data, request, ...):
        super().__init__(data, request)          # stores request in self.request
        self.alns = ALNSOperators(data, request, self.rng)
        self._ga  = GAOptimizer(data, request, ...)  # GA shares same request
```

### `optimize()` — main loop (ga_alns.py:92)

```
optimize()
  │
  ├─ _init_population()          → 50 random routes
  │     └─ _generate_random_route()   ← [lifestyle affects this — see §6]
  │
  └─ for gen in range(80):
        │
        ├─ Preserve elite_size=5 best routes unchanged
        │
        └─ While population < 50:
              │
              ├─ _tournament_select()  ×2  → parent1, parent2
              ├─ self._ga._crossover(p1, p2)   ← [lifestyle affects candidates — see §5]
              ├─ self._ga._mutate(child)        ← [lifestyle affects swap pool — see §5]
              │
              └─ 30% chance → _alns_local_search(child)
                    │
                    ├─ random_removal / worst_removal / shaw_removal  (destroy)
                    └─ greedy_insert / random_insert / regret_insert  (repair)
```

---

## 5. GA Operators — `backend/app/optimizers/ga.py`

Both crossover and mutation call `self._get_candidate_places()` when they need to fill a slot with a replacement place. This is the first point where lifestyle selection visibly changes which places are considered.

### `_crossover(p1, p2)` (ga.py:87)

```
Order Crossover (OX) per day
  → Remove cross-day duplicates
      → if slot is empty: self._get_candidate_places()  ← lifestyle-ordered list
  → Repair OTOP constraint (exactly 1 per day)
      → if missing: pick from _get_candidate_places() where type == OTOP
      → if excess:  replace with _get_candidate_places() where type ∉ {OTOP, FOOD, FOOD_CAFE}
  → Repair FOOD constraint (at least 1 per day; FOOD_CAFE counts as FOOD)
      → if missing: pick from _get_candidate_places() where type ∈ {FOOD, FOOD_CAFE}
      → if excess:  replace with _get_candidate_places() where type ∉ {OTOP, FOOD, FOOD_CAFE}
  → Hotel: randomly pick from either parent
```

### `_mutate(child)` (ga.py:177) — 30% probability, one of 4 types:

| Type | Action | Lifestyle effect |
|---|---|---|
| 0 — Swap | Swap 2 places within same day | None (just reorders) |
| 1 — Reverse | Reverse a sub-segment within a day | None (just reorders) |
| 2 — Inter-day Swap | Move place Day1↔Day2 | Restricted: FOOD/FOOD_CAFE only swaps with FOOD/FOOD_CAFE; OTOP with OTOP; others freely |
| 3 — Hotel | Replace hotel randomly | None |

---

## 6. Base Optimizer — `backend/app/optimizers/base.py`

This is where `lifestyle_type` first directly filters and reorders which places are available.

### Step 6a — `_get_candidate_places()` (base.py:263)

```python
def _get_candidate_places(self) -> List[Place]:
    tourist = self.data.get_tourist_places()   # all non-Depot, non-Hotel places

    if lifestyle == "culture":
        preferred = [p for p in tourist if p.type == PlaceType.CULTURE]
        others    = [p for p in tourist if p.type != PlaceType.CULTURE]
        return preferred + others

    elif lifestyle == "cafe":
        preferred = [p for p in tourist if p.type in (PlaceType.CAFE, PlaceType.FOOD_CAFE)]
        others    = [p for p in tourist if p.type not in (PlaceType.CAFE, PlaceType.FOOD_CAFE)]
        return preferred + others        # ← Café/Food+Café are at the FRONT of the list

    # "all" or "food": no reordering
    return tourist
```

**Effect:** For "cafe" lifestyle, every call to `_get_candidate_places()` returns a list where `Café` and `Food and Café` places appear first. When crossover needs a replacement or when the random route builder fills tourist slots, it picks from this front-of-list first (via `replacements[0]` or roulette-weighted from the ordered pool).

---

### Step 6b — `_generate_random_route(rng)` (base.py:275)

This builds every chromosome in the initial population.

```
all_candidates = _get_candidate_places()
                 ↑ already lifestyle-ordered (CAFE first for "cafe")

otop_pool  = data.get_otop_places()              (shuffled)
food_pool  = [FOOD places] + [FOOD_CAFE places]  (shuffled)
                              ↑ FOOD_CAFE counts as mandatory lunch

non_otop_food = [p for p in all_candidates
                 if p.type not in (OTOP, FOOD, FOOD_CAFE)]
                 ↑ includes PlaceType.CAFE  ← cafes ARE tourist candidates
```

**Per day:**

```
Step 1 — Mandatory OTOP:  pick 1 from otop_pool        → added to day_places[d]
Step 2 — Mandatory FOOD:  pick 1 from food_pool         → added to day_places[d]
          (food_pool contains FOOD and FOOD_CAFE; both satisfy the lunch constraint)

Step 3 — Fill slots:
    target = rng.integers(min_per_day, max_per_day+1)
    fill_count = target − 2  (already have OTOP + FOOD)

    pick_non_otop_food(fill_count, exclude=used_ids):
        pool  = non_otop_food filtered by unused ids
              = [TRAVEL, CULTURE, CAFE] ordered by lifestyle preference
        probs = place.rate / sum(rates)    ← roulette weighted by rating
        idxs  = rng.choice(pool, size=fill_count, replace=False, p=probs)

    For "cafe" lifestyle:
        CAFE places are in non_otop_food
        They appear first in all_candidates (from _get_candidate_places)
        → Higher chance of being selected in the fill step

Step 4 — Shuffle: rng.shuffle(day_places[d])
Step 5 — Hotel: pick randomly from hotel pool
```

---

### Step 6c — `fitness(route)` (base.py:139)

After building or modifying a route, fitness is computed. For "cafe" lifestyle, a bonus is applied:

```
Z = W_d × (dist_km / 400)
  + W_co2 × (co2_kg / 150)
  + W_r × ((5.0 − avg_rating) / 5.0)
  + penalties
  − cafe_bonus

Where:
  cafe_bonus = 0.05 × (number of CAFE or FOOD_CAFE places in route)
```

**Penalties relevant to food/cafe places:**

| Condition | Penalty |
|---|---|
| Day has no FOOD or FOOD_CAFE | +50.0 |
| FOOD/FOOD_CAFE arrives before 11:00 | +2.0 per 10 min early |
| FOOD/FOOD_CAFE arrives after 13:00 | +2.0 per 10 min late |
| Day ends after 17:00 | +10.0 |
| Too few places in day | +50.0 × deficit |
| Too many places in day | +50.0 × excess |

---

## 7. Data Layer — `backend/app/services/data_loader.py`

```python
def get_tourist_places(self) -> List[Place]:
    return [p for p in self.places if p.is_tourist]
    # is_tourist = type not in (DEPOT, HOTEL)
    # → includes TRAVEL, CULTURE, OTOP, FOOD, CAFE, FOOD_CAFE

def get_cafe_places(self) -> List[Place]:
    return [p for p in self.places if p.type in (PlaceType.CAFE, PlaceType.FOOD_CAFE)]
```

Data is loaded from `TravelInfo_v3.csv`:

| Type | Count | Role in route |
|---|---|---|
| Depot | 1 | Start/end point only |
| Hotel | 18 | Overnight stay between days |
| Travel | 11 | Tourist slot |
| Culture | 10 | Tourist slot |
| OTOP | 4 | Mandatory 1/day |
| Food | 8 | Mandatory food slot (lunch) |
| **Café** | **1** | **Tourist slot (+ cafe bonus)** |
| **Food and Café** | **10** | **Mandatory food slot + cafe bonus** |

---

## 8. End-to-End Flow Diagram

```
[UI: LifestyleType = "cafe"]
          │
          ▼
POST /api/v1/routes/optimize
  { lifestyle_type: "cafe", algorithm: "ga_alns", ... }
          │
          ▼
OptimizeRequest(lifestyle_type=LifestyleType.CAFE)
          │
          ▼
RouteOptimizerService.optimize(request)
  → GAAlnsOptimizer(data, request)
          │
          ▼
GAAlnsOptimizer.optimize()
  ┌───────────────────────────────────────────────────────┐
  │ _init_population()  [pop=50]                          │
  │   └─ _generate_random_route() ×50                     │
  │         ├─ _get_candidate_places()                    │
  │         │     → [CAFE, FOOD_CAFE, TRAVEL, CULTURE, …] │  ← lifestyle reorder
  │         ├─ food_pool = [FOOD] + [FOOD_CAFE]           │  ← FOOD_CAFE = lunch OK
  │         ├─ non_otop_food = [TRAVEL, CULTURE, CAFE]    │  ← CAFE = tourist slot
  │         └─ fill slots: roulette(rate) from front      │  ← CAFE preferred
  │                                                       │
  │ for gen in range(80):                                 │
  │   ├─ preserve top-5 elites                            │
  │   └─ while pop < 50:                                  │
  │         ├─ _tournament_select() ×2  → p1, p2         │
  │         ├─ _crossover(p1, p2)                         │
  │         │     └─ _get_candidate_places()              │  ← lifestyle-ordered replacements
  │         ├─ _mutate(child)                             │
  │         │     └─ FOOD_CAFE protected as food-type     │
  │         └─ 30%: _alns_local_search(child)             │
  │               ├─ destroy: random/worst/shaw removal   │
  │               └─ repair:  greedy/random/regret insert │
  │                                                       │
  │ fitness(route)  per generation                        │
  │   cost = W_d·dist + W_co2·co2 + W_r·rating           │
  │   − 0.05 × (# CAFE + FOOD_CAFE places)               │  ← cafe bonus
  │   + penalties (missing food, late lunch, etc.)        │
  └───────────────────────────────────────────────────────┘
          │
          ▼
best_route  →  result JSON  →  frontend map display
```

---

## 9. Summary: Where lifestyle_type Changes Behaviour

| Stage | File | What changes for `"cafe"` |
|---|---|---|
| Initial population | `base.py:_generate_random_route` | CAFE places enter the tourist slot pool (`non_otop_food`); FOOD_CAFE enters food pool |
| Candidate ordering | `base.py:_get_candidate_places` | CAFE + FOOD_CAFE sorted to front of all replacement lists |
| Crossover repair | `ga.py:_crossover` | Replacement slots prefer CAFE/FOOD_CAFE first (front of candidate list) |
| Mutation swap | `ga.py:_mutate` | FOOD_CAFE treated as food-type — only swaps with other FOOD/FOOD_CAFE |
| Fitness reward | `base.py:fitness` | −0.05 per CAFE/FOOD_CAFE place → routes with more cafes score better |
| Data available | `data_loader.py` | v3 CSV loaded: 1 Café + 10 Food and Café = 11 cafe-eligible places |
