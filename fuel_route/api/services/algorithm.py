from django.conf import settings

def compute_min_fuel_cost(stations, total_route_miles):
    MAX_RANGE = settings.MAX_RANGE_MILES
    MPG = settings.MPG
    TANK_CAPACITY = MAX_RANGE / MPG  # 50 gallons

    if not stations:
        return None, []

    # Only real stations — no virtual start/end
    # We begin with a full tank at mile 0, no cost
    # We must reach total_route_miles

    n = len(stations)

    # Add virtual end node
    end_node = {
        'dist_from_start': total_route_miles,
        'price': 0,
        'name': 'END',
        'is_virtual': True
    }
    nodes = stations + [end_node]
    total_nodes = len(nodes)

    INF = float('inf')

    # dp[i] = (min_cost_to_arrive_at_i, fuel_level_on_arrival)
    dp = [(INF, 0.0)] * total_nodes
    prev = [-1] * total_nodes

    # Start: we are at mile 0 with a full tank, cost 0
    # Find first reachable station
    start_dist = 0
    start_fuel = TANK_CAPACITY  # full tank at start
    start_cost = 0.0

    # Bootstrap: from start position reach each station
    for j in range(total_nodes):
        miles_to_j = nodes[j]['dist_from_start'] - start_dist
        if miles_to_j > MAX_RANGE:
            break
        fuel_used = miles_to_j / MPG
        fuel_on_arrival = start_fuel - fuel_used
        if fuel_on_arrival >= 0:
            dp[j] = (start_cost, fuel_on_arrival)
            prev[j] = -1  # came from start

    # DP over stations
    for i in range(total_nodes - 1):
        cost_here, fuel_on_arrival = dp[i]
        if cost_here == INF:
            continue

        current = nodes[i]
        if current.get('is_virtual'):
            continue

        current_price = current['price']
        current_dist = current['dist_from_start']

        # Find next cheaper station within range
        cheaper_idx = None
        for k in range(i + 1, total_nodes):
            miles = nodes[k]['dist_from_start'] - current_dist
            if miles > MAX_RANGE:
                break
            if nodes[k]['price'] <= current_price:
                cheaper_idx = k
                break

        # Decide how much to buy at station i
        for j in range(i + 1, total_nodes):
            next_node = nodes[j]
            miles_to_j = next_node['dist_from_start'] - current_dist

            if miles_to_j > MAX_RANGE:
                break

            fuel_needed = miles_to_j / MPG

            if cheaper_idx is not None and cheaper_idx <= j:
                # Buy just enough to reach the cheaper station
                miles_to_cheaper = nodes[cheaper_idx]['dist_from_start'] - current_dist
                fuel_to_cheaper = miles_to_cheaper / MPG
                gallons_to_buy = max(0, fuel_to_cheaper - fuel_on_arrival)
            else:
                # No cheaper station ahead — fill tank
                gallons_to_buy = max(0, TANK_CAPACITY - fuel_on_arrival)

            # Safety: ensure we have enough to reach j
            fuel_after_buy = fuel_on_arrival + gallons_to_buy
            if fuel_after_buy < fuel_needed:
                gallons_to_buy += (fuel_needed - fuel_after_buy)
                fuel_after_buy = fuel_needed

            fuel_at_j = fuel_after_buy - fuel_needed
            cost_of_stop = gallons_to_buy * current_price
            total_cost_at_j = cost_here + cost_of_stop

            if total_cost_at_j < dp[j][0]:
                dp[j] = (total_cost_at_j, fuel_at_j)
                prev[j] = i

    # Check END is reachable
    final_cost, _ = dp[total_nodes - 1]
    if final_cost == INF:
        return None, []

    # Traceback — skip END node
    stops = []
    idx = total_nodes - 1
    while idx != -1:
        node = nodes[idx]
        if not node.get('is_virtual'):
            stops.append(node)
        idx = prev[idx]

    stops.reverse()
    return round(final_cost, 2), stops
