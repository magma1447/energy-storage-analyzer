import unittest
import json
import gzip
from datetime import datetime
from analyzer.simulation import OptimizedBatterySimulation

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
        self.assertEqual(self.first_date.strftime("%Y-%m-%d %H:%M"), "2024-05-01 00:00")
        self.assertEqual(self.last_date.strftime("%Y-%m-%d %H:%M"), "2025-02-14 23:00")
        self.assertAlmostEqual(self.simulation_days, 290, places=0)
        
    def test_energy_flows(self):
        """Test main energy flow totals"""
        flows = self.simulation.flows
        self.assertAlmostEqual(flows['export_stored'].energy/1000, 3633.56, places=1)  # kWh
        self.assertAlmostEqual(flows['grid_charged'].energy/1000, 2982.36, places=1)   # kWh
        self.assertAlmostEqual(flows['battery_used'].energy/1000, 5660.75, places=1)   # kWh
        
    def test_financial_results(self):
        """Test financial outcomes"""
        flows = self.simulation.flows
        export_lost = flows['export_stored'].cost
        grid_cost = flows['grid_charged'].cost
        import_saved = flows['battery_used'].cost
        
        self.assertAlmostEqual(export_lost, 1014.14, places=1)  # SEK
        self.assertAlmostEqual(grid_cost, 3799.76, places=1)    # SEK
        self.assertAlmostEqual(import_saved, 13065.99, places=1) # SEK
        
        net_savings = import_saved - export_lost - grid_cost
        self.assertAlmostEqual(net_savings, 8252.09, places=1)  # SEK
        
    def test_battery_statistics(self):
        """Test battery state statistics"""
        # Test counts
        self.assertEqual(len(self.simulation.timestamps_full), 373)
        self.assertEqual(len(self.simulation.timestamps_empty), 326)
        
        # Test percentages
        hourly_samples = len(self.simulation.battery_levels)
        full_count = sum(1 for t in self.simulation.battery_levels.values() 
                        if t >= self.simulation.MAX_BATTERY_LEVEL * 0.99)
        empty_count = sum(1 for t in self.simulation.battery_levels.values() 
                         if t <= self.simulation.MIN_BATTERY_LEVEL * 1.01)
        
        full_percent = (full_count / hourly_samples) * 100
        empty_percent = (empty_count / hourly_samples) * 100
        partial_percent = 100 - full_percent - empty_percent
        
        self.assertAlmostEqual(full_percent, 11.5, places=1)
        self.assertAlmostEqual(empty_percent, 51.5, places=1)
        self.assertAlmostEqual(partial_percent, 37.0, places=1)
        
    def test_battery_cycles(self):
        """Test battery cycle calculations"""
        total_discharge = self.simulation.flows['battery_used'].energy / 1000  # kWh
        cycles = total_discharge / (self.simulation.BATTERY_CAPACITY_WH / 1000)
        cycles_per_day = cycles / self.simulation_days
        
        self.assertAlmostEqual(cycles, 235.9, places=1)
        self.assertAlmostEqual(cycles_per_day, 0.81, places=2)
        
    def test_monthly_breakdowns(self):
        """Test energy distribution across months"""
        # Test a sample month's values
        may_stored = self.simulation.flows['export_stored'].monthly_energy['2024-05'] / 1000
        may_grid = self.simulation.flows['grid_charged'].monthly_energy['2024-05'] / 1000
        may_used = self.simulation.flows['battery_used'].monthly_energy['2024-05'] / 1000
        
        self.assertAlmostEqual(may_stored, 724.67, places=1)  # kWh
        self.assertAlmostEqual(may_grid, 39.43, places=1)     # kWh
        self.assertAlmostEqual(may_used, 653.79, places=1)    # kWh

if __name__ == '__main__':
    unittest.main()
