# Implementation Plan: Lunch Constraint & Google Matrix Optimization

## Overview
We are integrating a new dataset (`TravelInfo_v2.csv`) that introduces a new `Food` place type. The objective is to replace the hardcoded "lunch break after 3 places" rule with a realistic constraint: users must visit a `Food` place around lunch time (e.g., 11:30 - 13:30) for 1 hour. Additionally, because the new dataset adds 19 new places, we must optimize the Google Distance Matrix API fetching script to perform *incremental* updates (only querying new pairs) rather than a full, expensive re-fetch of all 63x63 pairs.

## Architecture Decisions
- **Incremental Matrix Caching:** We will load the existing 44x44 cached matrices. When a new file is uploaded, the system will identify the diff (new place IDs) and only query the Google API for pairs involving these new IDs, merging the results into the existing cache.
- **Lunch Constraint Implementation:** 
  - Each day *must* contain exactly 1 `Food` place. (Penalty if 0 or >1).
  - The arrival time at the `Food` place will be evaluated. A time-window penalty will be applied if the arrival is outside the standard lunch window (e.g., 11:30 - 13:30).
  - The visit duration at the `Food` place will act as the lunch break (default 60 minutes based on CSV).
- **Algorithm Upgrades:** Route generators (SM, Random) must be updated to select exactly 1 OTOP and exactly 1 Food place per day.

## Task List

### Phase 1: Foundation (Data & Matrices)
- [ ] **Task 1: Update Data Loader to v2**
  - **Description:** Switch default data file to `TravelInfo_v2.csv` and register the `Food` PlaceType in Pydantic schemas.
  - **Files touched:** `backend/app/services/data_loader.py`, `backend/app/schemas/models.py`.
- [ ] **Task 2: Incremental Google API Fetching**
  - **Description:** Modify `load_google_matrices()` in `data_loader.py`. Load the old cache first. Compare the cached IDs against the loaded CSV IDs. Only chunk and query Google API for pairs where `start` or `dest` is a newly added ID. Merge and save the expanded cache.
  - **Files touched:** `backend/app/services/data_loader.py`.

### Checkpoint: Foundation
- [ ] Matrix size should successfully expand from 44x44 to 63x63 without querying 3,969 pairs (should only query the ~2,000 new combinations).
- [ ] `Food` places are correctly loaded.

### Phase 2: Core Routing Constraints
- [ ] **Task 3: Implement Food Constraint Penalties**
  - **Description:** In `base.py` `RouteEvaluator.fitness`, add penalties for missing or duplicate `Food` places (similar to OTOP). Remove the old `LUNCH_AFTER_N_PLACES` logic from `evaluate_day`. Instead, evaluate arrival time at the `Food` place. If it falls outside the 11:30-13:30 window, apply a scaling penalty based on how late/early they are.
  - **Files touched:** `backend/app/optimizers/base.py`.
- [ ] **Task 4: Update Objective Weights**
  - **Description:** Ensure `Food` places are factored into the `avg_rating` calculations correctly so the `weight_rating` objective remains balanced.
  - **Files touched:** `backend/app/optimizers/base.py`.

### Checkpoint: Constraints
- [ ] Routes without food fail feasibility checks or suffer massive penalties.

### Phase 3: Algorithm Upgrades
- [ ] **Task 5: Update Random Route Generator**
  - **Description:** Modify `_generate_random_route` in `base.py` to pick 1 OTOP and 1 Food place per day. Shuffle them randomly among the general tourist places.
  - **Files touched:** `backend/app/optimizers/base.py`.
- [ ] **Task 6: Update Saving Method (SM) Optimizer**
  - **Description:** Update `sm.py` to explicitly select 1 Food place per day. Because time matters, attempt to insert the Food place in the middle of the itinerary or after evaluating arrival times.
  - **Files touched:** `backend/app/optimizers/sm.py`.
- [ ] **Task 7: Update Crossover & ALNS Operators**
  - **Description:** Ensure GA crossover and ALNS destroy/repair operators respect the exactly 1 Food place constraint.
  - **Files touched:** `backend/app/optimizers/ga.py`, `backend/app/optimizers/alns.py`.

### Checkpoint: Algorithms
- [ ] Run `benchmark.py`. All algorithms must produce feasible routes visiting a food place at lunch.

### Phase 4: Polish & UI
- [ ] **Task 8: UI Updates**
  - **Description:** Add `Food` to the map legend (`frontend/js/app.js`) with an appropriate icon (e.g., `fa-utensils`) and color (e.g., `#F43F5E` Pink).
  - **Files touched:** `frontend/js/app.js`, `backend/app/api/map_api.py`.
- [ ] **Task 9: Test Suite Update**
  - **Description:** Update `test_api.py` and `benchmark.py` to validate `Food` constraints instead of just OTOP constraints.

### Checkpoint: Complete
- [ ] UI correctly visualizes food places.
- [ ] All tests pass.

## Risks and Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Google API Rate Limits | High | The incremental query is strictly necessary. We will batch queries into 25x25 blocks and aggressively cache. |
| Time Window Constraint Failure | Med | If forcing lunch strictly between 11:30 and 13:30 makes all routes infeasible, we will treat the time window as a "soft constraint" with a sliding scale penalty rather than an absolute failure. |
| SM Construction Complexity | Med | Inserting food exactly at lunch time during a greedy distance construction is hard. We will simply add 1 Food place and rely on the nearest-neighbor sorter to place it reasonably, then let ALNS fix the timing later. |

## Open Questions
- Is the lunch window strictly 11:30 to 13:30, or is there flexibility? (Assumption: Soft constraint, 11:30 - 13:30 is ideal, applying +1.0 penalty per 10 minutes outside this window).
- Should Food places be considered "Tourist" places when calculating the `max_places_per_day` limit? (Assumption: Yes, a 5-place day could be 1 OTOP, 1 Food, 3 Travel).