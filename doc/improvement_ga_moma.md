# GA & MOMA Refinement Plan

## Problem Statement
How might we tune the Genetic Algorithm (GA) and our Multi-Objective Memetic Algorithm (MOMA) so that the addition of ALNS (Memetic local search) guarantees strictly better performance than pure GA, rather than sometimes underperforming due to broken elitism or misallocated search constraints?

## Why does Pure GA sometimes beat GA+ALNS?
In our current benchmarks, GA often finds better minimal distances and CO2 emissions than GA+ALNS or MOMA. Why?
1. **Unprotected Elitism:** In `GA_ALNS`, the top `elite_size` individuals are passed into ALNS local search *before* being added to the new generation. While ALNS might improve their immediate scalar fitness, it alters their genetic structure, potentially destroying valuable "building blocks" (sub-routes) that were driving global exploration. True elitism requires passing the best individuals **unaltered** to the next generation.
2. **Exploration vs. Exploitation Imbalance:** Pure GA runs 100 generations with a population of 50 (5,000 evaluations of global search). GA+ALNS and MOMA run fewer generations (30-50) and smaller populations (30) to save time, relying on ALNS to make up the difference. However, ALNS is a *local* search. If the initial population doesn't have good global diversity, ALNS just optimizes a bad local area.
3. **Crossover Disruption:** Our current GA crossover operator tries to merge days, but the constraint repairs (filling in missing places randomly) add massive amounts of destructive noise, rendering crossover closer to a severe random mutation.

## Recommended Direction: "Strict Elitism & Smart Offspring ALNS"

We need to fix the elitism and crossover mechanics in the base GA, and propagate those fixes to MOMA.

### 1. Fix Elitism (GA, GA+ALNS, MOMA)
*   **Do not mutate the elites.** The top `N` individuals (or the Pareto Front in MOMA) must be copied directly into the next generation with 0% chance of mutation or ALNS.
*   ALNS should *only* be applied to offspring (children generated from crossover) as an "educational" step (Memetic Algorithm).

### 2. Improve the Base GA Crossover
*   Instead of blindly replacing duplicate nodes with completely random candidates (which destroys the route's coherence), the crossover repair should pull from the *nearest unused neighbors* or strictly swap missing nodes from the parents.

### 3. MOMA ALNS Tuning
*   In MOMA, we currently apply ALNS to 20% of the offspring. We should dynamically adjust this. Early in the generation, we want global crossover. Later in the generation, we want ALNS to squeeze out the final Pareto efficiencies.

## MVP Scope
1. **Update `GAAlnsOptimizer`:** Copy elites exactly. Apply ALNS only to newly generated children.
2. **Update `MOMAOptimizer`:** Ensure the Pareto Front elites are passed to the next generation *unmodified*. Apply ALNS only to the children produced by tournament selection.
3. **Run Benchmark:** Re-run `benchmark.py` to prove MOMA and GA+ALNS now strictly dominate pure GA.

## Not Doing (and Why)
- **Dynamic ALNS Weights:** Updating probabilities of Destroy/Repair operators based on success takes too much compute and isn't the root cause of the elitism bug.
- **Complex Crossover (e.g., Edge Recombination):** VRPTW with multiple days is too complex for standard TSP crossovers. We will stick to the current Order Crossover but fix the random injection.

## Open Questions
- If MOMA still runs slower than GA, should we lower the MOMA `population_size` to 20, but increase the `sm_seed_ratio` to 20% to guarantee a better starting point?