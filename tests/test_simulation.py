#!/usr/bin/env python3
import sys
import json
import gzip
from datetime import datetime
import os

# Add the project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from analyzer.simulation import OptimizedBatterySimulation

# Expected results from sample-data/partial-year1.json.gz
EXPECTED_RESULTS = {
    'simulation_period': {
        'start_date': "2024-05-01 00:00",
        'end_date': "2025-02-14 23:00",
        'days': 290,
        'years': 0.79,
    },
    'energy_flows': {
        'export_stored': 3633.56,  # kWh
        'grid_charged': 2982.36,   # kWh
        'battery_used': 5660.75,   # kWh
    },
    'financial': {
        'export_lost': 1014.14,    # SEK
        'grid_cost': 3799.76,      # SEK
        'import_saved': 13065.99,  # SEK
        'net_savings': 8252.09,    # SEK
    },
    'battery_stats': {
        'times_full': 373,
        'times_empty': 326,
        'percent_full': 11.5,
        'percent_empty': 51.5,
        'percent_partial': 37.0,
    },
    'battery_cycles': {
        'total_cycles': 235.9,
        'cycles_per_day': 0.81,
    },
    'monthly_energy': {
        '2024-05': {'stored': 724.67, 'grid': 39.43, 'used': 653.79},
        '2024-06': {'stored': 665.77, 'grid': 73.68, 'used': 632.70},
        '2024-07': {'stored': 661.44, 'grid': 102.67, 'used': 653.79},
        '2024-08': {'stored': 653.51, 'grid': 70.83, 'used': 619.77},
        '2024-09': {'stored': 558.13, 'grid': 108.25, 'used': 570.17},
        '2024-10': {'stored': 325.69, 'grid': 320.98, 'used': 553.31},
        '2024-11': {'stored': 22.46, 'grid': 618.57, 'used': 548.48},
        '2024-12': {'stored': 2.44, 'grid': 558.20, 'used': 479.70},
        '2025-01': {'stored': 6.39, 'grid': 757.72, 'used': 653.79},
        '2025-02': {'stored': 13.06, 'grid': 332.02, 'used': 295.26},
    },
    'monthly_financial': {
        '2024-05': {'export_lost': 170.46, 'grid_cost': 35.87, 'import_saved': 1400.99},
        '2024-06': {'export_lost': 209.76, 'grid_cost': 71.05, 'import_saved': 1541.52},
        '2024-07': {'export_lost': 177.04, 'grid_cost': 122.69, 'import_saved': 1362.50},
        '2024-08': {'export_lost': 128.21, 'grid_cost': 76.24, 'import_saved': 1401.30},
        '2024-09': {'export_lost': 157.04, 'grid_cost': 104.61, 'import_saved': 1032.44},
        '2024-10': {'export_lost': 117.35, 'grid_cost': 350.73, 'import_saved': 990.25},
        '2024-11': {'export_lost': 17.92, 'grid_cost': 856.96, 'import_saved': 1527.41},
        '2024-12': {'export_lost': 3.63, 'grid_cost': 679.14, 'import_saved': 1285.15},
        '2025-01': {'export_lost': 13.81, 'grid_cost': 944.06, 'import_saved': 1617.74},
        '2025-02': {'export_lost': 18.93, 'grid_cost': 558.39, 'import_saved': 906.67},
    },
}

def run_tests():
    """Run all battery simulation tests"""
    success_count = 0
    failure_count = 0
    test_results = []

    # Load sample data
    with gzip.open('sample-data/partial-year1.json.gz', 'rt') as f:
        data = json.load(f)

    # Run simulation with default parameters
    simulation = OptimizedBatterySimulation(
        battery_capacity_wh=24000,
        enable_grid_charge=True,
        depth_of_discharge=0.05,
        charging_efficiency=0.925,
        discharging_efficiency=0.925,
        max_charging_power_w=17250
    )
    simulation.process_data(data, window_size=1440)

    # Calculate some common values used in multiple tests
    all_hours = sorted(simulation.battery_levels.keys())
    first_date = datetime.strptime(all_hours[0], "%Y-%m-%dT%H:00:00Z")
    last_date = datetime.strptime(all_hours[-1], "%Y-%m-%dT%H:00:00Z")
    simulation_days = (last_date - first_date).total_seconds() / (24 * 3600)

    # Helper function to check and record test results
    def check_and_record(category, test_name, expected, current, tolerance=0.1):
        if isinstance(expected, (int, float)) and isinstance(current, (int, float)):
            success = abs(current - expected) <= tolerance
        else:
            success = current == expected

        if success:
            nonlocal success_count
            success_count += 1
        else:
            nonlocal failure_count
            failure_count += 1

        test_results.append({
            'category': category,
            'test': test_name,
            'expected': expected,
            'current': current,
            'success': success
        })

        return success

    # Test: Simulation Period
    expected = EXPECTED_RESULTS['simulation_period']

    # Test start date
    current_start = first_date.strftime("%Y-%m-%d %H:%M")
    check_and_record('simulation_period', 'start_date',
                    expected['start_date'], current_start)

    # Test end date
    current_end = last_date.strftime("%Y-%m-%d %H:%M")
    check_and_record('simulation_period', 'end_date',
                    expected['end_date'], current_end)

    # Test days
    current_days = round(simulation_days, 1)
    check_and_record('simulation_period', 'days',
                    expected['days'], current_days, 1)

    # Test years
    current_years = round(simulation_days / 365, 2)
    check_and_record('simulation_period', 'years',
                    expected['years'], current_years, 0.01)

    # Test: Energy Flows
    expected = EXPECTED_RESULTS['energy_flows']
    flows = simulation.flows

    # Test export_stored
    current_export_stored = round(flows['export_stored'].energy/1000, 2)
    check_and_record('energy_flows', 'export_stored',
                    expected['export_stored'], current_export_stored)

    # Test grid_charged
    current_grid_charged = round(flows['grid_charged'].energy/1000, 2)
    check_and_record('energy_flows', 'grid_charged',
                    expected['grid_charged'], current_grid_charged)

    # Test battery_used
    current_battery_used = round(flows['battery_used'].energy/1000, 2)
    check_and_record('energy_flows', 'battery_used',
                    expected['battery_used'], current_battery_used)

    # Test: Financial Results
    expected = EXPECTED_RESULTS['financial']

    # Test export_lost
    current_export_lost = round(flows['export_stored'].cost, 2)
    check_and_record('financial', 'export_lost',
                    expected['export_lost'], current_export_lost)

    # Test grid_cost
    current_grid_cost = round(flows['grid_charged'].cost, 2)
    check_and_record('financial', 'grid_cost',
                    expected['grid_cost'], current_grid_cost)

    # Test import_saved
    current_import_saved = round(flows['battery_used'].cost, 2)
    check_and_record('financial', 'import_saved',
                    expected['import_saved'], current_import_saved)

    # Test net_savings
    current_net_savings = round(flows['battery_used'].cost - flows['export_stored'].cost - flows['grid_charged'].cost, 2)
    check_and_record('financial', 'net_savings',
                    expected['net_savings'], current_net_savings)

    # Test: Battery Statistics
    expected = EXPECTED_RESULTS['battery_stats']

    # Test counts
    current_times_full = len(simulation.timestamps_full)
    check_and_record('battery_stats', 'times_full',
                    expected['times_full'], current_times_full, 0)

    current_times_empty = len(simulation.timestamps_empty)
    check_and_record('battery_stats', 'times_empty',
                    expected['times_empty'], current_times_empty, 0)

    # Test percentages
    hourly_samples = len(simulation.battery_levels)
    full_count = sum(1 for t in simulation.battery_levels.values()
                    if t >= simulation.MAX_BATTERY_LEVEL * 0.99)
    empty_count = sum(1 for t in simulation.battery_levels.values()
                     if t <= simulation.MIN_BATTERY_LEVEL * 1.01)

    full_percent = round((full_count / hourly_samples) * 100, 1)
    check_and_record('battery_stats', 'percent_full',
                    expected['percent_full'], full_percent)

    empty_percent = round((empty_count / hourly_samples) * 100, 1)
    check_and_record('battery_stats', 'percent_empty',
                    expected['percent_empty'], empty_percent)

    partial_percent = round(100 - full_percent - empty_percent, 1)
    check_and_record('battery_stats', 'percent_partial',
                    expected['percent_partial'], partial_percent)

    # Test: Battery Cycles
    expected = EXPECTED_RESULTS['battery_cycles']

    total_discharge = simulation.flows['battery_used'].energy / 1000  # kWh
    cycles = round(total_discharge / (simulation.BATTERY_CAPACITY_WH / 1000), 1)
    check_and_record('battery_cycles', 'total_cycles',
                    expected['total_cycles'], cycles)

    cycles_per_day = round(cycles / simulation_days, 2)
    check_and_record('battery_cycles', 'cycles_per_day',
                    expected['cycles_per_day'], cycles_per_day, 0.01)

    # Test: Monthly Energy
    expected = EXPECTED_RESULTS['monthly_energy']
    for month, values in expected.items():
        stored = round(simulation.flows['export_stored'].monthly_energy[month] / 1000, 2)
        check_and_record('monthly_energy', f"{month} -> stored",
                        values['stored'], stored)

        grid = round(simulation.flows['grid_charged'].monthly_energy[month] / 1000, 2)
        check_and_record('monthly_energy', f"{month} -> grid",
                        values['grid'], grid)

        used = round(simulation.flows['battery_used'].monthly_energy[month] / 1000, 2)
        check_and_record('monthly_energy', f"{month} -> used",
                        values['used'], used)

    # Test: Monthly Financial
    expected = EXPECTED_RESULTS['monthly_financial']
    for month, values in expected.items():
        export_lost = round(simulation.flows['export_stored'].monthly_cost[month], 2)
        check_and_record('monthly_financial', f"{month} -> export_lost",
                        values['export_lost'], export_lost)

        grid_cost = round(simulation.flows['grid_charged'].monthly_cost[month], 2)
        check_and_record('monthly_financial', f"{month} -> grid_cost",
                        values['grid_cost'], grid_cost)

        import_saved = round(simulation.flows['battery_used'].monthly_cost[month], 2)
        check_and_record('monthly_financial', f"{month} -> import_saved",
                        values['import_saved'], import_saved)

    # Print test results in a nicely formatted way
    print_test_results(test_results, success_count, failure_count)

    # Return exit code
    return 0 if failure_count == 0 else 1

def print_test_results(test_results, success_count, failure_count):
    """Print formatted test results"""
    print("\nTest Results:")
    print("=============")

    current_category = None

    for result in test_results:
        if result['category'] != current_category:
            current_category = result['category']
            print(f"\n{current_category}:")
            print("-" * (len(current_category) + 1))

        status = "Success" if result['success'] else "FAIL   "
        expected_val = result['expected']
        current_val = result['current']

        # Format numbers consistently
        if isinstance(expected_val, (int, float)) and isinstance(current_val, (int, float)):
            if isinstance(expected_val, int):
                expected_str = f"{expected_val}"
                current_str = f"{current_val}"
                diff_str = f"{current_val - expected_val:+d}" if not result['success'] else ""
            else:
                # Determine number of decimal places based on the expected value
                if expected_val == int(expected_val):
                    decimal_places = 0
                elif expected_val * 10 == int(expected_val * 10):
                    decimal_places = 1
                else:
                    decimal_places = 2

                expected_str = f"{expected_val:.{decimal_places}f}"
                current_str = f"{current_val:.{decimal_places}f}"
                diff_str = f"{current_val - expected_val:+.{decimal_places}f}" if not result['success'] else ""
        else:
            expected_str = str(expected_val)
            current_str = str(current_val)
            diff_str = ""

        if result['success'] or diff_str == "":
            print(f"{status}: {result['test']:<25} expected={expected_str:<10} current={current_str:<10}")
        else:
            print(f"{status}: {result['test']:<25} expected={expected_str:<10} current={current_str:<10} diff={diff_str}")

    # Print summary
    total_tests = success_count + failure_count
    print("\nTest Summary:")
    print(f"Total tests: {total_tests}")
    print(f"Successes:   {success_count}")
    print(f"Failures:    {failure_count}")
    print(f"Success rate: {(success_count / total_tests) * 100:.1f}%")

if __name__ == '__main__':
    sys.exit(run_tests())
