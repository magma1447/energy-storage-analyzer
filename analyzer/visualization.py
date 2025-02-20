import json

def create_viewer_html(json_data: str) -> str:
    """Create an HTML page with embedded visualization of battery data"""
    return f"""<!DOCTYPE html>
<html>
<head>
    <title>Battery Analysis Visualization</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.24.2/plotly.min.js"></script>
    <style>
        body {{ margin: 0; padding: 20px; font-family: Arial, sans-serif; }}
        .chart-container {{ height: 800px; }}
        .controls {{ margin-bottom: 20px; }}
    </style>
</head>
<body>
    <div class="controls">
        <button onclick="resetZoom()">Reset Zoom</button>
        <span id="stats"></span>
    </div>
    <div id="chart" class="chart-container"></div>

    <script>
        // Embed the JSON data directly
        const jsonData = {json_data};
        const data = jsonData.timeSeries;
        const batteryConfig = jsonData.config;

        function createCharts() {{
            const timestamps = data.map(d => d.timestamp);
            
            // Combined chart with battery level and energy flows - all on same y-axis
            const traces = [{{
                name: 'Battery Level',
                x: timestamps,
                y: data.map(d => d.batteryLevel / 1000), // Show raw values
                type: 'scatter',
                mode: 'lines',
                line: {{ shape: 'hv', color: 'purple', width: 2 }}
            }}, {{
                name: 'Min Level',
                x: timestamps,
                y: Array(timestamps.length).fill(batteryConfig.minLevel / 1000),
                type: 'scatter',
                mode: 'lines',
                line: {{
                    shape: 'hv',
                    color: 'red',
                    dash: 'dash',
                    width: 1
                }}
            }}, {{
                name: 'Max Level',
                x: timestamps,
                y: Array(timestamps.length).fill(batteryConfig.maxLevel / 1000),
                type: 'scatter',
                mode: 'lines',
                line: {{
                    shape: 'hv',
                    color: 'green',
                    dash: 'dash',
                    width: 1
                }}
            }}, {{
                name: 'Solar Stored',
                x: timestamps,
                y: data.map(d => d.solarStored / 1000), // Show raw values
                type: 'scatter',
                mode: 'lines',
                line: {{ shape: 'hv', color: 'green' }}
            }}, {{
                name: 'Grid Charged',
                x: timestamps,
                y: data.map(d => d.gridCharged / 1000), // Show raw values
                type: 'scatter',
                mode: 'lines',
                line: {{ shape: 'hv', color: 'red' }}
            }}, {{
                name: 'Battery Used',
                x: timestamps,
                y: data.map(d => d.batteryUsed / 1000), // Show raw values
                type: 'scatter',
                mode: 'lines',
                line: {{ shape: 'hv', color: 'blue' }}
            }}];

            // Calculate min and max values for y-axis scaling
            const allValues = [
                ...data.map(d => d.batteryLevel / 1000),
                ...data.map(d => d.solarStored / 1000),
                ...data.map(d => d.gridCharged / 1000),
                ...data.map(d => d.batteryUsed / 1000)
            ].filter(v => !isNaN(v) && v !== null && v !== undefined);

            const minValue = Math.min(0, ...allValues); // Use 0 or actual minimum if lower
            const maxValue = Math.max(
                batteryConfig.batteryCapacity / 1000,
                ...allValues
            );

            const layout = {{
                title: 'Battery State and Energy Flows',
                xaxis: {{
                    title: 'Time',
                    tickformat: '%Y-%m-%d %H:%M'
                }},
                yaxis: {{
                    title: 'Energy (kWh)',
                    range: [minValue, maxValue],
                    side: 'left'
                }},
                legend: {{
                    x: 1.05,
                    y: 1
                }},
                hovermode: 'x unified',
                margin: {{
                    r: 50,
                    t: 30,
                    b: 50,
                    l: 60
                }}
            }};

            Plotly.newPlot('chart', traces, layout);
        }}

        function updateStats() {{
            const totalSamples = data.length;
            const fullCount = data.filter(d => d.batteryLevel >= batteryConfig.maxLevel * 0.99).length;
            const emptyCount = data.filter(d => d.batteryLevel <= batteryConfig.minLevel * 1.01).length;

            const fullPercent = (fullCount / totalSamples * 100).toFixed(1);
            const emptyPercent = (emptyCount / totalSamples * 100).toFixed(1);
            const partialPercent = (100 - parseFloat(fullPercent) - parseFloat(emptyPercent)).toFixed(1);

            document.getElementById('stats').textContent =
                `Battery State: ${{fullPercent}}% Full, ${{emptyPercent}}% Empty, ${{partialPercent}}% Partial`;
        }}

        function resetZoom() {{
            // Calculate min and max values for reset
            const allValues = [
                ...data.map(d => d.batteryLevel / 1000),
                ...data.map(d => d.solarStored / 1000),
                ...data.map(d => d.gridCharged / 1000),
                ...data.map(d => d.batteryUsed / 1000)
            ].filter(v => !isNaN(v) && v !== null && v !== undefined);

            const minValue = Math.min(0, ...allValues);
            const maxValue = Math.max(
                batteryConfig.batteryCapacity / 1000,
                ...allValues
            );

            Plotly.relayout('chart', {{
                'xaxis.autorange': true,
                'yaxis.range': [minValue, maxValue]
            }});
        }}

        // Create charts immediately since data is embedded
        createCharts();
        updateStats();
    </script>
</body>
</html>
"""
