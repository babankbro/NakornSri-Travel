# Mathematical Model for Multi-Objective Travel Route Optimization

This document outlines the formal mathematical model used in the Travel Route File-Based System. It has been updated to reflect the new 3-objective structure (Distance, CO2, Rating) and the new constraints (Food/Lunch timing, OTOP, min/max places).

## 1. Sets, Parameters, and Decision Variables

### 1.1 Sets
| Symbol | Description |
|---|---|
| $K$ | Set of travel days, where $k \in K, k = 1, 2, \dots, d$ |
| $P$ | Set of all places (locations) |
| $O$ | Set of community product (OTOP) places, where $O \subset P$ |
| $F$ | Set of food/restaurant places, where $F \subset P$ |
| $H$ | Set of available hotels/accommodations, where $h \in H, h = 1, 2, \dots, m$ |
| $D$ | Set containing the Depot (Airport), usually $D = \{0\}$ |
| $N$ | Set of all nodes in the network, $N = P \cup H \cup D$ |

### 1.2 Parameters
| Symbol | Description |
|---|---|
| $c_{ij}$ | Travel distance from node $i$ to node $j$ (km) |
| $t_{ij}$ | Travel time from node $i$ to node $j$ (minutes) |
| $v_i$ | Visit duration at node $i$ (minutes) |
| $e_i$ | Amount of CO₂ emitted by visiting node $i$ (kg/day) |
| $r_i$ | Popularity/Rating of node $i$ ($1.0 \le r_i \le 5.0$) |
| $Q_{max}$ | Maximum number of places allowed per day |
| $Q_{min}$ | Minimum number of places allowed per day |
| $W_d$ | User-defined weight for Distance objective |
| $W_c$ | User-defined weight for CO₂ objective |
| $W_r$ | User-defined weight for Rating objective |
| $[T_{start}, T_{end}]$ | Daily operational time window (e.g., 08:00 - 17:00, or 480 - 1020 mins) |
| $[L_{start}, L_{end}]$ | Target lunch arrival window (e.g., 11:00 - 13:00, or 660 - 780 mins) |

### 1.3 Decision Variables
| Symbol | Type | Description |
|---|---|---|
| $x_{ijk}$ | Binary | $1$ if the route travels directly from node $i$ to node $j$ on day $k$, else $0$ |
| $y_{ik}$ | Binary | $1$ if node $i$ is visited on day $k$, else $0$ |
| $z_{h}$ | Binary | $1$ if hotel $h$ is selected for the entire trip, else $0$ |
| $a_{ik}$ | Continuous | Arrival time at node $i$ on day $k$ (minutes from 00:00) |
| $u_{ik}$ | Integer | Sequence order variable for subtour elimination on day $k$ |

---

## 2. Multi-Objective Functions

The system optimizes for three distinct, often conflicting objectives. In the scalarized algorithms (SM, GA, SA, ALNS), these are combined into a single fitness score via weighted sum normalization. In the MOMA algorithm, these form the 3 axes of the Pareto front.

### Objective 1: Minimize Total Distance ($F_1$)
$$ F_1 = \sum_{k \in K} \sum_{i \in N} \sum_{j \in N} c_{ij} x_{ijk} $$

### Objective 2: Minimize Total CO₂ Emissions ($F_2$)
$$ F_2 = \sum_{k \in K} \sum_{i \in P} e_i y_{ik} $$

### Objective 3: Maximize Average Place Rating ($F_3$)
$$ F_3 = \frac{\sum_{k \in K} \sum_{i \in P} r_i y_{ik}}{\sum_{k \in K} \sum_{i \in P} y_{ik}} $$

*Note: In the implementation, $F_3$ is inverted as $\left( \frac{5.0 - F_3}{5.0} \right)$ so that all algorithms can strictly minimize the resulting scalar value.*

### Scalarized Fitness Function
For non-Pareto algorithms, the fitness $Z$ is calculated as:
$$ \text{Minimize } Z = W_d \left(\frac{F_1}{200}\right) + W_c \left(\frac{F_2}{150}\right) + W_r \left(\frac{5.0 - F_3}{5.0}\right) + \mathcal{P} $$
Where $\mathcal{P}$ represents the sum of all constraint violation penalties.

---

## 3. Constraints

### 3.1 Routing & Flow Constraints

**1. Hotel Selection:**
Exactly one hotel must be selected for the entire multi-day trip.
$$ \sum_{h \in H} z_h = 1 $$

**2. Node Uniqueness:**
A tourist place can be visited at most once across the entire trip.
$$ \sum_{k \in K} y_{ik} \le 1 \quad \forall i \in P $$

**3. Flow Conservation:**
If a place is visited on day $k$, there must be exactly one incoming edge and one outgoing edge.
$$ \sum_{j \in N} x_{jik} = y_{ik} \quad \forall i \in P, \forall k \in K $$
$$ \sum_{j \in N} x_{ijk} = y_{ik} \quad \forall i \in P, \forall k \in K $$

**4. Subtour Elimination (MTZ Formulation):**
$$ u_{ik} - u_{jk} + 1 \le |P|(1 - x_{ijk}) \quad \forall i, j \in P, i \ne j, \forall k \in K $$

### 3.2 Categorical Constraints

**5. Daily Place Limits:**
The number of places visited each day must fall within the user-defined bounds.
$$ Q_{min} \le \sum_{i \in P} y_{ik} \le Q_{max} \quad \forall k \in K $$

**6. OTOP Constraint:**
Exactly 1 community product (OTOP) place must be visited per day.
$$ \sum_{i \in O} y_{ik} = 1 \quad \forall k \in K $$

**7. Food Constraint:**
At least 1 food/restaurant place must be visited per day.
$$ \sum_{i \in F} y_{ik} \ge 1 \quad \forall k \in K $$

### 3.3 Time Constraints

**8. Arrival Time Calculation:**
If traveling from $i$ to $j$, the arrival time at $j$ must account for the arrival time at $i$, the visit duration at $i$, and the travel time from $i$ to $j$.
$$ a_{jk} \ge a_{ik} + v_i + t_{ij} - M(1 - x_{ijk}) \quad \forall i, j \in N, \forall k \in K $$
*(where $M$ is a large constant)*

**9. Daily Time Window:**
The day must begin at $T_{start}$ and the final arrival at the end point (Hotel/Depot) must occur before $T_{end}$.
$$ a_{ik} \ge T_{start} \quad \forall i \in N, \forall k \in K $$
$$ a_{ik} \le T_{end} \quad \text{for the final node } i \text{ on day } k, \forall k \in K $$

**10. Lunch Time Penalty (Soft Constraint):**
If node $i$ is a Food place ($i \in F$), its arrival time $a_{ik}$ should ideally fall within $[L_{start}, L_{end}]$ (e.g., 11:00 to 13:00). 
In the mathematical model, this is expressed as a continuous penalty function added to $\mathcal{P}$:
$$ 
\text{Penalty}_{lunch} = 
\begin{cases} 
\alpha (L_{start} - a_{ik}) & \text{if } a_{ik} < L_{start} \\
0 & \text{if } L_{start} \le a_{ik} \le L_{end} \\
\alpha (a_{ik} - L_{end}) & \text{if } a_{ik} > L_{end}
\end{cases}
$$
*(where $\alpha$ is a scaling factor, implemented as $+2.0$ penalty per $10$ minutes of deviation).*