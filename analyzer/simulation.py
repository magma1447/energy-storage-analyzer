from typing import Dict, Any, List
from collections import defaultdict
from datetime import datetime
from .models import MinuteData, EnergyFlow

class OptimizedBatterySimulation:
    def __init__(self, battery_capacity_wh: float, enable_grid_charge: bool = True,
                 depth_of_discharge: float = 0.05, charging_efficiency: float = 0.925,
                 discharging_efficiency: float = 0.925, max_charging_power_w: float = 17250,
                 loss_multiplier: float = 1.25):
        # Configuration
        self.BATTERY_CAPACITY_WH = battery_capacity_wh
        self.MIN_BATTERY_LEVEL = battery_capacity_wh * depth_of_discharge
        self.MAX_BATTERY_LEVEL = battery_capacity_wh
        self.enable_grid_charge = enable_grid_charge
        self.charging_efficiency = charging_efficiency
        self.discharging_efficiency = discharging_efficiency
        self.max_charging_power_w = max_charging_power_w
        self.loss_multiplier = loss_multiplier

        # Calculate compound losses from both charging and discharging
        combined_losses = 1 - (charging_efficiency * discharging_efficiency)
        self.min_price_ratio = 1 + (combined_losses * loss_multiplier)

        print(f"\nGrid charging parameters:")
        print(f"  Combined losses: {combined_losses*100:.1f}%")
        print(f"  Loss multiplier: {loss_multiplier:.4f}")
        print(f"  Required price ratio: {self.min_price_ratio:.4f} ({(self.min_price_ratio-1)*100:.1f}%)")

        # Store for reporting
        self.combined_losses = combined_losses

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
            window_data = [MinuteData.from_json(ts, data[ts], self.max_charging_power_w)
                          for ts in window_timestamps]
            self._optimize_window(window_data)

    def _optimize_window(self, window: List[MinuteData]) -> None:
        """Optimize battery usage for a time window"""
        if not window:
            return

        # Initialize collections
        excess_minutes = []
        deficit_minutes = []
        grid_charge_candidates = []

        # Track hourly battery changes
        hourly_changes = defaultdict(float)
        initial_battery_level = self.battery_level

        # First pass: identify hours and categorize minutes
        for minute in window:
            if minute.wh > 0:
                excess_minutes.append(minute)
            else:
                deficit_minutes.append(minute)
                if minute.max_charging_power > 0:
                    grid_charge_candidates.append(minute)

        # Sort by price to optimize, putting negative prices first, then lowest export price
        excess_minutes.sort(key=lambda x: (x.export_price >= 0, x.export_price))
        deficit_minutes.sort(key=lambda x: x.import_price, reverse=True)  # Use when import price is highest
        grid_charge_candidates.sort(key=lambda x: x.import_price)  # Charge from grid when price is lowest

        # Reset battery level for accurate tracking
        self.battery_level = initial_battery_level

        # Process in batches
        # 1. First store all excess power
        for minute in excess_minutes:
            before_level = self.battery_level
            self._store_excess_power(minute)
            # Track hourly change
            hour = minute.timestamp[:13] + ":00:00Z"
            hourly_changes[hour] += self.battery_level - before_level

        # 2. Then handle grid charging
        if self.enable_grid_charge:
            for minute in grid_charge_candidates:
                potential_usage = [m for m in deficit_minutes
                                 if m.timestamp > minute.timestamp
                                 and m.import_price > minute.import_price * self.min_price_ratio]

                if potential_usage:
                    before_level = self.battery_level
                    self._perform_grid_charging(minute, potential_usage[0])
                    # Track hourly change
                    hour = minute.timestamp[:13] + ":00:00Z"
                    hourly_changes[hour] += self.battery_level - before_level

        # 3. Finally use stored power
        for minute in deficit_minutes:
            before_level = self.battery_level
            self._use_stored_power(minute)
            # Track hourly change
            hour = minute.timestamp[:13] + ":00:00Z"
            hourly_changes[hour] += self.battery_level - before_level

        # Update battery levels for all affected hours
        for hour in sorted(hourly_changes.keys()):
            # If this is the first entry for this hour, use the initial level
            if hour not in self.battery_levels:
                prev_hour = max((h for h in self.battery_levels.keys() if h < hour), default=None)
                base_level = self.battery_levels[prev_hour] if prev_hour else initial_battery_level
                self.battery_levels[hour] = base_level + hourly_changes[hour]
            else:
                self.battery_levels[hour] += hourly_changes[hour]

    def _perform_grid_charging(self, charge_minute: MinuteData, usage_minute: MinuteData) -> None:
        """Perform grid charging if profitable"""
        if self.battery_level >= self.MAX_BATTERY_LEVEL:
            return

        # First, check price difference (like the old code did)
        price_ratio = usage_minute.import_price / charge_minute.import_price
        required_ratio = 1 + (0.2 * self.loss_multiplier)

        if price_ratio >= required_ratio:
            # Calculate how much we could charge
            available_space = self.MAX_BATTERY_LEVEL - self.battery_level
            max_charge = min(
                charge_minute.max_charging_power / 60,  # Convert W to Wh
                available_space / self.charging_efficiency
            )

            if max_charge > 0:
                # Calculate potential profit considering losses
                charge_cost = (max_charge * charge_minute.import_price / 1000)
                discharge_energy = max_charge * self.charging_efficiency * self.discharging_efficiency
                potential_savings = discharge_energy * usage_minute.import_price / 1000

                # Debug for January 2025
                # if charge_minute.timestamp.startswith("2025-01"):
                #     print(f"\nDEBUG {charge_minute.timestamp}:")
                #     print(f"  Import prices: {charge_minute.import_price:.4f} -> {usage_minute.import_price:.4f}")
                #     print(f"  Price ratio: {price_ratio:.4f}")
                #     print(f"  Required ratio: {required_ratio:.4f}")
                #     print(f"  Potential savings: {potential_savings:.2f} SEK")
                #     print(f"  Charge cost: {charge_cost:.2f} SEK")

                if potential_savings > charge_cost:  # Must be profitable after losses
                    stored_energy = max_charge * self.charging_efficiency
                    self.battery_level += stored_energy

                    # Track the energy flow
                    self.flows['grid_charged'].add(max_charge, charge_minute.import_price, charge_minute.timestamp)

                    # if charge_minute.timestamp.startswith("2025-01"):
                    #     self.actions_log.append(
                    #         f"Grid charged {stored_energy:.2f}Wh at {charge_minute.timestamp} "
                    #         f"(price: {charge_minute.import_price:.3f}, future price: {usage_minute.import_price:.3f}, "
                    #         f"ratio: {price_ratio:.3f}, profit: {(potential_savings - charge_cost):.3f} SEK)"
                    #     )

    def _store_battery_level(self, timestamp: str):
        """Store the battery level for the current hour"""
        hour = timestamp[:13] + ":00:00Z"  # Convert YYYY-MM-DDTHH to full hour
        self.battery_levels[hour] = self.battery_level

    def _store_excess_power(self, minute: MinuteData) -> None:
        """Store excess power, prioritizing lowest export price periods"""
        available_space = self.MAX_BATTERY_LEVEL - self.battery_level
        storable_before_losses = min(minute.wh, available_space / self.charging_efficiency)

        if storable_before_losses > 0:
            stored_energy = storable_before_losses * self.charging_efficiency
            self.battery_level += stored_energy
            
            # Track the energy flow
            self.flows['export_stored'].add(storable_before_losses, minute.export_price, minute.timestamp)

            if self.battery_level >= self.MAX_BATTERY_LEVEL * 0.99:
                self.timestamps_full.append(minute.timestamp)

    def _use_stored_power(self, minute: MinuteData) -> None:
        """Use stored power, prioritizing highest import price periods"""
        if minute.wh >= 0:
            return

        energy_needed = -minute.wh
        usable_battery_energy = (self.battery_level - self.MIN_BATTERY_LEVEL) * self.discharging_efficiency
        energy_from_battery = min(energy_needed, usable_battery_energy)

        if energy_from_battery > 0:
            actual_battery_drain = energy_from_battery / self.discharging_efficiency
            self.battery_level -= actual_battery_drain
            
            # Track the energy flow
            self.flows['battery_used'].add(energy_from_battery, minute.import_price, minute.timestamp)

            if self.battery_level <= self.MIN_BATTERY_LEVEL * 1.01:
                self.timestamps_empty.append(minute.timestamp)

    def print_summary(self) -> None:
            print("\nOptimized Battery Simulation Summary")
            print("=" * 50)

            # Find first and last dates
            all_hours = sorted(self.battery_levels.keys())
            first_date = datetime.strptime(all_hours[0], "%Y-%m-%dT%H:00:00Z")

            # For the last date, we need to add 59:59 to show the true end time
            last_hour = datetime.strptime(all_hours[-1], "%Y-%m-%dT%H:00:00Z")
            last_date = datetime(last_hour.year, last_hour.month, last_hour.day,
                                last_hour.hour, 59, 59)

            # Format dates and calculate duration
            first_date_str = first_date.strftime("%Y-%m-%d %H:%M")
            last_date_str = last_date.strftime("%Y-%m-%d %H:%M")
            days = (last_date - first_date).total_seconds() / (24 * 3600)
            years = days / 365.25

            print(f"\nTime period: {first_date_str} to {last_date_str}")
            print(f"  Days: {days:.0f} ({years:.2f} years)")

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

            # Add section about negative prices
            print("\nNegative Price Statistics:")
            for flow_name, flow in self.flows.items():
                if flow.negative_price_energy > 0:
                    print(f"WARNING: {flow_name}: {flow.negative_price_energy/1000:.2f} kWh during negative prices")
                    print(f"         Cost impact: {flow.negative_price_cost:.2f} SEK")
            if all(flow.negative_price_energy == 0 for flow in self.flows.values()):
                print("No energy was handled during negative prices")

            # Add warning about price margin if it's too low
            current_margin = self.min_price_ratio - 1
            if current_margin < self.combined_losses:
                print(f"\nWARNING: Current price margin ({current_margin*100:.1f}%) is lower than")
                print(f"         combined losses ({self.combined_losses*100:.1f}%) from")
                print(f"         charging loss ({(1-self.charging_efficiency)*100:.1f}%) and")
                print(f"         discharging loss ({(1-self.discharging_efficiency)*100:.1f}%)")

            net_savings = (self.flows['battery_used'].cost -
                          self.flows['export_stored'].cost -
                          self.flows['grid_charged'].cost)
            print(f"\nNet savings: {net_savings:.2f} SEK")

            # Calculate yearly estimate based on simulation period
            years = days / 365.25  # We already calculated days earlier in the method
            if years > 0:
                yearly_estimate = net_savings / years
                print(f"  Rough estimate: {yearly_estimate:.2f} SEK/year (disclaimer: not a true value)")

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

                # Calculate battery cycles
                total_discharge = self.flows['battery_used'].energy / 1000  # Convert to kWh
                cycles = total_discharge / (self.BATTERY_CAPACITY_WH / 1000)

                print(f"Number of battery cycles: {cycles:.1f}")
                print(f"Average cycles per day: {(cycles/hourly_samples*24):.2f}")
