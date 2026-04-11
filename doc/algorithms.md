# Optimization Algorithms

## Problem Formulation

This system solves a variant of the **multi-objective Traveling Salesman Problem (TSP)** with the following structure:

- **Trip**: 2 days, 1 night in Nakhon Si Thammarat, Thailand
- **Start/End**: Nakhon Si Thammarat Airport (Depot)
- **Day 1**: Depot → tourist places → Hotel
- **Day 2**: Hotel → tourist places → Depot
- **Objectives**: Minimize weighted sum of distance, time, and CO2 emissions
- **Constraints**: Time window, OTOP visit requirement, no duplicate places

### Time Constants

| Parameter | Value | Description |
|-----------|-------|-------------|
| `DAY_START_MINUTES` | 480 (08:00) | Daily start time |
| `DAY_END_MINUTES` | 1020 (17:00) | Daily end time |
| `LUNCH_AFTER_N_PLACES` | 3 | Lunch break after every 3rd place |
| `LUNCH_DURATION_MINUTES` | 60 | Lunch break duration |

### Constraints

1. **Time window**: Each day must finish by 17:00 (1020 minutes)
2. **OTOP**: Each day must visit **exactly 1** OTOP (community product) place
3. **No duplicates**: A place visited on Day 1 cannot be visited on Day 2
4. **Hotel**: Exactly 1 hotel selected for overnight stay between days

## Route Representation

A route is represented by the `Route` class:

```python
class Route:
    day1_places: List[str]   # ordered list of place IDs for Day 1
    day2_places: List[str]   # ordered list of place IDs for Day 2
    hotel_id: str            # selected hotel ID
```

Day 1 sequence: `Depot → day1_places[0] → ... → day1_places[n] → Hotel`
Day 2 sequence: `Hotel → day2_places[0] → ... → day2_places[n] → Depot`

## Fitness Function

The fitness function combines three normalized objectives plus constraint penalties:

```
fitness = w_distance * (total_distance / 200)
        + w_time    * (total_time / 600)
        + w_co2     * (total_co2 / 30)
        + penalties
```

**Normalization constants**: distance/200 km, time/600 min, co2/30 kg

**Default weights**: `w_distance=0.4`, `w_time=0.3`, `w_co2=0.3`

### Penalties

| Condition | Penalty |
|-----------|---------|
| Route exceeds time window (infeasible) | +10.0 |
| Day missing OTOP visit (0 OTOP places) | +5.0 per day |
| Day has extra OTOP visits (>1) | +3.0 per extra OTOP |

**Lower fitness = better route**. The optimizer minimizes this value.

## Day Evaluation

For each day, the evaluator computes:

1. Start at `start_id` (Depot or Hotel) at 08:00
2. For each place in sequence:
   - Add travel distance and travel time from previous place
   - Add visit duration (from CSV `VisitTime`, default 45 min if 0)
   - Add CO2 value (from CSV `CO2` field — per-place, not per-travel)
   - After every 3rd place: add 60-minute lunch break
3. Add travel distance/time from last place to `end_id` (Hotel or Depot)
4. Check feasibility: `end_time <= 17:00`

## Lifestyle Filtering

The `lifestyle_type` parameter affects candidate place ordering:

| Lifestyle | Effect |
|-----------|--------|
| `all` | No filtering — all tourist places equally available |
| `culture` | `Culture` type places prioritized (placed first in candidate list) |
| `cafe` | `Travel` type places prioritized |
| `food` | Same as `all` (no specific food type in data) |

Higher-rated places (`RATE` field) have a higher probability of being selected during random route generation (weighted random sampling).

---

## Algorithms

### GA — Genetic Algorithm

**Source**: `backend/app/optimizers/ga.py`

Population-based evolutionary algorithm that evolves a set of candidate routes over generations.

#### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `population_size` | 100 | Number of routes per generation |
| `generations` | 200 | Number of evolutionary cycles |
| `crossover_rate` | 0.8 | Probability of crossover vs. cloning |
| `mutation_rate` | 0.3 | Probability of mutation |
| `tournament_size` | 5 | Tournament selection pool size |
| `elite_size` | 5 | Number of top routes preserved unchanged |

#### Operators

**Selection**: Tournament selection — pick `tournament_size` random individuals, select the best.

**Crossover**: Order crossover (OX) — preserves a segment from parent1, fills remaining positions from parent2's ordering. Applied independently to day1 and day2 place lists. Deduplication ensures no place appears twice.

**Mutation types** (chosen randomly):
1. **Swap** — swap two places within a day
2. **Reverse segment** — reverse a subsequence within a day
3. **Inter-day swap** — swap one place between Day 1 and Day 2
4. **Hotel change** — replace the hotel with a random alternative

**Elitism**: Top 5 routes are copied directly to the next generation.

#### Flow

```
Initialize population (100 random routes)
For each generation (200):
    Copy elite (top 5) to new population
    While new population < 100:
        Select 2 parents via tournament
        Apply crossover → child
        Apply mutation → child
        Add to new population
    Evaluate all fitnesses
    Track best solution
```

---

### SA — Simulated Annealing

**Source**: `backend/app/optimizers/sa.py`

Single-solution metaheuristic that explores the neighborhood of the current solution, accepting worse solutions with decreasing probability.

#### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `initial_temp` | 100.0 | Starting temperature |
| `cooling_rate` | 0.995 | Temperature multiplier per step (T = T * cooling_rate) |
| `min_temp` | 0.01 | Stop when temperature reaches this |
| `iterations_per_temp` | 50 | Neighborhood searches per temperature step |

#### Neighborhood Moves

5 types of moves (chosen randomly):
1. **Swap** — swap two places within a random day
2. **Reverse segment** — reverse a subsequence within a day
3. **Inter-day swap** — swap one place between Day 1 and Day 2
4. **Replace place** — replace a random place with an unused candidate
5. **Hotel change** — switch to a different hotel

#### Acceptance Criterion

- If neighbor is better (lower fitness): always accept
- If neighbor is worse: accept with probability `exp(-delta / temperature)`
- As temperature decreases, probability of accepting worse solutions decreases

#### Flow

```
Generate random initial route
While temperature > min_temp:
    For i in range(iterations_per_temp):
        Generate neighbor via random move
        If better: accept
        Else: accept with probability exp(-delta/T)
        Track best solution found
    temperature *= cooling_rate
```

---

### ALNS — Adaptive Large Neighborhood Search (Operators)

**Source**: `backend/app/optimizers/alns.py`

Not a standalone optimizer — provides destroy and repair operators used by the hybrid algorithms.

#### Destroy Operators

| Operator | Description |
|----------|-------------|
| `random_removal` | Remove `n_remove` random places from the route |
| `worst_removal` | Remove the places whose removal improves fitness the most |
| `shaw_removal` | Remove geographically similar places (close to a seed place) |

#### Repair Operators

| Operator | Description |
|----------|-------------|
| `greedy_insert` | Insert each removed place at the position that yields the best fitness |
| `random_insert` | Insert each removed place at a random position in a random day |
| `regret_insert` | Insert the place with the highest "regret" (difference between best and second-best insertion cost) first |

---

### GA+ALNS — Genetic Algorithm with ALNS Local Search

**Source**: `backend/app/optimizers/ga_alns.py`

Hybrid that combines GA's population-based search with ALNS local search to refine solutions.

#### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `population_size` | 50 | Smaller population than pure GA |
| `generations` | 80 | Fewer generations than pure GA |
| `crossover_rate` | 0.8 | Same as GA |
| `mutation_rate` | 0.3 | Same as GA |
| `tournament_size` | 5 | Same as GA |
| `elite_size` | 5 | Same as GA |
| `alns_iterations` | 10 | ALNS local search iterations per application |
| `n_remove` | 2 | Places to remove per ALNS destroy step |

#### Flow

```
Initialize population (50 random routes)
For each generation (80):
    Elite routes: apply ALNS local search to improve them
    While new population < 50:
        Select 2 parents via tournament
        Apply GA crossover → child
        Apply GA mutation → child
        With 30% probability: apply ALNS local search to child
        Add to new population
    Evaluate all fitnesses
    Track best solution
```

The ALNS local search randomly selects a destroy operator (random, worst, or Shaw removal) and a repair operator (greedy, random, or regret insertion) for each iteration.

---

### SA+ALNS — Simulated Annealing with Adaptive ALNS

**Source**: `backend/app/optimizers/sa_alns.py`

Hybrid that uses SA's acceptance criterion with ALNS destroy/repair as the neighborhood generator. Includes **adaptive operator weights** that learn which operators perform best.

#### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `initial_temp` | 50.0 | Lower than pure SA |
| `cooling_rate` | 0.99 | Faster cooling than pure SA |
| `min_temp` | 0.1 | Higher minimum than pure SA |
| `iterations_per_temp` | 15 | Fewer iterations per step |
| `n_remove` | 2 | Places to remove per destroy step |

#### Adaptive Weights

Each destroy and repair operator has a weight that determines its selection probability. Weights are updated every 100 iterations based on operator performance:

| Reward | Score | Condition |
|--------|-------|-----------|
| Best improvement | +3 | New global best found |
| Improvement | +2 | Better than current solution |
| Accepted | +1 | Worse but accepted by SA criterion |

Weight update formula:
```
weight = decay * old_weight + (1 - decay) * (total_score / count)
```
Where `decay = 0.8` and minimum weight = 0.1.

#### Flow

```
Generate random initial route
Initialize operator weights (all = 1.0)
While temperature > min_temp:
    For i in range(iterations_per_temp):
        Select destroy operator (weighted random)
        Select repair operator (weighted random)
        Destroy current route → partial + removed places
        Repair partial route → neighbor
        SA acceptance: accept if better, or probabilistically if worse
        Score operators based on result quality
        Every 100 iterations: update operator weights
    temperature *= cooling_rate
```

---

## Algorithm Comparison Guide

| Algorithm | Speed | Solution Quality | Best For |
|-----------|-------|-----------------|----------|
| **GA** | Medium | Good | General use, large solution spaces |
| **SA** | Fast | Good | Quick results, escaping local optima |
| **GA+ALNS** | Slow | Very Good | Best quality when time allows |
| **SA+ALNS** | Medium | Very Good | Balance of quality and speed, adaptive |

Use the `/api/v1/routes/compare` endpoint to run all algorithms on the same parameters and compare results side-by-side.
