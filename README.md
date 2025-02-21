# energy-storage-analyzer
A tool to analyze existing energy data to see how much money an energy storing system would have saved.

Note that this is based on historical data, that you must have. And also of course historical prices, which you'll also have to provide. This doesn't tell the whole truth about the future.

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
