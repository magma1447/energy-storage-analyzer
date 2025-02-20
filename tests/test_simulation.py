#!/usr/bin/env python3
import sys
import json
import gzip
import argparse
from datetime import datetime
import os

# Add the project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from analyzer.simulation import OptimizedBatterySimulation

def run_simulation():
    """Run simulation and return results"""
    # Load sample data
    with gzip.open('sample-data/partial-year2.json.gz', 'rt') as f:
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

    # Gather current results
    current_results = {
        'simulation_period': {
            'start_date': first_date.strftime("%Y-%m-%d %H:%M"),
            'end_date': last_date.strftime("%Y-%m-%d %H:%M"),
            'days': round(simulation_days, 1),
            'years': round(simulation_days / 365, 2),
        },
        'energy_flows': {
            'export_stored': round(simulation.flows['export_stored'].energy/1000, 2),
            'grid_charged': round(simulation.flows['grid_charged'].energy/1000, 2),
            'battery_used': round(simulation.flows['battery_used'].energy/1000, 2),
        },
        'financial': {
            'export_lost': round(simulation.flows['export_stored'].cost, 2),
            'grid_cost': round(simulation.flows['grid_charged'].cost, 2),
            'import_saved': round(simulation.flows['battery_used'].cost, 2),
            'net_savings': round(simulation.flows['battery_used'].cost -
                                simulation.flows['export_stored'].cost -
                                simulation.flows['grid_charged'].cost, 2),
        },
        'battery_stats': {
            'times_full': len(simulation.timestamps_full),
            'times_empty': len(simulation.timestamps_empty),
            'percent_full': round((sum(1 for t in simulation.battery_levels.values()
                                    if t >= simulation.MAX_BATTERY_LEVEL * 0.99) /
                                len(simulation.battery_levels)) * 100, 1),
            'percent_empty': round((sum(1 for t in simulation.battery_levels.values()
                                     if t <= simulation.MIN_BATTERY_LEVEL * 1.01) /
                                 len(simulation.battery_levels)) * 100, 1),
        },
        'battery_cycles': {
            'total_cycles': round(simulation.flows['battery_used'].energy /
                                 (simulation.BATTERY_CAPACITY_WH), 1),
            'cycles_per_day': round((simulation.flows['battery_used'].energy /
                                    simulation.BATTERY_CAPACITY_WH) /
                                   simulation_days, 2),
        },
        'monthly_energy': {},
        'monthly_financial': {}
    }

    # Calculate percent_partial after the other percentages
    current_results['battery_stats']['percent_partial'] = round(
        100 - current_results['battery_stats']['percent_full'] -
        current_results['battery_stats']['percent_empty'], 1
    )

    # Gather monthly energy data
    for month in sorted(simulation.flows['export_stored'].monthly_energy.keys()):
        current_results['monthly_energy'][month] = {
            'stored': round(simulation.flows['export_stored'].monthly_energy[month] / 1000, 2),
            'grid': round(simulation.flows['grid_charged'].monthly_energy[month] / 1000, 2),
            'used': round(simulation.flows['battery_used'].monthly_energy[month] / 1000, 2)
        }

    # Gather monthly financial data
    for month in sorted(simulation.flows['export_stored'].monthly_cost.keys()):
        current_results['monthly_financial'][month] = {
            'export_lost': round(simulation.flows['export_stored'].monthly_cost[month], 2),
            'grid_cost': round(simulation.flows['grid_charged'].monthly_cost[month], 2),
            'import_saved': round(simulation.flows['battery_used'].monthly_cost[month], 2)
        }

    return current_results, simulation

def create_expected_results_file(filename):
    """Create a new expected results file from current simulation results"""
    current_results, _ = run_simulation()

    with open(filename, 'w') as f:
        json.dump(current_results, f, indent=2)

    print(f"Created new expected results file: {filename}")
    return 0

def run_tests(expected_results_file):
    """Run all battery simulation tests against expected results"""
    success_count = 0
    failure_count = 0
    test_results = []

    # Load expected results
    try:
        with open(expected_results_file, 'r') as f:
            expected_results = json.load(f)
    except FileNotFoundError:
        print(f"Error: Expected results file '{expected_results_file}' not found.")
        print(f"Use '--create {expected_results_file}' to create it.")
        return 1

    # Run simulation
    current_results, simulation = run_simulation()

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
    for key, expected_value in expected_results['simulation_period'].items():
        current_value = current_results['simulation_period'][key]
        tolerance = 1 if key == 'days' else 0.01 if key == 'years' else 0.1
        check_and_record('simulation_period', key, expected_value, current_value, tolerance)

    # Test: Energy Flows
    for key, expected_value in expected_results['energy_flows'].items():
        current_value = current_results['energy_flows'][key]
        check_and_record('energy_flows', key, expected_value, current_value)

    # Test: Financial Results
    for key, expected_value in expected_results['financial'].items():
        current_value = current_results['financial'][key]
        check_and_record('financial', key, expected_value, current_value)

    # Test: Battery Statistics
    for key, expected_value in expected_results['battery_stats'].items():
        current_value = current_results['battery_stats'][key]
        tolerance = 0 if key in ['times_full', 'times_empty'] else 0.1
        check_and_record('battery_stats', key, expected_value, current_value, tolerance)

    # Test: Battery Cycles
    for key, expected_value in expected_results['battery_cycles'].items():
        current_value = current_results['battery_cycles'][key]
        tolerance = 0.1 if key == 'total_cycles' else 0.01
        check_and_record('battery_cycles', key, expected_value, current_value, tolerance)

    # Test: Monthly Energy
    for month, values in expected_results['monthly_energy'].items():
        for key, expected_value in values.items():
            if month in current_results['monthly_energy']:
                current_value = current_results['monthly_energy'][month][key]
                check_and_record('monthly_energy', f"{month} -> {key}", expected_value, current_value)
            else:
                check_and_record('monthly_energy', f"{month} -> {key}", expected_value, None)

    # Test: Monthly Financial
    for month, values in expected_results['monthly_financial'].items():
        for key, expected_value in values.items():
            if month in current_results['monthly_financial']:
                current_value = current_results['monthly_financial'][month][key]
                check_and_record('monthly_financial', f"{month} -> {key}", expected_value, current_value)
            else:
                check_and_record('monthly_financial', f"{month} -> {key}", expected_value, None)

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

def main():
    """Parse arguments and run tests or create expected results file"""
    parser = argparse.ArgumentParser(description='Battery Simulation Test Suite')
    parser.add_argument('--create', metavar='FILE', help='Create a new expected results file')
    parser.add_argument('--expected', metavar='FILE', default='tests/expected_results.json',
                       help='Specify the expected results file (default: tests/expected_results.json)')

    args = parser.parse_args()

    if args.create:
        return create_expected_results_file(args.create)
    else:
        return run_tests(args.expected)

if __name__ == '__main__':
    sys.exit(main())
