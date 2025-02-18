#!/usr/bin/env python3
import json
import sys
import os
import argparse
from .simulation import OptimizedBatterySimulation
from .visualization import create_viewer_html

def main():
    parser = argparse.ArgumentParser(description='Analyze potential battery savings from energy data')
    parser.add_argument('input_file', help='Input JSON file with energy data')
    parser.add_argument('--window', type=int, default=1440,
                        help='Optimization window size in minutes (default: 1440 = 24h)')
    parser.add_argument('--battery-capacity', type=float, default=24000,
                        help='Battery capacity in Wh (default: 24000 = 5 * 4800)')
    parser.add_argument('--output-dir', type=str, default='.',
                        help='Output directory for visualization files')
    parser.add_argument('--no-grid-charge', action='store_true',
                        help='Disable grid charging')
    parser.add_argument('--start-time', type=str,
                        help='Start time in ISO format (e.g., 2024-05-01T00:00:00Z)')
    parser.add_argument('--end-time', type=str,
                        help='End time in ISO format (e.g., 2024-05-02T00:00:00Z)')
    args = parser.parse_args()
    
    try:
        print(f"Reading input file {args.input_file}...")
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
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
        
    # Run simulation
    simulation = OptimizedBatterySimulation(args.battery_capacity, not args.no_grid_charge)
    simulation.process_data(data, args.window)
    simulation.print_summary()
    

    # DEBUG
    #print("\nDebug - Available hours in battery_levels:")
    #for hour in sorted(simulation.battery_levels.keys())[:24]:  # Show first 24 entries
    #    print(f"  {hour}: {simulation.battery_levels[hour]}")
    #
    #print("\nDebug - Hours with grid charging:")
    #for hour in sorted(simulation.flows['grid_charged'].hourly_energy.keys())[:24]:
    #    value = simulation.flows['grid_charged'].hourly_energy[hour]
    #    if value > 0:
    #        print(f"  {hour}: {value:.2f} Wh")
    # -DEBUG

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
