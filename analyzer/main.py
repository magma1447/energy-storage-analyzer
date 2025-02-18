#!/usr/bin/env python3
import json
import sys
import os
import gzip
import argparse
from datetime import datetime
from .simulation import OptimizedBatterySimulation
from .visualization import create_viewer_html

def main():
    parser = argparse.ArgumentParser(description='Analyze potential battery savings from energy data')
    parser.add_argument('input_file', help='Input JSON file with energy data')
    parser.add_argument('--window', type=int, default=1440,
                        help='Optimization window size in minutes (default: 1440 = 24h)')
    parser.add_argument('--battery-capacity', type=float, default=24000,
                        help='Battery capacity in Wh (default: 24000 = 5 * 4800)')
    parser.add_argument('--depth-of-discharge', type=float, default=5.0,
                        help='Minimum battery level as percentage (default: 5.0)')
    parser.add_argument('--charging-loss', type=float, default=7.5,
                        help='Charging loss percentage (default: 7.5)')
    parser.add_argument('--discharging-loss', type=float, default=7.5,
                        help='Discharging loss percentage (default: 7.5)')
    parser.add_argument('--max-grid-power', type=float, default=17250,
                        help='Maximum grid charging power in watts (default: 17250 = 230V * 25A * 3 phases)')
    parser.add_argument('--output-dir', type=str, default='out',
                        help='Output directory for visualization files')
    parser.add_argument('--no-grid-charge', action='store_true',
                        help='Disable grid charging')
    parser.add_argument('--start-time', type=str,
                        help='Start time in ISO format (e.g., 2024-05-01T00:00:00Z)')
    parser.add_argument('--end-time', type=str,
                        help='End time in ISO format (e.g., 2024-05-02T00:00:00Z)')
    args = parser.parse_args()

    # Convert loss percentages to efficiency factors
    charging_efficiency = (100 - args.charging_loss) / 100
    discharging_efficiency = (100 - args.discharging_loss) / 100
    depth_of_discharge = args.depth_of_discharge / 100

    try:
        print(f"Reading input file {args.input_file}...")
        if args.input_file.endswith('.gz'):
            with gzip.open(args.input_file, 'rt') as f:
                data = json.load(f)
        else:
            with open(args.input_file, 'r') as f:
                data = json.load(f)

        # Filter data by date range if specified
        if args.start_time or args.end_time:
            filtered_data = {}
            start_time = args.start_time or min(data.keys())
            end_time = args.end_time or max(data.keys())

            print(f"Filtering data from {start_time} to {end_time}")
            for timestamp, values in data.items():
                if start_time <= timestamp <= end_time:
                    filtered_data[timestamp] = values
            data = filtered_data

        print(f"Loaded {len(data)} data points")
    except FileNotFoundError:
        print(f"Error: Could not find file {args.input_file}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in file {args.input_file}")
        sys.exit(1)
    except gzip.BadGzipFile:
        print(f"Error: Invalid gzip file {args.input_file}")
        sys.exit(1)

    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)

    # Run simulation with configured parameters
    simulation = OptimizedBatterySimulation(
        battery_capacity_wh=args.battery_capacity,
        enable_grid_charge=not args.no_grid_charge,
        depth_of_discharge=depth_of_discharge,
        charging_efficiency=charging_efficiency,
        discharging_efficiency=discharging_efficiency,
        max_charging_power_w=args.max_grid_power
    )
    simulation.process_data(data, args.window)
    simulation.print_summary()

    # Generate visualization data
    viz_data = {
        'config': {
            'batteryCapacity': simulation.BATTERY_CAPACITY_WH,
            'minLevel': simulation.MIN_BATTERY_LEVEL,
            'maxLevel': simulation.MAX_BATTERY_LEVEL
        },
        'timeSeries': [{
            'timestamp': ts,
            'batteryLevel': simulation.battery_levels[ts],
            'solarStored': simulation.flows['export_stored'].hourly_energy.get(ts, 0),
            'gridCharged': simulation.flows['grid_charged'].hourly_energy.get(ts, 0),
            'batteryUsed': simulation.flows['battery_used'].hourly_energy.get(ts, 0)
        } for ts in sorted(simulation.battery_levels.keys())]
    }
    
    # Create and write visualization files
    viewer_html = create_viewer_html(json.dumps(viz_data))
    html_path = os.path.join(args.output_dir, 'battery_viewer.html')
    with open(html_path, 'w') as f:
        f.write(viewer_html)
    
    print(f"\nVisualization file has been created: {html_path}")
    print("\nOpen this file in a web browser to view the interactive visualization.")

if __name__ == "__main__":
    main()
