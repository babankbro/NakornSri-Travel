# MOMA Refinement Plan: Unmutated Elitism

## Problem Statement
How might we tune the Multi-Objective Memetic Algorithm (MOMA) so that it strictly dominates pure GA across all objectives, replicating the success we recently achieved with the GA+ALNS hybrid?

## Current Situation Analysis
In the latest benchmarks:
*   **GA+ALNS** successfully beats GA. We achieved this by fixing its elitism (carrying top elites over unaltered) and ensuring ALNS is only applied as an educational step to offspring.
*   **MOMA** is currently underperforming compared to GA+ALNS. MOMA is already running with `pop=50`, `gen=80`.
*   The primary failure mode is that MOMA's Pareto Fronts are likely being destroyed because we apply ALNS and mutations too broadly, rather than protecting the non-dominated elites.

## Recommended Direction: "Strict Pareto Elitism & Offspring-Only ALNS"

We will apply the exact same strategy to MOMA that succeeded for GA+ALNS: protecting the elites.

In NSGA-II (the backbone of MOMA), elitism is handled by combining the parent and offspring populations, sorting them into Pareto fronts, and keeping the top `N` individuals.
However, if those `N` individuals are then immediately subjected to ALNS or mutation in the *next* generation without a protected copy step, their Pareto dominance is destroyed.

### 1. Protect the Elites (The Pareto Front)
In MOMA, the `combined_fronts` selection creates the `next_pop`. We need to ensure that when we iterate to the next generation, a subset of `next_pop` (e.g., the top 5 individuals from Rank 1) are explicitly copied into `new_population` **before** any crossover, mutation, or ALNS occurs.

### 2. Apply ALNS Only to Offspring
Just like in GA+ALNS, ALNS should only ever be applied to the children generated from the tournament selection and crossover steps.

## Key Assumptions to Validate
- [ ] **MOMA Elitism Implementation:** We assume that explicitly copying the top 5 individuals from the previous generation's Pareto sorting into the new population will prevent the regression seen in the benchmark.
- [ ] **Computation Time:** We assume that avoiding ALNS on the elite routes will not only preserve good routes but marginally speed up the computation.

## MVP Scope
1. **Update `MOMAOptimizer`:** Add an explicit loop at the start of the generation to copy the top `elite_size` (e.g., 5) individuals from `population` directly into `new_population`.
2. **Update Reproduction Loop:** Ensure the `while len(new_population) < self.population_size:` loop only applies crossover, mutation, and ALNS to the newly generated children.
3. **Run Benchmark:** Re-run `benchmark.py` to confirm MOMA now aligns with or beats GA/GA+ALNS.

## Not Doing (and Why)
- **Changing MOMA's Objectives:** The 3 objectives (Distance, CO2, -Rating) are working correctly. The issue is purely genetic preservation, not the objective definitions.
- **Increasing Generations:** `gen=80` is already sufficient to beat GA if elitism is working correctly.

## Open Questions
- Should the `elite_size` for MOMA be a fixed number (like 5), or should it be the entire 1st Rank Pareto Front (which could vary in size)? For the MVP, we will stick to a fixed size of 5 to match GA+ALNS.