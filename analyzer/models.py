from dataclasses import dataclass
from typing import Dict, Any
from collections import defaultdict

@dataclass
class MinuteData:
    timestamp: str
    wh: float
    import_price: float
    export_price: float
    max_charging_power: float

    @classmethod
    def from_json(cls, timestamp: str, data: Dict[str, Any], max_charging_power_w: float) -> 'MinuteData':
        return cls(
            timestamp=timestamp,
            wh=data['Wh'],
            import_price=data['importPrice'],
            export_price=data['exportPrice'],
            max_charging_power=max_charging_power_w + data['Wh']  # Available charging power
        )

class EnergyFlow:
    def __init__(self):
        self.energy = 0.0
        self.cost = 0.0
        self.monthly_energy = defaultdict(float)
        self.monthly_cost = defaultdict(float)
        self.hourly_energy = defaultdict(float)

    def add(self, energy: float, price: float, timestamp: str):
        """Add energy (in Wh) and its associated cost/value (in SEK)"""
        self.energy += energy
        cost = (energy / 1000) * price  # Convert to kWh for price calculation
        self.cost += cost

        # Track monthly data
        month = timestamp[:7]  # Get YYYY-MM
        self.monthly_energy[month] += energy
        self.monthly_cost[month] += cost

        # Track hourly data for visualization
        hour = timestamp[:13] + ":00:00Z"  # Convert YYYY-MM-DDTHH to full hour
        self.hourly_energy[hour] += energy