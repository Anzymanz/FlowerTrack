from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Flower:
    name: str
    thc_pct: float
    cbd_pct: float
    grams_remaining: float = 0.0

    def remove_by_grams(self, grams: float) -> None:
        if grams > self.grams_remaining:
            raise ValueError("Not enough stock for this dose.")
        self.grams_remaining -= grams

    def add_stock(self, grams: float, thc_pct: float, cbd_pct: float) -> None:
        if abs(thc_pct - self.thc_pct) > 1e-6 or abs(cbd_pct - self.cbd_pct) > 1e-6:
            raise ValueError("Potency for this flower does not match existing record.")
        # Set to the new absolute value rather than incrementing
        self.grams_remaining = grams
