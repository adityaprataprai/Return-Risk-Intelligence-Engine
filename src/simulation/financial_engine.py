from typing import Dict
from .entities import Product, Return


class FinancialEngine:
    """Calculates unit economics, exposure, and recovery values for orders and returns."""

    @staticmethod
    def calculate_logistics_cost(product: Product) -> float:
        """Calculates total logistics cost of handling a return."""
        return round(
            product.return_shipping_cost + product.handling_cost + product.restocking_cost,
            2,
        )

    @staticmethod
    def calculate_salvage_value(refund_amount: float, salvage_value_percentage: float) -> float:
        """Calculates recoverable salvage value after return inspection."""
        return round(refund_amount * salvage_value_percentage, 2)

    @classmethod
    def compute_return_economics(
        cls, refund_amount: float, product: Product
    ) -> Dict[str, float]:
        """Calculates gross exposure, logistics cost, salvage value, and net return cost."""
        logistics_costs = cls.calculate_logistics_cost(product)
        gross_exposure = round(refund_amount + logistics_costs, 2)
        salvage_value = cls.calculate_salvage_value(
            refund_amount, product.salvage_value_percentage
        )
        net_return_cost = round(gross_exposure - salvage_value, 2)

        return {
            "gross_exposure": gross_exposure,
            "logistics_costs": logistics_costs,
            "salvage_value": salvage_value,
            "net_return_cost": net_return_cost,
        }
