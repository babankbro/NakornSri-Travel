# Algorithm Workflows & Flowcharts

This document provides detailed workflows, Mermaid flowcharts, and pseudocode for all the optimization algorithms implemented in the Travel Route File-Based System (`backend/app/optimizers/`).

## 1. Genetic Algorithm (GA)

**Workflow:**
1. **Initialize:** Generate an initial population of random, valid routes.
2. **Evaluate:** Calculate fitness for all routes.
3. **Evolve:** Loop for $N$ generations:
   - **Elitism:** Carry over the top $k$ routes to the next generation without changes.
   - **Selection:** Use tournament selection to pick parents.
   - **Crossover:** Combine parts of two parents to create a child route (Order Crossover).
   - **Mutation:** Randomly swap, reverse, or replace places/hotels in the child route.
   - **Replace:** The new population replaces the old one.
4. **Result:** Return the best route found across all generations.

**Flowchart:**
```mermaid
graph TD
    Start(("Start")) --> InitPop["1. Initialize Population N=POPULATION_SIZE"]
    InitPop --> EvalPop["1.1 Evaluate Fitness"]
    EvalPop --> LoopGen{"2. Gen < MAX_GENERATIONS?"}
    
    LoopGen -- Yes --> Elitism["2.1 Copy Top ELITE_SIZE Elite Routes"]
    
    Elitism --> LoopPop{"2.2 New Pop < POPULATION_SIZE?"}
    
    LoopPop -- Yes --> Selection["2.2.1 Tournament Selection x2 (size=TOURNAMENT_SIZE)"]
    Selection --> Crossover["2.2.2 Order Crossover prob=CROSSOVER_RATE"]
    Crossover --> Mutation["2.2.3 Mutation prob=MUTATION_RATE"]
    Mutation --> EvalChild["2.2.4 Evaluate Child & Add to New Pop"]
    EvalChild --> LoopPop
    
    LoopPop -- No --> UpdateBest["2.3 Update Global Best Route"]
    UpdateBest --> LoopGen
    
    LoopGen -- No --> End(("3. End: Return Best"))
```

**Pseudocode:**
```text
Input:
  - POPULATION_SIZE (e.g., 100)
  - MAX_GENERATIONS (e.g., 200)
  - CROSSOVER_RATE (e.g., 0.8)
  - MUTATION_RATE (e.g., 0.3)
  - TOURNAMENT_SIZE (e.g., 5)
  - ELITE_SIZE (e.g., 5)

// 1. Initialization
Create initial population P = GenerateRandomPopulation(size=POPULATION_SIZE)
Evaluate fitness for each route in P
best_route = MinFitness(P)
Generation = 1

// 2. Evolution Loop
WHILE Generation <= MAX_GENERATIONS DO:
    
    Create new_population P_new
    
    // 2.1 Elitism
    Add Top ELITE_SIZE Elite from P to P_new
    
    WHILE size(P_new) < POPULATION_SIZE DO:
        // 2.2 Selection
        Select parents P1, P2 from P based on fitness (Tournament, size=TOURNAMENT_SIZE)
        
        // 2.3 Crossover
        Apply Order Crossover to P1, P2 to create offspring child (rate=CROSSOVER_RATE)
        
        // 2.4 Mutation
        Apply mutation operator to child (rate=MUTATION_RATE)
        
        // 2.5 Evaluation & Replacement
        Evaluate fitness for child and add to P_new
    END WHILE
    
    // 2.6 Update Population & Best Solution
    Replace old population P with P_new
    Update best_route = MinFitness(P ∪ {best_route})
    
    // 2.7 Update Generation Counter
    Generation = Generation + 1
END WHILE

// 3. Return Best Solution
RETURN best_route
```

---

## 2. Simulated Annealing (SA)

**Workflow:**
1. **Initialize:** Generate a random initial route and set a starting temperature.
2. **Iterate per Temp:** For a fixed number of iterations, explore the neighborhood.
3. **Neighborhood Move:** Swap, reverse, or replace places/hotels to generate a neighbor.
4. **Acceptance:** If the neighbor is better, accept it. If worse, accept it probabilistically based on the temperature.
5. **Cooling:** Multiply the temperature by a cooling rate.
6. **Result:** Return the best route found when the minimum temperature is reached.

**Flowchart:**
```mermaid
graph TD
    Start(("Start")) --> Init["1. Init Route, Temp=INITIAL_TEMP"]
    Init --> LoopTemp{"2. Temp > MIN_TEMP?"}
    
    LoopTemp -- Yes --> LoopIter{"2.1 Iter < ITERATIONS_PER_TEMP?"}
    
    LoopIter -- Yes --> GenNeighbor["2.1.1 Generate Random Neighbor"]
    GenNeighbor --> CalcDelta["2.1.2 Delta = Neighbor - Current"]
    CalcDelta --> CheckBetter{"2.1.3 Delta < 0?"}
    
    CheckBetter -- Yes --> Accept["2.1.4 Accept & Update Current"]
    CheckBetter -- No --> ProbAccept{"2.1.5 Rand() < exp(-Delta/Temp)?"}
    
    ProbAccept -- Yes --> Accept
    ProbAccept -- No --> LoopIter
    
    Accept --> UpdateBest["2.1.6 Update Global Best"]
    UpdateBest --> LoopIter
    
    LoopIter -- No --> Cool["2.2 Temp = Temp * COOLING_RATE"]
    Cool --> LoopTemp
    
    LoopTemp -- No --> End(("3. End: Return Best"))
```

**Pseudocode:**
```text
Input:
  - INITIAL_TEMP (e.g., 1000)
  - COOLING_RATE (e.g., 0.95)
  - MIN_TEMP (e.g., 1)
  - ITERATIONS_PER_TEMP (e.g., 10)

// 1. Initialization
Create initial current_route = GenerateRandomRoute()
best_route = current_route
Set initial temperature Temp = INITIAL_TEMP

// 2. Annealing Loop
WHILE Temp > MIN_TEMP DO:
    
    // 2.1 Iterations at current temperature
    FOR Iteration from 1 to ITERATIONS_PER_TEMP DO:
        
        // 2.1.1 Neighborhood Move
        Generate neighbor from current_route (randomly swap/reverse/replace)
        
        // 2.1.2 Evaluation
        Calculate delta = Fitness(neighbor) - Fitness(current_route)
        
        // 2.1.3 Acceptance Criterion
        IF delta < 0 OR Random() < exp(-delta / Temp) THEN
            current_route = neighbor
            
            // 2.1.4 Update Best Solution
            IF Fitness(current_route) < Fitness(best_route) THEN
                best_route = current_route
            END IF
        END IF
    END FOR
    
    // 2.2 Cooling Schedule
    Temp = Temp * COOLING_RATE
END WHILE

// 3. Return Best Solution
RETURN best_route
```

---

## 3. Saving Method (SM - Clarke-Wright Heuristic)

**Workflow:**
1. **Select Hotels:** Greedily select the best hotel(s) based on average distance to the depot and tourist spots.
2. **Compute Savings:** For each day, compute the distance saved by combining two places rather than visiting them separately from the hub.
3. **Construct Route:** Sort the savings and greedily append pairs of places into the day's route, respecting constraints (max places, time windows, OTOP requirement).
4. **Optimize Order:** Use a nearest-neighbor approach to finalize the ordering of places within each day.

**Flowchart:**
```mermaid
graph TD
    Start(("Start")) --> SelectHotels["1. Select Optimal Hotels"]
    SelectHotels --> LoopDays{"2. For Each Day?"}
    
    LoopDays -- Yes --> CalcSavings["2.1 Compute Clarke-Wright Savings"]
    CalcSavings --> SortSavings["2.2 Sort Savings Descending"]
    SortSavings --> InitDay["2.3 Add 1 OTOP Place"]
    InitDay --> GreedyAdd["2.4 Greedily Add Places via Savings"]
    GreedyAdd --> CheckConstraints{"2.4.1 Valid Limits & Time?"}
    CheckConstraints -- Yes --> AddToDay["2.4.2 Add Place to Day Route"]
    CheckConstraints -- No --> NextSaving["2.4.3 Check Next Saving Pair"]
    AddToDay --> FillRemaining["2.5 Fill Remaining Slots by Rate"]
    NextSaving --> FillRemaining
    FillRemaining --> NNOrder["2.6 Nearest-Neighbor Ordering"]
    NNOrder --> SaveDay["2.7 Store Day Route"]
    SaveDay --> LoopDays
    
    LoopDays -- No --> BuildFinal["3. Combine Days & Hotels"]
    BuildFinal --> End(("3.1 End: Return Final Route"))
```

**Pseudocode:**
```text
Input:
  - TRIP_DAYS (e.g., 3)
  - PLACES_LIST (array of locations)
  - DISTANCE_MATRIX (NxN matrix)
  - TIME_MATRIX (NxN matrix)

// 1. Initialization
Select optimal hotel_ids based on average distance (TRIP_DAYS - 1)
Initialize empty list route_days

// 2. Day-by-Day Construction Loop
FOR day = 1 to TRIP_DAYS DO:
    Set hub = Start location for day
    Set end = End location for day
    Define available_places = All candidates excluding already used
    
    // 2.1 Savings Calculation
    Compute Clarke-Wright savings for all pairs from hub
    Sort savings in descending order
    
    // 2.2 Initial Day Route
    Initialize day_route with best OTOP place for hub
    
    // 2.3 Greedily Add Places
    FOR EACH pair IN sorted savings DO:
        IF pair fits within max_places AND time_window THEN
            Append pair to day_route
        END IF
    END FOR
    
    // 2.4 Fill Remaining Slots
    IF length(day_route) < max_places THEN
        Append best rated unused places to day_route
    END IF
    
    // 2.5 Finalize Order
    Apply Nearest-Neighbor ordering to day_route
    Append day_route to route_days
END FOR

// 3. Return Best Solution
RETURN Route(route_days, hotel_ids)
```

---

## 4. Genetic Algorithm + ALNS (GA+ALNS)

**Workflow:**
1. **Base:** Uses the standard GA framework.
2. **Enhancement:** Integrates ALNS (Adaptive Large Neighborhood Search) as a local search mechanism.
3. **Elite Polish:** The top $k$ elite routes are passed through the ALNS optimizer for refinement every generation.
4. **Child Polish:** 30% of newly generated children are passed through the ALNS optimizer before being added to the population.

**Flowchart:**
```mermaid
graph TD
    Start(("Start")) --> InitPop["1. Initialize Pop N=POPULATION_SIZE"]
    InitPop --> LoopGen{"2. Gen < MAX_GENERATIONS?"}
    
    LoopGen -- Yes --> ALNSElite["2.1 Apply ALNS Local Search to Top ELITE_SIZE Elite"]
    ALNSElite --> LoopPop{"2.2 New Pop < POPULATION_SIZE?"}
    
    LoopPop -- Yes --> Crossover["2.2.1 Tournament + Crossover"]
    Crossover --> Mutate["2.2.2 Mutation"]
    Mutate --> ProbALNS{"2.2.3 Rand < MUTATION_RATE?"}
    
    ProbALNS -- Yes --> ALNSChild["2.2.4 Apply ALNS Local Search to Child"]
    ProbALNS -- No --> AddChild["2.2.5 Add to New Pop"]
    ALNSChild --> AddChild
    AddChild --> LoopPop
    
    LoopPop -- No --> UpdateBest["2.3 Update Global Best"]
    UpdateBest --> LoopGen
    
    LoopGen -- No --> End(("3. End: Return Best"))
```

**Pseudocode:**
```text
Input:
  - POPULATION_SIZE (e.g., 100)
  - MAX_GENERATIONS (e.g., 200)
  - CROSSOVER_RATE (e.g., 0.8)
  - MUTATION_RATE (e.g., 0.3)
  - TOURNAMENT_SIZE (e.g., 5)
  - ELITE_SIZE (e.g., 5)
  - ALNS_ITERATIONS (e.g., 50)
  - N_REMOVE (e.g., 3)

// 1. Initialization
Create initial population P = GenerateRandomPopulation(size=POPULATION_SIZE)
Evaluate fitness for each route in P
best_route = MinFitness(P)
Generation = 1

// 2. Evolution Loop with ALNS Enhancement
WHILE Generation <= MAX_GENERATIONS DO:
    
    Create new_population P_new
    
    // 2.1 Elite Polish (ALNS Local Search)
    FOR EACH elite IN Top ELITE_SIZE of P DO:
        Apply ALNS Local Search (ALNS_ITERATIONS iterations) to elite
        Add improved_elite to P_new
    END FOR
    
    WHILE size(P_new) < POPULATION_SIZE DO:
        // 2.2 Selection
        Select parents P1, P2 using Tournament Selection
        
        // 2.3 Crossover & Mutation
        Apply Crossover to P1, P2 to create child
        Apply Mutation to child
        
        // 2.4 Child Polish (ALNS Local Search)
        IF Random() < MUTATION_RATE THEN
            Apply ALNS Local Search (ALNS_ITERATIONS iterations) to child
        END IF
        
        // 2.5 Evaluation & Replacement
        Evaluate fitness for child and add to P_new
    END WHILE
    
    // 2.6 Update Population & Best Solution
    Replace old population P with P_new
    Update best_route = MinFitness(P ∪ {best_route})
    
    // 2.7 Update Generation Counter
    Generation = Generation + 1
END WHILE

// 3. Return Best Solution
RETURN best_route
```

---

## 5. Simulated Annealing + ALNS (SA+ALNS)

**Workflow:**
1. **Base:** Follows the SA temperature and acceptance schema.
2. **Neighborhood Generation:** Instead of random moves, neighbors are generated by applying one Destroy operator and one Repair operator.
3. **Adaptive Weights:** Operators are selected based on roulette wheel selection (weights). Weights are updated based on the historical success of the operators (adaptive).

**Flowchart:**
```mermaid
graph TD
    Start(("Start")) --> Init["1. Init Route, Temp=INITIAL_TEMP, Weights=1"]
    Init --> LoopTemp{"2. Temp > MIN_TEMP?"}
    
    LoopTemp -- Yes --> LoopIter{"2.1 Iter < ITERATIONS_PER_TEMP?"}
    
    LoopIter -- Yes --> SelectOps["2.1.1 Select Destroy & Repair Ops via Weights"]
    SelectOps --> ApplyALNS["2.1.2 Apply Destroy -> Repair"]
    ApplyALNS --> EvalDelta["2.1.3 Delta = Neighbor - Current"]
    EvalDelta --> AcceptRules{"2.1.4 Delta < 0 or Prob?"}
    
    AcceptRules -- Yes --> Accept["2.1.5 Accept Neighbor & Score Ops"]
    AcceptRules -- No --> Reject["2.1.6 Reject"]
    Accept --> LoopIter
    Reject --> LoopIter
    
    LoopIter -- No --> UpdateWeights["2.2 Update Op Weights per 100 iters"]
    UpdateWeights --> Cool["2.3 Temp = Temp * COOLING_RATE"]
    Cool --> LoopTemp
    
    LoopTemp -- No --> End(("3. End: Return Best"))
```

**Pseudocode:**
```text
Input:
  - INITIAL_TEMP (e.g., 1000)
  - COOLING_RATE (e.g., 0.95)
  - MIN_TEMP (e.g., 1)
  - ITERATIONS_PER_TEMP (e.g., 10)
  - N_REMOVE (e.g., 3)

// 1. Initialization
Create initial current_route = GenerateRandomRoute()
best_route = current_route
Set initial temperature Temp = INITIAL_TEMP
Initialize destroy_weights and repair_weights (all 1.0)
Total_Iterations = 0

// 2. Annealing & ALNS Loop
WHILE Temp > MIN_TEMP DO:
    
    // 2.1 Iterations at current temperature
    FOR Iteration from 1 to ITERATIONS_PER_TEMP DO:
        
        // 2.1.1 Adaptive Operator Selection
        Select destroy_op based on destroy_weights
        Select repair_op based on repair_weights
        
        // 2.1.2 Neighborhood Move (Destroy & Repair)
        Apply destroy_op then repair_op to current_route to create neighbor
        
        // 2.1.3 Evaluation
        Calculate delta = Fitness(neighbor) - Fitness(current_route)
        
        // 2.1.4 Acceptance & Scoring
        Set accept = False
        IF delta < 0 THEN
            accept = True
            Increase scores for destroy_op and repair_op (+3 or +2)
        ELSE IF Random() < exp(-delta / Temp) THEN
            accept = True
            Increase scores for destroy_op and repair_op (+1)
        END IF
        
        // 2.1.5 Update Route
        IF accept is True THEN
            current_route = neighbor
            IF Fitness(current_route) < Fitness(best_route) THEN
                best_route = current_route
            END IF
        END IF
        
        Total_Iterations = Total_Iterations + 1
    END FOR
    
    // 2.2 Adaptive Weights Update
    IF Total_Iterations is multiple of 100 THEN
        Update destroy_weights and repair_weights based on scores
    END IF
    
    // 2.3 Cooling Schedule
    Temp = Temp * COOLING_RATE
END WHILE

// 3. Return Best Solution
RETURN best_route
```

---

## 6. Saving Method + ALNS (SM+ALNS)

**Workflow:**
1. **Phase 1 (Construction):** Run the deterministic SM optimizer to rapidly build a high-quality initial solution.
2. **Phase 2 (Refinement):** Pass the SM route into an ALNS loop.
3. **ALNS Loop:** For $N$ iterations, randomly destroy and repair the route, greedily accepting any improvements.

**Flowchart:**
```mermaid
graph TD
    Start(("Start")) --> Phase1["1. Phase 1: Run SM Optimizer"]
    Phase1 --> Phase2Init["1.1 Init ALNS Loop with SM Route"]
    Phase2Init --> LoopALNS{"2. Iter < ALNS_ITERATIONS?"}
    
    LoopALNS -- Yes --> SelectOps["2.1 Select Random Destroy & Repair Ops"]
    SelectOps --> ApplyOps["2.2 Destroy -> Repair"]
    ApplyOps --> Eval{"2.3 Fitness < Current?"}
    
    Eval -- Yes --> Accept["2.4 Accept & Update Best"]
    Eval -- No --> Reject["2.5 Reject"]
    
    Accept --> LoopALNS
    Reject --> LoopALNS
    
    LoopALNS -- No --> End(("3. End: Return Best"))
```

**Pseudocode:**
```text
Input:
  - ALNS_ITERATIONS (e.g., 100)
  - N_REMOVE (e.g., 3)

// 1. Initialization (Phase 1: Construction)
Create initial current_route = Run SM_Optimize() to generate high-quality base
best_route = current_route

// 2. Refinement Loop (Phase 2: ALNS)
FOR Iteration from 1 to ALNS_ITERATIONS DO:
    
    // 2.1 Operator Selection
    Select random destroy_op (Random, Worst, Shaw)
    Select random repair_op (Greedy, Random, Regret)
    
    // 2.2 Neighborhood Move (Destroy & Repair)
    Apply destroy_op then repair_op to current_route to create neighbor
    
    // 2.3 Evaluation & Acceptance
    IF Fitness(neighbor) < Fitness(current_route) THEN
        current_route = neighbor
        
        // 2.4 Update Best Solution
        IF Fitness(current_route) < Fitness(best_route) THEN
            best_route = current_route
        END IF
    END IF
END FOR

// 3. Return Best Solution
RETURN best_route
```

---

## 7. Multi-Objective Memetic Algorithm (MOMA)

**Workflow:**
1. **Initialization:** Create an initial population where 10% are derived from the Saving Method (SM) for rapid convergence, and the rest are generated randomly.
2. **NSGA-II Backbone:** Evaluate all routes across three distinct objectives (Distance, CO2, and negative Rating). Do not collapse these into a single scalar fitness. Instead, assign a Non-Dominated Pareto Rank and a Crowding Distance to each route.
3. **Strict Elitism:** At the start of each generation, the top routes (from the 1st Pareto Front) are explicitly protected and carried over without any mutation.
4. **Reproduction & ALNS:** Generate offspring via Tournament Selection (preferring better rank and wider crowding distance) and Order Crossover. Apply ALNS (Memetic local search) exclusively to the offspring.

**Flowchart:**
```mermaid
graph TD
    Start(("Start")) --> InitPop["1. Phase 1: Init Pop (SM_SEED_RATIO SM, (1-SM_SEED_RATIO) Random)"]
    InitPop --> EvalPop["1.1 Evaluate (Dist, CO2, Rating)"]
    EvalPop --> LoopGen{"2. Gen < Max?"}
    
    LoopGen -- Yes --> Rank["2.1 Phase 2: NSGA-II Fast Pareto Ranking"]
    Rank --> Crowd["2.2 Calculate Crowding Distance"]
    
    Crowd --> Elitism["2.3 Phase 3: Strict Elitism (Copy Top N_ELITES Rank 1)"]
    Elitism --> LoopPop{"2.4 New Pop < Pop Size?"}
    
    LoopPop -- Yes --> Selection["2.4.1 Tournament Selection (Rank & Crowd)"]
    Selection --> Crossover["2.4.2 Order Crossover"]
    Crossover --> ProbALNS{"2.4.3 Rand < ALNS_MUTATION_RATE?"}
    
    ProbALNS -- Yes --> ALNSChild["2.4.4 Phase 5: Apply ALNS to Child"]
    ProbALNS -- No --> MutateChild["2.4.5 Standard Random Mutation"]
    ALNSChild --> AddChild["2.4.6 Add Child to New Pop"]
    MutateChild --> AddChild
    AddChild --> LoopPop
    
    LoopPop -- No --> Merge["2.5 Merge Parent + Child"]
    Merge --> KeepTop["2.6 Keep Top N via NSGA-II Elitism"]
    KeepTop --> LoopGen
    
    LoopGen -- No --> End(("3. End: Return Best Scalar from 1st Front"))
```

**Pseudocode:**
```text
Input:
  - POPULATION_SIZE (e.g., 100)
  - MAX_GENERATIONS (e.g., 200)
  - ALNS_MUTATION_RATE (e.g., 0.2)
  - STANDARD_MUTATION_RATE (e.g., 0.1)
  - N_ELITES (e.g., 5)
  - SM_SEED_RATIO (e.g., 0.2)

// 1. Initialization (Phase 1: Hybrid Seed)
Create empty population P
P_SM = Generate routes using SM_Optimize() (SM_SEED_RATIO of Pop size)
P_Random = GenerateRandomPopulation((1-SM_SEED_RATIO) of Pop size)
P = P_SM ∪ P_Random
Evaluate multiple objectives for each route in P (F1: Dist, F2: CO2, F3: -Rating)

Generation = 1

// 2. Evolution Loop (Phase 2: NSGA-II Backbone)
WHILE Generation <= MAX_GENERATIONS DO:
    
    Create new_population P_child
    
    // 2.1 Strict Elitism
    Assign Pareto Ranks using Non-dominated Sorting on P
    Copy Top N Elites directly from P to P_child
    
    // 2.2 Reproduction
    WHILE size(P_child) < Pop_Size DO:
        // 2.2.1 Selection based on Pareto Rank and Crowding Distance
        Select parents P1, P2 using Binary Tournament
        Child = Order_Crossover(P1, P2)
        
        // 2.2.2 Memetic Local Search (Phase 3: ALNS Injection)
        IF Random() < ALNS_MUTATION_RATE THEN
            destroy_op = Select Random Destroy
            repair_op = Select Random Repair
            Child = repair_op(destroy_op(Child))
        ELSE IF Random() < STANDARD_MUTATION_RATE THEN
            Child = Mutate_Swap_or_Reverse(Child)
        END IF
        
        Add Child to P_child
    END WHILE
    
    // 2.3 Environmental Selection
    P_combined = P ∪ P_child
    Assign Pareto Ranks on P_combined
    Calculate Crowding Distance
    P = SelectTopN(P_combined, Pop_Size)
    
    Generation = Generation + 1
END WHILE

// 3. Return Best Solution
RETURN best_balanced_route_from(Pareto_Front(P))
```

---

## 8. Adaptive Large Neighborhood Search (ALNS)

**Workflow:**
1. **Initialize:** Receive an initial route and set a starting temperature.
2. **Iterate per Temp:** Loop while the current temperature is above the minimum temperature.
3. **Inner Iterations:** For a fixed number of iterations at the current temperature:
   - **Select Operators:** Randomly select one Destroy operator and one Repair operator.
   - **Neighborhood Move:** Apply the Destroy operator to remove $N$ places, then apply the Repair operator to reinsert them.
   - **Evaluation:** Calculate the fitness change (Delta).
   - **Acceptance:** If the new route is better, accept it. If worse, accept it probabilistically based on the SA criterion.
4. **Cooling:** Multiply the temperature by a cooling rate.
5. **Result:** Return the best route found when the minimum temperature is reached.

**Flowchart:**
```mermaid
graph TD
    Start(("Start")) --> Init["1. Init Route, Temp=INITIAL_TEMP"]
    Init --> LoopTemp{"2. Temp > MIN_TEMP?"}
    
    LoopTemp -- Yes --> LoopIter{"2.1 Iter < ITERATIONS_PER_TEMP?"}
    
    LoopIter -- Yes --> SelectOps["2.1.1 Select Destroy & Repair Ops"]
    SelectOps --> ApplyOps["2.1.2 Apply Destroy -> Repair"]
    ApplyOps --> EvalDelta["2.1.3 Delta = Neighbor - Current"]
    EvalDelta --> AcceptRules{"2.1.4 Delta < 0 or Rand() < exp(-Delta/Temp)?"}
    
    AcceptRules -- Yes --> Accept["2.1.5 Accept & Update Current"]
    AcceptRules -- No --> Reject["2.1.6 Reject & Revert"]
    
    Accept --> UpdateBest["2.1.7 Update Global Best"]
    UpdateBest --> LoopIter
    Reject --> LoopIter
    
    LoopIter -- No --> Cool["2.2 Temp = Temp * COOLING_RATE"]
    Cool --> LoopTemp
    
    LoopTemp -- No --> End(("3. End: Return Best"))
```

**Pseudocode:**
```text
Input:
  - INITIAL_TEMP (e.g., 100.0)
  - MIN_TEMP (e.g., 0.01)
  - COOLING_RATE (e.g., 0.995)
  - ITERATIONS_PER_TEMP (e.g., 50)
  - N_REMOVE (e.g., 2)

// 1. Initialization
current_route = GetInitialRoute()
best_route = current_route
Set initial temperature Temp = INITIAL_TEMP

// 2. Annealing & ALNS Loop
WHILE Temp > MIN_TEMP DO:
    
    // 2.1 Inner Iterations
    FOR Iteration from 1 to ITERATIONS_PER_TEMP DO:
        
        // 2.1.1 Operator Selection
        Select random destroy_op
        Select random repair_op
        
        // 2.1.2 Neighborhood Move (Destroy & Repair)
        neighbor = repair_op(destroy_op(current_route, N_REMOVE))
        
        // 2.1.3 Evaluation
        Calculate delta = Fitness(neighbor) - Fitness(current_route)
        
        // 2.1.4 Acceptance Criterion (SA)
        IF delta < 0 OR Random() < exp(-delta / Temp) THEN
            current_route = neighbor
            
            // 2.1.5 Update Best Solution
            IF Fitness(current_route) < Fitness(best_route) THEN
                best_route = current_route
            END IF
        END IF
    END FOR
    
    // 2.2 Cooling Schedule
    Temp = Temp * COOLING_RATE
END WHILE

// 3. Return Best Solution
RETURN best_route
```

---

## 9. ALNS Operators Reference

### Destroy Operators
- **Random Removal (`random_removal`):** Randomly selects $N$ places and removes them from the route. Promotes broad exploration.
- **Worst Removal (`worst_removal`):** Iteratively evaluates the cost reduction of removing each place, and removes the $N$ places that improve the fitness the most.
- **Shaw Removal (`shaw_removal`):** Removes places that are geographically close to each other (based on distance matrix) to reorganize entire local clusters.

### Repair Operators
- **Greedy Insert (`greedy_insert`):** Tests every removed place at every possible insertion point and iteratively inserts the place that results in the lowest immediate fitness cost.
- **Random Insert (`random_insert`):** Inserts removed places back into random valid positions across any day.
- **Regret Insert (`regret_insert`):** Evaluates the cost of inserting a place at its best position vs its second-best position (the "regret"). Inserts the place with the highest regret first, delaying easier decisions.