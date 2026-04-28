"""Main tax calculator: FIFO, NBP rates, capital gains."""

from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple

from .nbp import NBPClient


class TaxCalculator:
    """Calculate capital gains using FIFO with NBP rates."""

    def __init__(self, nbp_client: Optional[NBPClient] = None):
        """Initialize calculator with optional NBP client."""
        self.nbp = nbp_client or NBPClient()
        self.stock_fifo = defaultdict(list)
        self.crypto_fifo = defaultdict(list)

    def add_buy(
        self,
        symbol: str,
        quantity: Decimal,
        cost_per_unit: Decimal,
        currency: str,
        date_acquired: datetime,
        asset_type: str = "stock",
    ):
        """
        Add a buy transaction to FIFO queue.

        Args:
            symbol: Ticker/symbol
            quantity: Number of units
            cost_per_unit: Cost per unit in original currency
            currency: Currency code (e.g., 'USD')
            date_acquired: Transaction date
            asset_type: 'stock' or 'crypto'
        """
        fifo_queue = self.stock_fifo if asset_type == "stock" else self.crypto_fifo

        fifo_queue[symbol].append(
            {
                "quantity": quantity,
                "cost_per_unit": cost_per_unit,
                "currency": currency,
                "date_acquired": date_acquired,
                "total_cost": quantity * cost_per_unit,
            }
        )

    def calculate_sell(
        self,
        symbol: str,
        quantity: Decimal,
        proceeds_per_unit: Decimal,
        currency: str,
        date_sold: datetime,
        asset_type: str = "stock",
    ) -> Dict:
        """
        Calculate capital gain using FIFO.

        Args:
            symbol: Ticker/symbol
            quantity: Units sold
            proceeds_per_unit: Price per unit in original currency
            currency: Currency code
            date_sold: Sell date
            asset_type: 'stock' or 'crypto'

        Returns:
            {
                'symbol': str,
                'quantity': Decimal,
                'cost_basis_foreign': Decimal,  # Total cost in original currency (across all FIFO lots)
                'proceeds_foreign': Decimal,    # Total proceeds in original currency
                'cost_basis_pln': Decimal,
                'proceeds_pln': Decimal,
                'gain_pln': Decimal,
                'trades': [
                    {
                        'cost_pln': Decimal,
                        'proceeds_pln': Decimal,
                        'gain_pln': Decimal,
                    }
                ],
                'currency': str,
            }
        """
        fifo_queue = self.stock_fifo if asset_type == "stock" else self.crypto_fifo

        if symbol not in fifo_queue or not fifo_queue[symbol]:
            raise ValueError(f"No buy transactions for {symbol}")

        total_cost_pln = Decimal(0)
        total_proceeds_pln = Decimal(0)
        total_cost_foreign = Decimal(0)  # Sum of cost in original currency
        total_proceeds_foreign = Decimal(0)  # Sum of proceeds in original currency
        trades = []
        qty_remaining = quantity

        # FIFO: pop from front
        while qty_remaining > 0 and fifo_queue[symbol]:
            buy_lot = fifo_queue[symbol].pop(0)

            qty_this_trade = min(qty_remaining, buy_lot["quantity"])

            # Calculate foreign amounts first (before currency conversion)
            cost_foreign_this_lot = qty_this_trade * buy_lot["cost_per_unit"]
            proceeds_foreign_this_lot = qty_this_trade * proceeds_per_unit
            total_cost_foreign += cost_foreign_this_lot
            total_proceeds_foreign += proceeds_foreign_this_lot

            # Get NBP rate D-1 for cost
            cost_rate = self.nbp.get_rate(
                buy_lot["currency"], buy_lot["date_acquired"], use_d_minus_1=True
            )

            # Get NBP rate D-1 for proceeds
            proceeds_rate = self.nbp.get_rate(
                currency, date_sold, use_d_minus_1=True
            )

            cost_pln = (qty_this_trade * buy_lot["cost_per_unit"] * cost_rate).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            proceeds_pln = (
                qty_this_trade * proceeds_per_unit * proceeds_rate
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            gain_pln = proceeds_pln - cost_pln

            total_cost_pln += cost_pln
            total_proceeds_pln += proceeds_pln

            trades.append(
                {
                    "quantity": qty_this_trade,
                    "cost_pln": cost_pln,
                    "proceeds_pln": proceeds_pln,
                    "gain_pln": gain_pln,
                }
            )

            # Update buy lot if partial sale
            buy_lot["quantity"] -= qty_this_trade
            if buy_lot["quantity"] > 0:
                fifo_queue[symbol].insert(0, buy_lot)

            qty_remaining -= qty_this_trade

        if qty_remaining > 0:
            raise ValueError(
                f"Insufficient quantity for {symbol}: "
                f"tried to sell {quantity}, only {quantity - qty_remaining} available"
            )

        total_gain_pln = total_proceeds_pln - total_cost_pln

        return {
            "symbol": symbol,
            "quantity": quantity,
            "cost_basis_foreign": total_cost_foreign,
            "proceeds_foreign": total_proceeds_foreign,
            "cost_basis_pln": total_cost_pln,
            "proceeds_pln": total_proceeds_pln,
            "gain_pln": total_gain_pln,
            "trades": trades,
            "currency": currency,
        }

    def round_to_grosz(self, amount: Decimal) -> Decimal:
        """Round to 2 decimal places (grosz), .5 rounds up."""
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
