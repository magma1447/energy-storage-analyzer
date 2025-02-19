#!/usr/bin/env python3
import json
import sys
import argparse
from datetime import datetime
from influxdb_client import InfluxDBClient
from typing import Dict, Any, List, Optional

def is_over_producing(data: Dict[str, Any]) -> bool:
    """
    Determine if power is being overproduced (negative values mean overproduction)
    """
    if 'solaredge_m1_ac_power_a' not in data or 'solaredge_m1_ac_power_b' not in data or 'solaredge_m1_ac_power_c' not in data:
        return False

    power_a = data['solaredge_m1_ac_power_a']
    power_b = data['solaredge_m1_ac_power_b']
    power_c = data['solaredge_m1_ac_power_c']
    return power_a + power_b + power_c < 0

def watts_to_wh(data: Dict[str, Any]) -> float:
    """
    Convert power readings to Wh
    """
    if 'solaredge_m1_ac_power_a' not in data or 'solaredge_m1_ac_power_b' not in data or 'solaredge_m1_ac_power_c' not in data:
        return 0

    power_a = data['solaredge_m1_ac_power_a']
    power_b = data['solaredge_m1_ac_power_b']
    power_c = data['solaredge_m1_ac_power_c']

    # Sum the three phases and divide by 60 to get Wh (for 1 minute intervals)
    total_power = power_a + power_b + power_c
    return total_power / 60

def fetch_data(start: str, end: str, config: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    """
    Fetches data from InfluxDB

    Args:
        start: Start time in InfluxDB format
        end: End time in InfluxDB format
        config: Configuration dict with url, token, org, bucket, etc.

    Returns:
        Dict with timestamps as keys, each value containing raw sensor data
    """
    # Initialize client
    influx = InfluxDBClient(
        url=config['url'],
        token=config['token'],
        org=config['org'],
        verify_ssl=False,
        timeout=60000
    )

    query_api = influx.query_api()
    data = {}

    # Fetch power data from the three phases
    power_entities = [
        {'domain': 'sensor', 'id': 'solaredge_m1_ac_power_a', 'unit': 'W'},
        {'domain': 'sensor', 'id': 'solaredge_m1_ac_power_b', 'unit': 'W'},
        {'domain': 'sensor', 'id': 'solaredge_m1_ac_power_c', 'unit': 'W'},
    ]

    for entity in power_entities:
        query = f'''
        from(bucket: "{config['bucket']}")
          |> range(start: {start}, stop: {end})
          |> filter(fn: (r) => r["domain"] == "{entity['domain']}")
          |> filter(fn: (r) => r["entity_id"] == "{entity['id']}")
          |> filter(fn: (r) => r["_field"] == "value")
          |> filter(fn: (r) => r["_measurement"] == "{entity['unit']}")
          |> aggregateWindow(every: 1m, fn: mean, createEmpty: true)
          |> fill(usePrevious: true)
          |> yield(name: "mean")
        '''
        print(f"Executing query for {entity['id']}...")

        result = query_api.query(query)

        for table in result:
            for record in table.records:
                t = record.values['_time'].strftime("%Y-%m-%dT%H:%M:%SZ")
                v = record.values['_value']

                if t not in data:
                    data[t] = {}
                data[t][entity['id']] = v

    # Fetch electricity price data
    price_entities = [
        {'domain': 'sensor', 'id': 'nordpool_kwh_se4_sek_2_10_025', 'unit': 'Öre/kWh'},
        {'domain': 'sensor', 'id': 'electricity_price_valavagen_23', 'unit': 'SEK/kWh'},
    ]

    for entity in price_entities:
        query = f'''
        from(bucket: "{config['bucket']}")
          |> range(start: {start}, stop: {end})
          |> filter(fn: (r) => r["domain"] == "{entity['domain']}")
          |> filter(fn: (r) => r["entity_id"] == "{entity['id']}")
          |> filter(fn: (r) => r["_field"] == "value")
          |> filter(fn: (r) => r["_measurement"] == "{entity['unit']}")
          |> aggregateWindow(every: 1m, fn: first, createEmpty: true)
          |> fill(usePrevious: true)
          |> yield(name: "first")
        '''
        print(f"Executing query for {entity['id']}...")

        result = query_api.query(query)

        for table in result:
            for record in table.records:
                t = record.values['_time'].strftime("%Y-%m-%dT%H:%M:%SZ")
                v = record.values['_value']

                if t not in data:
                    data[t] = {}
                data[t][entity['id']] = v

    # Fetch price level data
    price_level_entities = [
        {'domain': 'input_select', 'id': 'price_level_24h', 'unit': 'input_select.price_level_24h'},
    ]

    for entity in price_level_entities:
        query = f'''
        from(bucket: "{config['bucket']}")
          |> range(start: {start}, stop: {end})
          |> filter(fn: (r) => r["domain"] == "{entity['domain']}")
          |> filter(fn: (r) => r["entity_id"] == "{entity['id']}")
          |> filter(fn: (r) => r["_field"] == "state")
          |> filter(fn: (r) => r["_measurement"] == "{entity['unit']}")
          |> aggregateWindow(every: 1m, fn: first, createEmpty: true)
          |> fill(usePrevious: true)
          |> yield(name: "first")
        '''
        print(f"Executing query for {entity['id']}...")

        result = query_api.query(query)

        for table in result:
            for record in table.records:
                t = record.values['_time'].strftime("%Y-%m-%dT%H:%M:%SZ")
                v = record.values.get('_value', 'NORMAL')  # Default to NORMAL if missing

                if t not in data:
                    data[t] = {}
                data[t][entity['id']] = v

    # Fetch energy production data
    production_entities = [
        {'domain': 'sensor', 'id': 'energy_production_today', 'unit': 'kWh'},
        {'domain': 'sensor', 'id': 'energy_production_today_2', 'unit': 'kWh'},
        {'domain': 'sensor', 'id': 'energy_production_today_3', 'unit': 'kWh'},
    ]

    for entity in production_entities:
        query = f'''
        from(bucket: "{config['bucket']}")
          |> range(start: {start}, stop: {end})
          |> filter(fn: (r) => r["domain"] == "{entity['domain']}")
          |> filter(fn: (r) => r["entity_id"] == "{entity['id']}")
          |> filter(fn: (r) => r["_field"] == "value")
          |> filter(fn: (r) => r["_measurement"] == "{entity['unit']}")
          |> aggregateWindow(every: 1m, fn: first, createEmpty: true)
          |> fill(usePrevious: true)
          |> yield(name: "first")
        '''
        print(f"Executing query for {entity['id']}...")

        result = query_api.query(query)

        for table in result:
            for record in table.records:
                t = record.values['_time'].strftime("%Y-%m-%dT%H:%M:%SZ")
                v = record.values.get('_value', None)  # Allow None if missing

                if t not in data:
                    data[t] = {}
                data[t][entity['id']] = v

    return data

def postprocess_data(data: Dict[str, Dict[str, Any]], config: Dict[str, float]) -> Dict[str, Dict[str, Any]]:
    """
    Process raw data to add calculated fields exactly as in the PHP version
    """
    processed_data = {}

    for timestamp, values in sorted(data.items()):
        # Only process if we have the power data
        if all(k in values for k in ['solaredge_m1_ac_power_a', 'solaredge_m1_ac_power_b', 'solaredge_m1_ac_power_c',
                                     'nordpool_kwh_se4_sek_2_10_025', 'electricity_price_valavagen_23']):
            entry = {}

            # Calculate if over-producing
            entry['overProduction'] = is_over_producing(values)

            # Calculate Wh from power readings
            entry['Wh'] = watts_to_wh(values)

            # Calculate prices
            # Export price: (nordpool price in öre * 0.8 / 100) + tax reduction + network benefits
            entry['exportPrice'] = (values['nordpool_kwh_se4_sek_2_10_025'] * 0.8 / 100) + config['tax_reduction'] + config['network_benefits']

            # Import price: electricity price + transfer cost
            entry['importPrice'] = values['electricity_price_valavagen_23'] + config['transfer_cost']

            # Calculate export value and import cost
            entry['exportValue'] = (entry['Wh'] / 1000) * entry['exportPrice']
            entry['importCost'] = (-entry['Wh'] / 1000) * entry['importPrice']

            # Store only the fields needed by the simulation
            processed_data[timestamp] = {
                'Wh': entry['Wh'],
                'exportPrice': entry['exportPrice'],
                'importPrice': entry['importPrice']
            }

    return processed_data

def main():
    parser = argparse.ArgumentParser(description='Fetch energy data from InfluxDB')
    parser.add_argument('--url', required=True, help='InfluxDB URL')
    parser.add_argument('--token', required=True, help='InfluxDB authentication token')
    parser.add_argument('--org', required=True, help='InfluxDB organization')
    parser.add_argument('--bucket', required=True, help='InfluxDB bucket')
    parser.add_argument('--start', default='-30d', help='Start time in InfluxDB format (default: -30d)')
    parser.add_argument('--end', default='now()', help='End time in InfluxDB format (default: now())')
    parser.add_argument('--output', default='influx_data.json', help='Output file name (default: influx_data.json)')
    parser.add_argument('--tax-reduction', type=float, default=0.0, help='Tax reduction in SEK/kWh')
    parser.add_argument('--network-benefits', type=float, default=0.0, help='Network benefits in SEK/kWh')
    parser.add_argument('--transfer-cost', type=float, default=0.8, help='Transfer cost in SEK/kWh (default: 0.8)')

    args = parser.parse_args()

    # Create configuration dictionary
    influx_config = {
        'url': args.url,
        'token': args.token,
        'org': args.org,
        'bucket': args.bucket
    }

    processing_config = {
        'tax_reduction': args.tax_reduction,
        'network_benefits': args.network_benefits,
        'transfer_cost': args.transfer_cost
    }

    print(f"Fetching data from {args.start} to {args.end}...")
    raw_data = fetch_data(args.start, args.end, influx_config)

    print(f"Retrieved {len(raw_data)} raw data points. Postprocessing...")
    processed_data = postprocess_data(raw_data, processing_config)

    print(f"Processed {len(processed_data)} data points.")

    # Save to file
    with open(args.output, 'w') as f:
        json.dump(processed_data, f, indent=2)

    print(f"Data saved to {args.output}")

if __name__ == "__main__":
    main()
