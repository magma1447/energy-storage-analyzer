from typing import Dict, Any, List
from collections import defaultdict
from .models import MinuteData, EnergyFlow, CHARGING_EFFICIENCY, DISCHARGING_EFFICIENCY

class OptimizedBatterySimulation:
    def __init__(self, battery_capacity_wh: float, enable_grid_charge: bool = True):
        # Battery-specific constants
        self.BATTERY_CAPACITY_WH = battery_capacity_wh
        self.MIN_BATTERY_LEVEL = battery_capacity_wh * 0.05  # 5% DoD
        self.MAX_BATTERY_LEVEL = battery_capacity_wh
        self.enable_grid_charge = enable_grid_charge
        
        # State
        self.battery_level = self.MIN_BATTERY_LEVEL
        self.flows = {
            'export_stored': EnergyFlow(),  # Excess solar stored
            'grid_charged': EnergyFlow(),   # Energy charged from grid
            'battery_used': EnergyFlow(),   # Energy discharged from battery
        }
        self.timestamps_full = []
        self.timestamps_empty = []
        self.actions_log = []
        self.battery_levels = defaultdict(float)  # Track battery level by hour

    def process_data(self, data: Dict[str, Dict[str, Any]], window_size: int = 1440) -> None:
        """Process data in sliding windows to enable look-ahead optimization"""
        print(f"\nProcessing data with {window_size} minute windows...")
        timestamps = sorted(data.keys())
        
        # Process in windows (default 24h = 1440 minutes)
        for i in range(0, len(timestamps), window_size):
            window_timestamps = timestamps[i:i + window_size]
            window_data = [MinuteData.from_json(ts, data[ts]) for ts in window_timestamps]
            self._optimize_window(window_data)

    def _optimize_window(self, window: List[MinuteData]) -> None:
        """Optimize battery usage for a time window"""
        if not window:
            return
            
        # Initialize collections
        excess_minutes = []
        deficit_minutes = []
        grid_charge_candidates = []
        
        # Sort minutes chronologically            
        minutes = sorted(window, key=lambda x: x.timestamp)
        
        # First pass: identify hours and categorize minutes
        for minute in minutes:
            hour = minute.timestamp[:13] + ":00:00Z"
            if hour not in self.battery_levels:
                self._store_battery_level(hour)
            
            if minute.wh > 0:
                excess_minutes.append(minute)
            else:
                deficit_minutes.append(minute)
                if minute.max_charging_power > 0:
                    grid_charge_candidates.append(minute)

        # Sort by price to optimize
        excess_minutes.sort(key=lambda x: x.export_price)  # Store when export price is lowest
        deficit_minutes.sort(key=lambda x: x.import_price, reverse=True)  # Use when import price is highest
        grid_charge_candidates.sort(key=lambda x: x.import_price)  # Charge from grid when price is lowest

        # Process in order
        for minute in excess_minutes:
            self._store_excess_power(minute)
            # Update battery level for the hour after storing excess
            hour = minute.timestamp[:13] + ":00:00Z"
            self.battery_levels[hour] = self.battery_level

        if self.enable_grid_charge:
            self._optimize_grid_charging(grid_charge_candidates, deficit_minutes)
            # Update battery levels after grid charging
            #for min in minutes:
            #    hour = min.timestamp[:13] + ":00:00Z"
            #    self.battery_levels[hour] = self.battery_level
            if grid_charge_candidates:
                hour = grid_charge_candidates[0].timestamp[:13] + ":00:00Z"
                self.battery_levels[hour] = self.battery_level

        for minute in deficit_minutes:
            self._use_stored_power(minute)
            # Update battery level for the hour after using power
            hour = minute.timestamp[:13] + ":00:00Z"
            self.battery_levels[hour] = self.battery_level

    def _store_battery_level(self, timestamp: str):
        """Store the battery level for the current hour"""
        hour = timestamp[:13] + ":00:00Z"  # Convert YYYY-MM-DDTHH to full hour
        self.battery_levels[hour] = self.battery_level

    def _store_excess_power(self, minute: MinuteData) -> None:
        """Store excess power, prioritizing lowest export price periods"""
        available_space = self.MAX_BATTERY_LEVEL - self.battery_level
        storable_before_losses = min(minute.wh, available_space / CHARGING_EFFICIENCY)
        
        if storable_before_losses > 0:
            stored_energy = storable_before_losses * CHARGING_EFFICIENCY
            self.battery_level += stored_energy
            
            # Track the energy flow
            self.flows['export_stored'].add(storable_before_losses, minute.export_price, minute.timestamp)

            if self.battery_level >= self.MAX_BATTERY_LEVEL * 0.99:
                self.timestamps_full.append(minute.timestamp)

    def _optimize_grid_charging(self, charge_candidates: List[MinuteData], 
                              usage_candidates: List[MinuteData]) -> None:
        """Determine if grid charging would be profitable"""
        if not charge_candidates or not usage_candidates:
            return

        for charge_minute in charge_candidates:
            if self.battery_level >= self.MAX_BATTERY_LEVEL:
                break

            # Find highest price usage periods that haven't been processed
            potential_usage = [m for m in usage_candidates 
                             if m.timestamp > charge_minute.timestamp 
                             and m.import_price > charge_minute.import_price * 1.2]  # 20% price difference threshold

            if potential_usage:
                # Calculate how much we could charge
                available_space = self.MAX_BATTERY_LEVEL - self.battery_level
                max_charge = min(
                    charge_minute.max_charging_power / 60,  # Convert W to Wh
                    available_space / CHARGING_EFFICIENCY
                )

                if max_charge > 0:
                    # Calculate potential profit
                    charge_cost = (max_charge * charge_minute.import_price / 1000)
                    discharge_energy = max_charge * CHARGING_EFFICIENCY * DISCHARGING_EFFICIENCY
                    potential_savings = discharge_energy * potential_usage[0].import_price / 1000

                    if potential_savings > charge_cost * 1.1:  # 10% minimum profit threshold
                        # Perform grid charging
                        stored_energy = max_charge * CHARGING_EFFICIENCY
                        self.battery_level += stored_energy
                        
                        # Track the energy flow
                        self.flows['grid_charged'].add(max_charge, charge_minute.import_price, charge_minute.timestamp)
                        
                        self.actions_log.append(
                            f"Grid charged {stored_energy:.2f}Wh at {charge_minute.timestamp} "
                            f"(price: {charge_minute.import_price:.3f}, future price: {potential_usage[0].import_price:.3f}, "
                            f"profit: {(potential_savings - charge_cost):.3f} SEK)"
                        )

    def _use_stored_power(self, minute: MinuteData) -> None:
        """Use stored power, prioritizing highest import price periods"""
        if minute.wh >= 0:
            return

        energy_needed = -minute.wh
        usable_battery_energy = (self.battery_level - self.MIN_BATTERY_LEVEL) * DISCHARGING_EFFICIENCY
        energy_from_battery = min(energy_needed, usable_battery_energy)
        
        if energy_from_battery > 0:
            actual_battery_drain = energy_from_battery / DISCHARGING_EFFICIENCY
            self.battery_level -= actual_battery_drain
            
            # Track the energy flow
            self.flows['battery_used'].add(energy_from_battery, minute.import_price, minute.timestamp)

            if self.battery_level <= self.MIN_BATTERY_LEVEL * 1.01:
                self.timestamps_empty.append(minute.timestamp)

    def print_summary(self) -> None:
        print("\nOptimized Battery Simulation Summary")
        print("=" * 50)
        
        print("\nBattery Configuration:")
        print(f"  Capacity: {self.BATTERY_CAPACITY_WH/1000:.1f} kWh")
        print(f"  Final level: {self.battery_level/1000:.2f} kWh")
        
        # Energy flows with monthly breakdown
        print("\nEnergy Flows:")
        print(f"Excess energy stored: {self.flows['export_stored'].energy/1000:.2f} kWh")
        for month in sorted(self.flows['export_stored'].monthly_energy.keys()):
            print(f"  {month}: {self.flows['export_stored'].monthly_energy[month]/1000:.2f} kWh")
            
        print(f"\nGrid energy charged: {self.flows['grid_charged'].energy/1000:.2f} kWh")
        for month in sorted(self.flows['grid_charged'].monthly_energy.keys()):
            print(f"  {month}: {self.flows['grid_charged'].monthly_energy[month]/1000:.2f} kWh")
            
        print(f"\nBattery energy used: {self.flows['battery_used'].energy/1000:.2f} kWh")
        for month in sorted(self.flows['battery_used'].monthly_energy.keys()):
            print(f"  {month}: {self.flows['battery_used'].monthly_energy[month]/1000:.2f} kWh")
        
        # Financial summary with monthly breakdown
        print("\nFinancial Summary:")
        print(f"Export value lost: {self.flows['export_stored'].cost:.2f} SEK")
        for month in sorted(self.flows['export_stored'].monthly_cost.keys()):
            print(f"  {month}: {self.flows['export_stored'].monthly_cost[month]:.2f} SEK")
            
        print(f"\nGrid charging cost: {self.flows['grid_charged'].cost:.2f} SEK")
        for month in sorted(self.flows['grid_charged'].monthly_cost.keys()):
            print(f"  {month}: {self.flows['grid_charged'].monthly_cost[month]:.2f} SEK")
            
        print(f"\nImport cost saved: {self.flows['battery_used'].cost:.2f} SEK")
        for month in sorted(self.flows['battery_used'].monthly_cost.keys()):
            print(f"  {month}: {self.flows['battery_used'].monthly_cost[month]:.2f} SEK")
            
        net_savings = (self.flows['battery_used'].cost - 
                      self.flows['export_stored'].cost - 
                      self.flows['grid_charged'].cost)
        print(f"\nNet savings: {net_savings:.2f} SEK")
        
        print("\nBattery State Statistics:")
        print(f"Number of times battery was full: {len(self.timestamps_full)}")
        print(f"Number of times battery was empty: {len(self.timestamps_empty)}")
        
        # Calculate time percentages
        hourly_samples = len(self.battery_levels)
        if hourly_samples > 0:
            full_count = sum(1 for t in self.battery_levels.values() 
                           if t >= self.MAX_BATTERY_LEVEL * 0.99)
            empty_count = sum(1 for t in self.battery_levels.values() 
                            if t <= self.MIN_BATTERY_LEVEL * 1.01)
            
            full_percent = (full_count / hourly_samples) * 100
            empty_percent = (empty_count / hourly_samples) * 100
            partial_percent = 100 - full_percent - empty_percent
            print(f"Battery was full {full_percent:.1f}% of the time")
            print(f"Battery was empty {empty_percent:.1f}% of the time")
            print(f"Battery was partially charged {partial_percent:.1f}% of the time")
        
        print("\nGrid Charging Actions (first 5):")
        for action in self.actions_log[:5]:
            print(f"  {action}")
