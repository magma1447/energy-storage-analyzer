# energy-storage-analyzer
A tool to analyze existing energy data to see how much money an energy storing system would have saved.

The software handles this:
- Storing excess solar power.
- Charge from grid.
- Use stored energy when most profitable.

Note that this is based on historical data, that you must have. And also of course historical prices, which you'll also have to provide. This doesn't tell the whole truth about the future. In fact, since this is based on **real** and **historical** data, where the prediction could be perfect, this **should** give a better result than in reality.

# Usage
`python3 -m analyzer.main sample-data/partial-year2.json.gz`

Additional options:
```
usage: main.py [-h] [--window WINDOW] [--battery-capacity BATTERY_CAPACITY]
               [--depth-of-discharge DEPTH_OF_DISCHARGE] [--charging-loss CHARGING_LOSS]
               [--discharging-loss DISCHARGING_LOSS] [--max-grid-power MAX_GRID_POWER]
               [--output-dir OUTPUT_DIR] [--no-grid-charge] [--start-time START_TIME]
               [--end-time END_TIME]
               input_file

Analyze potential battery savings from energy data

positional arguments:
  input_file            Input JSON file with energy data

options:
  -h, --help            show this help message and exit
  --window WINDOW       Optimization window size in minutes (default: 1440 = 24h)
  --battery-capacity BATTERY_CAPACITY
                        Battery capacity in Wh (default: 24000 = 5 * 4800)
  --depth-of-discharge DEPTH_OF_DISCHARGE
                        Minimum battery level as percentage (default: 5.0)
  --charging-loss CHARGING_LOSS
                        Charging loss percentage (default: 7.5)
  --discharging-loss DISCHARGING_LOSS
                        Discharging loss percentage (default: 7.5)
  --max-grid-power MAX_GRID_POWER
                        Maximum grid charging power in watts (default: 17250 = 230V * 25A * 3
                        phases)
  --output-dir OUTPUT_DIR
                        Output directory for visualization files
  --no-grid-charge      Disable grid charging
  --start-time START_TIME
                        Start time in ISO format (e.g., 2024-05-01T00:00:00Z)
  --end-time END_TIME   End time in ISO format (e.g., 2024-05-02T00:00:00Z)
```

# Data
The software reads data in the following format.
```
{
  "2024-05-01T00:01:00Z": {
    "Wh": -92.49444444444445,
    "importPrice": 1.4260000000000002,
    "exportPrice": 0.5008
  },
  "2024-05-01T00:02:00Z": {
    "Wh": -94.23333333333333,
    "importPrice": 1.4260000000000002,
    "exportPrice": 0.5008
  },
  ...
}

```
The analytics will work best if you include **all** costs/benefits that scales with (k)Wh.

The code has been designed with minutely data in mind. It's untested how it behaves with lower and higher data resolutions. The higher the resolution, the higher the accurancy of the output though.

# Visual representation
By using the `--output-dir` option the code generates a chart showing when different actions happens. With this you should be able to get a better understanding of the flow of energy and the battery level. This will be rendered as a single html file so that you easily can open it in your web browser.


# Tests
`python3 tests/test_simulation.py`

Verifies that the output data is as expected with the given sample file.

# Influx fetcher
```
python3 influx_fetcher.py \
  --url "influx-url" \
  --token "access-token" \
  --org "your-org" \
  --bucket "your-bucket" \
  --start "2024-05-01" \
  --end "2025-02-14T23:59:59Z" \
  --output "sample-data/partial-year3.json" \
  --tax-reduction 0 \
  --network-benefits 0.08 \
  --transfer-cost 0.8
```

Hint: Needs `python3-influxdb-client` on Debian. Or equivalents in other distributions.

# Sample output data

This is output from the analyzer, based on real data.

```
$ time python3 -m analyzer.main sample-data/partial-year2.json.gz --output-dir ./out
Reading input file sample-data/partial-year2.json.gz...
Loaded 417600 data points

Grid charging parameters:
  Combined losses: 14.4%
  Loss multiplier: 1.2500
  Required price ratio: 1.1805 (18.0%)

Processing data with 1440 minute windows...

Optimized Battery Simulation Summary
==================================================

Time period: 2024-05-01 00:00 to 2025-02-14 23:59
  Days: 290 (0.79 years)

Battery Configuration:
  Capacity: 24.0 kWh
  Final level: 1.20 kWh

Energy Flows:
Excess energy stored: 3633.56 kWh
  2024-05: 724.67 kWh
  2024-06: 665.77 kWh
  2024-07: 661.44 kWh
  2024-08: 653.51 kWh
  2024-09: 558.13 kWh
  2024-10: 325.69 kWh
  2024-11: 22.46 kWh
  2024-12: 2.44 kWh
  2025-01: 6.39 kWh
  2025-02: 13.06 kWh

Grid energy charged: 3070.07 kWh
  2024-05: 39.43 kWh
  2024-06: 73.68 kWh
  2024-07: 102.67 kWh
  2024-08: 70.83 kWh
  2024-09: 108.25 kWh
  2024-10: 328.46 kWh
  2024-11: 618.57 kWh
  2024-12: 638.42 kWh
  2025-01: 757.72 kWh
  2025-02: 332.02 kWh

Battery energy used: 5735.79 kWh
  2024-05: 653.79 kWh
  2024-06: 632.70 kWh
  2024-07: 653.79 kWh
  2024-08: 619.77 kWh
  2024-09: 570.17 kWh
  2024-10: 559.71 kWh
  2024-11: 548.48 kWh
  2024-12: 548.34 kWh
  2025-01: 653.79 kWh
  2025-02: 295.26 kWh

Financial Summary:
Export value lost: 1014.14 SEK
  2024-05: 170.46 SEK
  2024-06: 209.76 SEK
  2024-07: 177.04 SEK
  2024-08: 128.21 SEK
  2024-09: 157.04 SEK
  2024-10: 117.35 SEK
  2024-11: 17.92 SEK
  2024-12: 3.63 SEK
  2025-01: 13.81 SEK
  2025-02: 18.93 SEK

Grid charging cost: 3903.10 SEK
  2024-05: 35.87 SEK
  2024-06: 71.05 SEK
  2024-07: 122.69 SEK
  2024-08: 76.24 SEK
  2024-09: 104.61 SEK
  2024-10: 358.60 SEK
  2024-11: 856.96 SEK
  2024-12: 774.62 SEK
  2025-01: 944.06 SEK
  2025-02: 558.39 SEK

Import cost saved: 13173.57 SEK
  2024-05: 1400.99 SEK
  2024-06: 1541.52 SEK
  2024-07: 1362.50 SEK
  2024-08: 1401.30 SEK
  2024-09: 1032.44 SEK
  2024-10: 998.24 SEK
  2024-11: 1527.41 SEK
  2024-12: 1384.75 SEK
  2025-01: 1617.74 SEK
  2025-02: 906.67 SEK

Negative Price Statistics:
WARNING: export_stored: 200.34 kWh during negative prices
         Cost impact: -32.40 SEK

Net savings: 8256.33 SEK
  Rough estimate: 10398.71 SEK/year (disclaimer: not a true value)

Battery State Statistics:
Number of times battery was full: 373
Number of times battery was empty: 329
Battery was full 18.8% of the time
Battery was empty 28.9% of the time
Battery was partially charged 52.4% of the time
Number of battery cycles: 239.0
Average cycles per day: 0.82

Visualization file has been created: ./out/battery_viewer.html
Open this file in a web browser to view the interactive visualization.
```
