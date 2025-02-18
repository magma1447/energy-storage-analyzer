import unittest
import json
import gzip
from datetime import datetime
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

class TestSimulationResults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Run simulation once for all tests"""
        # Load sample data
        with gzip.open('sample-data/partial-year1.json.gz', 'rt') as f:
            data = json.load(f)
            
        # Run simulation with default parameters
        cls.simulation = OptimizedBatterySimulation(
            battery_capacity_wh=24000,
            enable_grid_charge=True,
            depth_of_discharge=0.05,
            charging_efficiency=0.925,
            discharging_efficiency=0.925,
            max_charging_power_w=17250
        )
        cls.simulation.process_data(data, window_size=1440)
        
        # Calculate some common values used in multiple tests
        cls.all_hours = sorted(cls.simulation.battery_levels.keys())
        cls.first_date = datetime.strptime(cls.all_hours[0], "%Y-%m-%dT%H:00:00Z")
        cls.last_date = datetime.strptime(cls.all_hours[-1], "%Y-%m-%dT%H:00:00Z")
        cls.simulation_days = (cls.last_date - cls.first_date).total_seconds() / (24 * 3600)
        
    def test_simulation_period(self):
        """Test simulation period dates and duration"""
        expected = EXPECTED_RESULTS['simulation_period']
        self.assertEqual(self.first_date.strftime("%Y-%m-%d %H:%M"), expected['start_date'])
        self.assertEqual(self.last_date.strftime("%Y-%m-%d %H:%M"), expected['end_date'])
        self.assertAlmostEqual(self.simulation_days, expected['days'], places=0)
        
    def test_energy_flows(self):
        """Test main energy flow totals"""
        expected = EXPECTED_RESULTS['energy_flows']
        flows = self.simulation.flows
        self.assertAlmostEqual(flows['export_stored'].energy/1000, expected['export_stored'], places=1)
        self.assertAlmostEqual(flows['grid_charged'].energy/1000, expected['grid_charged'], places=1)
        self.assertAlmostEqual(flows['battery_used'].energy/1000, expected['battery_used'], places=1)
        
    def test_financial_results(self):
        """Test financial outcomes"""
        expected = EXPECTED_RESULTS['financial']
        flows = self.simulation.flows
        
        self.assertAlmostEqual(flows['export_stored'].cost, expected['export_lost'], places=1)
        self.assertAlmostEqual(flows['grid_charged'].cost, expected['grid_cost'], places=1)
        self.assertAlmostEqual(flows['battery_used'].cost, expected['import_saved'], places=1)
        
        net_savings = flows['battery_used'].cost - flows['export_stored'].cost - flows['grid_charged'].cost
        self.assertAlmostEqual(net_savings, expected['net_savings'], places=1)
        
    def test_battery_statistics(self):
        """Test battery state statistics"""
        expected = EXPECTED_RESULTS['battery_stats']
        
        # Test counts
        self.assertEqual(len(self.simulation.timestamps_full), expected['times_full'])
        self.assertEqual(len(self.simulation.timestamps_empty), expected['times_empty'])
        
        # Test percentages
        hourly_samples = len(self.simulation.battery_levels)
        full_count = sum(1 for t in self.simulation.battery_levels.values() 
                        if t >= self.simulation.MAX_BATTERY_LEVEL * 0.99)
        empty_count = sum(1 for t in self.simulation.battery_levels.values() 
                         if t <= self.simulation.MIN_BATTERY_LEVEL * 1.01)
        
        full_percent = (full_count / hourly_samples) * 100
        empty_percent = (empty_count / hourly_samples) * 100
        partial_percent = 100 - full_percent - empty_percent
        
        self.assertAlmostEqual(full_percent, expected['percent_full'], places=1)
        self.assertAlmostEqual(empty_percent, expected['percent_empty'], places=1)
        self.assertAlmostEqual(partial_percent, expected['percent_partial'], places=1)
        
    def test_battery_cycles(self):
        """Test battery cycle calculations"""
        expected = EXPECTED_RESULTS['battery_cycles']
        
        total_discharge = self.simulation.flows['battery_used'].energy / 1000  # kWh
        cycles = total_discharge / (self.simulation.BATTERY_CAPACITY_WH / 1000)
        cycles_per_day = cycles / self.simulation_days
        
        self.assertAlmostEqual(cycles, expected['total_cycles'], places=1)
        self.assertAlmostEqual(cycles_per_day, expected['cycles_per_day'], places=2)
        
    def test_monthly_energy(self):
        """Test monthly energy breakdowns"""
        expected = EXPECTED_RESULTS['monthly_energy']
        for month, values in expected.items():
            stored = self.simulation.flows['export_stored'].monthly_energy[month] / 1000
            grid = self.simulation.flows['grid_charged'].monthly_energy[month] / 1000
            used = self.simulation.flows['battery_used'].monthly_energy[month] / 1000
            
            self.assertAlmostEqual(stored, values['stored'], places=1)
            self.assertAlmostEqual(grid, values['grid'], places=1)
            self.assertAlmostEqual(used, values['used'], places=1)
            
    def test_monthly_financial(self):
        """Test monthly financial breakdowns"""
        expected = EXPECTED_RESULTS['monthly_financial']
        for month, values in expected.items():
            export_lost = self.simulation.flows['export_stored'].monthly_cost[month]
            grid_cost = self.simulation.flows['grid_charged'].monthly_cost[month]
            import_saved = self.simulation.flows['battery_used'].monthly_cost[month]
            
            self.assertAlmostEqual(export_lost, values['export_lost'], places=1)
            self.assertAlmostEqual(grid_cost, values['grid_cost'], places=1)
            self.assertAlmostEqual(import_saved, values['import_saved'], places=1)

if __name__ == '__main__':
    unittest.main()
