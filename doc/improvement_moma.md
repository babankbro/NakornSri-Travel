# MOMA Refinement Plan: Beating Pure GA

## Problem Statement
How might we tune the Multi-Objective Memetic Algorithm (MOMA) so that it strictly dominates pure GA across all objectives, preventing it from converging prematurely to sub-optimal solutions while maintaining acceptable computation times?

## Current Situation Analysis
In the latest benchmarks:
*   **GA+ALNS** successfully beats GA. It is given `pop=50`, `gen=80`. It uses strict elitism (carrying elites over unaltered) and applies ALNS selectively.
*   **MOMA** is currently running very fast (under 1.5 seconds) but is converging to worse solutions than GA. It currently runs with `pop=30`, `gen=30`.
*   The user confirmed MOMA is not hitting a strict time limit; it's just converging to a worse local optimum early.

## Why is MOMA converging early?
1.  **Low Diversity (Small Population):** MOMA uses `pop=30` and `gen=30` (900 evaluations), whereas GA uses `pop=50` and `gen=100` (5,000 evaluations). MOMA simply isn't exploring enough of the search space.
2.  **Pareto Front Stagnation:** In Multi-Objective Optimization (like NSGA-II), the "Pareto Front" can quickly fill up with solutions that are extreme in one objective (e.g., incredibly short distance but terrible rating) but mediocre overall. If the crowding distance calculation isn't aggressively maintaining middle-ground diversity, the population stagnates.
3.  **Destructive Crossover:** MOMA relies on the base GA's order crossover. If parents from different ends of the Pareto front are crossed over, the child is often severely broken and heavily penalized by the constraint checker.
4.  **Scalar Fitness Tracking Bug:** MOMA returns the single best route based on a `scalar_fitness` score at the very end, rather than genuinely selecting the best balanced route from the final Pareto front. It might be generating great routes but throwing them away in the final return statement.

## Recommended Direction: "Scale Up and Stabilize"

To make MOMA reliably dominate GA, we need to bring its exploration power (population/generations) closer to GA+ALNS, whilst ensuring the NSGA-II backbone is actually preserving high-quality, balanced routes.

### 1. Increase Exploration (Match GA+ALNS)
Increase MOMA's default parameters to `pop=50` and `gen=80`. This gives the NSGA-II backbone enough raw material to build a stable Pareto front.

### 2. Smart Pareto Selection for Final Output
Instead of keeping a running tally of the "best scalar fitness" route (which defeats the purpose of multi-objective search), MOMA should evaluate the final Generation's 1st Rank Pareto Front. It should then select the single route from that front that has the best balanced scalar fitness to return to the API.

### 3. Focused Memetic Injection
Currently, MOMA applies ALNS to 20% of children. We will keep this, but ensure that ALNS iterations are slightly increased (e.g., 5 iterations instead of 2) so that when a child *is* selected for ALNS, it actually receives a meaningful local improvement rather than a negligible tweak.

## Key Assumptions to Validate
- [ ] **Computation Scaling:** We assume that increasing `pop=50`, `gen=80`, and ALNS iterations to 5 will increase computation time to ~5-8 seconds, which is still acceptable for a background API task.
- [ ] **Crowding Distance Correctness:** We assume the current Crowding Distance implementation is correctly spreading out solutions. If MOMA still fails after parameter tuning, the crowding distance logic is the likely culprit.

## MVP Scope
1. **Update `MOMAOptimizer` defaults:** Change `population_size=50`, `generations=80`, `alns_iterations=5`.
2. **Update Final Selection:** Remove the running `self.best_fitness` tracker inside the generation loop. Instead, after the loop finishes, extract `fronts[0]`, calculate the scalar fitness for all routes in that front, and return the absolute best one.
3. **Run Benchmark:** Re-run `benchmark.py` to confirm MOMA now aligns with or beats GA/GA+ALNS.

## Not Doing (and Why)
- **Returning the full Pareto Front to the API:** The frontend UI currently expects a single `best_route`. Rewriting the frontend to support 5 different route options is out of scope for this specific algorithm fix. We will continue to collapse the Pareto front down to a single "best balanced" route at the final step.
- **Dynamic Weight Adjustments:** We won't try to dynamically alter `weight_distance` or `weight_co2` during the run. The user's input weights must remain static to ensure predictable behavior.

## Open Questions
- If MOMA takes 10+ seconds on the `Real3` dataset with these new parameters, is that acceptable, or should we dynamically scale generations based on the dataset size?