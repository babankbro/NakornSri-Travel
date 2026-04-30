import re

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # --- 1. GA ---
    content = content.replace('N=100', 'N=population_size')
    content = content.replace('Gen < 200', 'Gen < max_generations')
    content = content.replace('Copy Top 5 Elite Routes', 'Copy Top elite_size Elite Routes')
    content = content.replace('New Pop < 100', 'New Pop < population_size')
    
    # Fix Tournament Selection x2 in MD and HTML
    content = content.replace('Tournament Selection x2"]', 'Tournament Selection x2 (size=tournament_size)"]')
    content = content.replace('Tournament Selection x2;', 'Tournament Selection x2 (size=tournament_size);')
    
    # GA prob replacements
    content = content.replace('prob=0.8', 'prob=crossover_rate')
    content = content.replace('prob=0.3', 'prob=mutation_rate')
    content = content.replace('GenerateRandomPopulation(size=100)', 'GenerateRandomPopulation(size=population_size)')
    content = content.replace('Generation <= 200', 'Generation <= max_generations')
    
    # GA top 5 elitism replacements
    content = content.replace('Top 5 Elite', 'Top elite_size Elite')
    content = content.replace('size(P_new) < 100', 'size(P_new) < population_size')
    content = content.replace('Tournament, size=5', 'Tournament, size=tournament_size')
    content = content.replace('(rate=0.8)', '(rate=crossover_rate)')
    content = content.replace('(rate=0.3)', '(rate=mutation_rate)')
    
    # --- 2. SA ---
    content = content.replace('Temp=100', 'Temp=initial_temp')
    content = content.replace('Temp > 0.01', 'Temp > min_temp')
    content = content.replace('Iter < 50', 'Iter < iterations_per_temp')
    content = content.replace('Temp = Temp * 0.995', 'Temp = Temp * cooling_rate')
    content = content.replace('Temp = 100.0', 'Temp = initial_temp')
    content = content.replace('from 1 to 50', 'from 1 to iterations_per_temp')

    # --- 4. GA+ALNS ---
    content = content.replace('N=50', 'N=population_size')
    content = content.replace('Gen < 80', 'Gen < max_generations')
    content = content.replace('New Pop < 50', 'New Pop < population_size')
    content = content.replace('(10 iterations)', '(alns_iterations iterations)')
    content = content.replace('GenerateRandomPopulation(size=50)', 'GenerateRandomPopulation(size=population_size)')
    content = content.replace('Generation <= 80', 'Generation <= max_generations')
    content = content.replace('Top 5 of P', 'Top elite_size of P')
    content = content.replace('size(P_new) < 50', 'size(P_new) < population_size')
    
    # ALNS child probability
    content = content.replace('Rand < 0.3', 'Rand < mutation_rate')
    content = content.replace('Random() < 0.3', 'Random() < mutation_rate')

    # --- 5. SA+ALNS ---
    content = content.replace('Temp=50', 'Temp=initial_temp')
    content = content.replace('Temp > 0.1', 'Temp > min_temp')
    content = content.replace('Iter < 15', 'Iter < iterations_per_temp')
    content = content.replace('Temp = Temp * 0.99', 'Temp = Temp * cooling_rate')
    content = content.replace('Temp = 50.0', 'Temp = initial_temp')
    content = content.replace('from 1 to 15', 'from 1 to iterations_per_temp')

    # --- 6. SM+ALNS ---
    content = content.replace('Iter < 100', 'Iter < alns_iterations')
    content = content.replace('from 1 to 100', 'from 1 to alns_iterations')

    # --- 7. MOMA ---
    # Need to be careful. The prompt says "Apply the same logic"
    content = content.replace('10% SM, 90% Random', 'sm_seed_ratio SM, (1-sm_seed_ratio) Random')
    content = content.replace('10% of Pop using SM', 'sm_seed_ratio of Pop using SM')
    content = content.replace('90% of Pop Randomly', '(1-sm_seed_ratio) of Pop Randomly')
    content = content.replace('10% of Pop size', 'sm_seed_ratio of Pop size')
    content = content.replace('90% of Pop size', '(1-sm_seed_ratio) of Pop size')
    
    # Keep Top N Rank 1 -> Top n_elites Rank 1
    content = content.replace('Top N Rank 1', 'Top n_elites Rank 1')
    content = content.replace('Top N Elites (Rank 1)', 'Top n_elites Elites (Rank 1)')
    
    # ALNS rate
    content = content.replace('ALNS Rate?', 'alns_mutation_rate?')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

process_file('doc/algorithm-workflows.md')
process_file('doc/algorithm-workflows.html')
