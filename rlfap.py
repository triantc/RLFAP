from collections import defaultdict
import random
import sys
import time
from csp import min_conflicts_value

import csp

weight = {}     # for dom/wdeg heuristic
conf_set = {}   # for fc-cbj (conflict set)
order = {}      # for fc-cbj (dict to keep order of variables as we assigned values)
visited = set() # for fc-cbj (set to keep visited vars)

# FC
def forward_checking(csp, var, value, assignment, removals):
    """Prune neighbor values inconsistent with var=value."""
    csp.support_pruning()
    for B in csp.neighbors[var]:
        if B not in assignment:
            for b in csp.curr_domains[B][:]:
                if not csp.constraints(var, value, B, b):
                    csp.prune(B, b, removals)
            if not csp.curr_domains[B]:
                weight[(var, B)] += 1   # domain wipe-out so increase weight for both var
                weight[(B, var)] += 1   # and the neighbour (dom/wdeg heuristic)
                conf_set[B].add(var)    # domain wipe-out so add var to conflict_set[B] (for cbj)
                return False
    return True

# MAC
def AC3(csp, queue=None, removals=None, arc_heuristic=csp.dom_j_up):
    """[Figure 6.3]"""
    if queue is None:
        queue = {(Xi, Xk) for Xi in csp.variables for Xk in csp.neighbors[Xi]}
    csp.support_pruning()
    queue = arc_heuristic(csp, queue)
    checks = 0
    while queue:
        (Xi, Xj) = queue.pop()
        revised, checks = revise(csp, Xi, Xj, removals, checks)
        if revised:
            if not csp.curr_domains[Xi]:
                return False, checks  # CSP is inconsistent
            for Xk in csp.neighbors[Xi]:
                if Xk != Xj:
                    queue.add((Xk, Xi))
    return True, checks  # CSP is satisfiable

def mac(csp, var, value, assignment, removals, constraint_propagation=AC3):
    """Maintain arc consistency."""
    return constraint_propagation(csp, {(X, var) for X in csp.neighbors[var]}, removals)

def revise(csp, Xi, Xj, removals, checks=0):
    """Return true if we remove a value."""
    revised = False
    for x in csp.curr_domains[Xi][:]:
        # If Xi=x conflicts with Xj=y for every possible y, eliminate Xi=x
        # if all(not csp.constraints(Xi, x, Xj, y) for y in csp.curr_domains[Xj]):
        conflict = True
        for y in csp.curr_domains[Xj]:
            if csp.constraints(Xi, x, Xj, y):
                conflict = False
            checks += 1
            if not conflict:
                break
        if conflict:
            csp.prune(Xi, x, removals)
            revised = True
    if not csp.curr_domains[Xi]:
        weight[(Xi, Xj)] += 1   # domain wipe-out so increase weight for both var
        weight[(Xj, Xi)] += 1   # and the neighbour (dom/wdeg heuristic)
    return revised, checks

# FC-CBJ
counter = 1
def cbj_search(csp, select_unassigned_variable=csp.first_unassigned_variable,
           order_domain_values=csp.unordered_domain_values, inference=csp.no_inference):

    # Returns a result and a var(if it needs to jump back on for cbj)
    def cbj(assignment):
        global counter 
        if len(assignment) == len(csp.variables):
            return assignment, None
        var = select_unassigned_variable(assignment, csp)
        order[var] = counter
        counter += 1
        for value in order_domain_values(var, assignment, csp):
            if 0 == csp.nconflicts(var, value, assignment):
                csp.assign(var, value, assignment)
                removals = csp.suppose(var, value)
                if inference(csp, var, value, assignment, removals):
                    result, best_var = cbj(assignment)
                    if result is not None:
                        return result, None
                    # Conflict detected, need to backtrack
                    # Skip every 'irrelevant' var until var == best_var
                    elif var in visited and var != best_var:
                        conf_set[var].clear()
                        visited.discard(var)
                        csp.restore(removals)
                        csp.unassign(var, assignment)
                        return None, best_var
                csp.restore(removals)
        csp.unassign(var, assignment)
        visited.add(var)
        best_var = None
        # Find best var to jump back on
        if conf_set[var]:
            # Find the variable in conf_set[var] that is 'last' in order
            best_var = max(conf_set[var], key=order.get)    # best_var -> (in lectures -> Xh) the best variable to jump back on
        else:
            best_var = None
        if best_var is not None:
            conf_set[best_var].union(conf_set[var])
            conf_set[best_var].discard(best_var)
        return None, best_var

    result, _ = cbj({})
    assert result is None or csp.goal_test(result)
    return result

# DOM/WDEG HEURISTIC
def dom_wdeg_heuristic(assignment, csp):
    # dom -> prioritise vars with smaller remaining domain
    # wdeg -> prioritise vars involved in more constraints
    wdeg = {}
    max_score = float('-inf')
    best_var = None
    for var in csp.variables:
        if var in assignment:
            continue

        # Calculate the weighted degree of the variable
        wdeg[var] = 1
        for y in neighbours[var]:
            wdeg[var] += weight[(var, y)]

        # Get the current domain of the variable
        var_domain = csp.curr_domains[var] if csp.curr_domains else domains[var]

        # Calculate the score based on the weighted degree and domain size
        score = wdeg[var] / len(var_domain) if len(var_domain) > 0 else float('inf')

        # Update the best variable if the score is higher
        if score > max_score:
            max_score = score
            best_var = var     
    return best_var

# MIN-CONFLICTS
def min_conflicts(csp, max_steps=1000):
    """Solve a CSP by stochastic Hill Climbing on the number of conflicts."""
    # Generate a complete assignment for all variables (probably with conflicts)
    csp.current = current = {}
    for var in csp.variables:
        val = min_conflicts_value(csp, var, current)
        csp.assign(var, val, current)
    # Now repeatedly choose a random conflicted variable and change it
    for i in range(max_steps):
        conflicted = csp.conflicted_vars(current)
        if not conflicted:
            return current
        var = random.choice(conflicted)
        val = min_conflicts_value(csp, var, current)
        csp.assign(var, val, current)
    return None

variables = []
domains = {}
domain_values = {}
neighbours = {}
constraints = {}

def rlfap_constraint(A, a, B, b):
    global constraints
    key = constraints[(A, B)]
    operator, k = key
    if operator == '>':
        return abs(a - b) > k
    elif operator == '=':
        return abs(a - b) == k

def read_variable_file(file_path):
    global variables, domains
    with open(file_path, 'r') as file:
        lines = file.readlines()
        num_variables = int(lines[0].strip())
        variables = list(range(num_variables))
        domains = {}

        for line in lines[1:]:
            parts = line.strip().split()
            var_id = int(parts[0])
            domain_id = int(parts[1])
            domains[var_id] = domain_id

def read_domain_file(file_path):
    global domain_values
    with open(file_path, 'r') as file:
        lines = file.readlines()
        domain_values = {}
        for line in lines[1:]:
            parts = line.strip().split()
            domain_id = int(parts[0])
            values = list(map(int, parts[2:]))
            domain_values[domain_id] = values

def read_constraint_file(file_path):
    global constraints, neighbours
    neighbours = defaultdict(list)
    constraints = {}
    with open(file_path, 'r') as file:
        lines = file.readlines()
        for line in lines[1:]:
            parts = line.strip().split()
            x = int(parts[0])
            y = int(parts[1])
            operator = parts[2]
            k = int(parts[3])

            constraints[(x, y)] = (operator, k)
            constraints[(y, x)] = (operator, k)

            neighbours[x].append(y)
            neighbours[y].append(x)

def rlfap():
    args = list(sys.argv)
    files = []
    files.append(str('../rlfap/var' + args[1] + '.txt'))
    files.append(str('../rlfap/dom' + args[1] + '.txt'))
    files.append(str('../rlfap/ctr' + args[1] + '.txt'))
    
    # Read information from files
    read_variable_file(files[0])
    read_domain_file(files[1])
    read_constraint_file(files[2])

    # Update domains for each variable
    for i in variables:
        domains[i] = domain_values[domains[i]]

    return csp.CSP(variables, domains, neighbours, rlfap_constraint)

def main():
    # Create the RlfaCSP instance by extracting information from var/dom/ctr instances
    RlfaCSP = rlfap()

    # Initialise all weight counter to 1 for dom/wdeg heuristic
    for constr in constraints:
        weight[constr] = 1

    # Make conf_set a dict with var->set
    # and initialise the order of every var to 0
    for var in variables:
        conf_set[var] = set()
        order[var] = 0

    # Parse command-line arguments
    args = list(sys.argv)
    instance = args[1]
    algorithm = args[2]
    print(f"Instance: {instance}, Algorithm: {algorithm}\n")
    start_time = time.time()
    
    if algorithm == "FC":
        solution = csp.backtracking_search(RlfaCSP, select_unassigned_variable=dom_wdeg_heuristic, order_domain_values=csp.unordered_domain_values, inference=forward_checking)
    elif algorithm == "MAC":
        solution = csp.backtracking_search(RlfaCSP, select_unassigned_variable=dom_wdeg_heuristic, order_domain_values=csp.unordered_domain_values, inference=mac)
    elif algorithm == "FC-CBJ":
        solution = cbj_search(RlfaCSP, select_unassigned_variable=dom_wdeg_heuristic, order_domain_values=csp.unordered_domain_values, inference=forward_checking)
    elif algorithm == "Min-Conflicts":
        solution = min_conflicts(RlfaCSP)
    else:
        exit("Error: Algorithm should be FC/MAC/FC-CBJ/Min-Conflicts\n")

    end_time = time.time()
    print("NO SOLUTION" if solution == None else solution)    
    print("\nAssignments: %d" % RlfaCSP.nassigns)
    print(f"Time: {end_time - start_time:0.2f} seconds\n")

if __name__ == "__main__":
    if len(sys.argv) != 3: exit('Command should look like this: python3 rlfap.py <instanceID> <algorithm>\
                                \ninstanceID: 14-f28/11/6-w2 etc\nalgorithm: FC/MAC/FC-CBJ/Min-Conflicts')
    main()