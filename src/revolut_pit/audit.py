"""Audit trail and cross-validation for tax calculations.

Provides methods to validate calculations against source data and generate
audit trails for manual verification.
"""

from decimal import Decimal
from typing import Dict, List, Tuple, Optional


def validate_fifo_against_revolut(
    account_statement_transactions: List[Dict],
    revolut_pnl: List[Dict],
) -> List[Dict]:
    """
    Validate FIFO reconstruction against Revolut's P&L.

    Rebuilds FIFO independently from account statement and compares to Revolut's
    pre-calculated P&L to detect mismatches or discrepancies.

    Args:
        account_statement_transactions: List of buy/sell transactions from account statement
            Each dict should contain: symbol, type (BUY/SELL), quantity, price, date
        revolut_pnl: List of closed positions from Revolut P&L
            Each dict should contain: symbol, quantity, cost_basis, proceeds, date_sold

    Returns:
        List of mismatch dicts, empty if all match:
            [
                {
                    'symbol': str,
                    'type': 'quantity_mismatch' | 'cost_basis_mismatch' | 'proceeds_mismatch',
                    'revolut_value': Decimal,
                    'our_value': Decimal,
                    'diff_pct': Decimal,
                }
            ]
    """
    # Build independent FIFO from account statement
    fifo_queue = {}
    our_positions = {}

    for tx in sorted(account_statement_transactions, key=lambda x: x.get("date", "")):
        symbol = tx.get("symbol", "")
        tx_type = tx.get("type", "").upper()
        qty = Decimal(str(tx.get("quantity", 0)))
        price = Decimal(str(tx.get("price", 0)))

        if tx_type == "BUY":
            if symbol not in fifo_queue:
                fifo_queue[symbol] = []
            fifo_queue[symbol].append({
                "quantity": qty,
                "cost_per_unit": price,
            })

        elif tx_type == "SELL":
            if symbol not in fifo_queue or not fifo_queue[symbol]:
                continue  # Skip sells with no corresponding buys

            if symbol not in our_positions:
                our_positions[symbol] = {
                    "quantity": Decimal(0),
                    "cost_basis": Decimal(0),
                    "proceeds": Decimal(0),
                }

            qty_remaining = qty
            total_cost = Decimal(0)

            # FIFO: pop from front
            while qty_remaining > 0 and fifo_queue[symbol]:
                buy_lot = fifo_queue[symbol].pop(0)
                qty_this_lot = min(qty_remaining, buy_lot["quantity"])
                total_cost += qty_this_lot * buy_lot["cost_per_unit"]
                qty_remaining -= qty_this_lot

                # Reduce buy lot if partial
                buy_lot["quantity"] -= qty_this_lot
                if buy_lot["quantity"] > 0:
                    fifo_queue[symbol].insert(0, buy_lot)

            our_positions[symbol]["quantity"] += qty
            our_positions[symbol]["cost_basis"] += total_cost
            our_positions[symbol]["proceeds"] += qty * price

    # Compare with Revolut P&L
    mismatches = []

    for pos in revolut_pnl:
        symbol = pos.get("symbol", "")
        if symbol not in our_positions:
            continue  # No mismatch if position not in our reconstruction

        revolut_qty = Decimal(str(pos.get("quantity", 0)))
        our_qty = our_positions[symbol]["quantity"]

        if revolut_qty != our_qty:
            diff_pct = abs(revolut_qty - our_qty) / revolut_qty * Decimal(100) if revolut_qty else Decimal(0)
            mismatches.append({
                "symbol": symbol,
                "type": "quantity_mismatch",
                "revolut_value": revolut_qty,
                "our_value": our_qty,
                "diff_pct": diff_pct,
            })

        revolut_cost = Decimal(str(pos.get("cost_basis", 0)))
        our_cost = our_positions[symbol]["cost_basis"]

        if abs(revolut_cost - our_cost) > Decimal("0.01"):  # Allow 1 grosz rounding
            diff_pct = abs(revolut_cost - our_cost) / revolut_cost * Decimal(100) if revolut_cost else Decimal(0)
            mismatches.append({
                "symbol": symbol,
                "type": "cost_basis_mismatch",
                "revolut_value": revolut_cost,
                "our_value": our_cost,
                "diff_pct": diff_pct,
            })

    return mismatches


def cross_validate_stocks(
    closed_positions: List[Dict],
    revolut_pl_totals: Optional[Dict] = None,
) -> Tuple[Decimal, bool, str]:
    """
    Cross-validate stock calculations against Revolut data.

    Compares total proceeds (converted from PLN back to foreign currency using
    volume-weighted average NBP rate) vs. Revolut's total proceeds to detect
    calculation errors or data inconsistencies.

    Args:
        closed_positions: List of closed stock positions from pipeline
            Each dict should contain: proceeds_pln, proceeds_foreign, sell_rate_nbp
        revolut_pl_totals: Optional dict with 'total_proceeds_foreign' for comparison

    Returns:
        Tuple of (drift_percentage, is_warning, message)
        where drift_percentage is the % difference, is_warning is True if > 0.5%
    """
    if not closed_positions:
        return Decimal(0), False, "No stock positions to validate"

    # Calculate our total proceeds in PLN
    total_proceeds_pln = sum(
        p.get("proceeds_pln", Decimal(0)) for p in closed_positions
    )

    if total_proceeds_pln == 0:
        return Decimal(0), False, "No proceeds to validate"

    # Calculate volume-weighted average NBP rate
    # (more accurate than arithmetic mean for multi-position validation)
    total_proceeds_foreign = Decimal(0)
    for p in closed_positions:
        proceeds_pln = p.get("proceeds_pln", Decimal(0))
        rate = p.get("sell_rate_nbp", Decimal(0))
        if rate > 0:
            total_proceeds_foreign += proceeds_pln / rate

    if total_proceeds_foreign == 0:
        return Decimal(0), False, "No foreign proceeds found"

    # Volume-weighted effective rate
    effective_rate = total_proceeds_pln / total_proceeds_foreign

    # If we have Revolut's total, compare
    if revolut_pl_totals and "total_proceeds_foreign" in revolut_pl_totals:
        revolut_total = Decimal(str(revolut_pl_totals["total_proceeds_foreign"]))
        if revolut_total > 0:
            drift = abs(total_proceeds_foreign - revolut_total) / revolut_total * Decimal(100)
            is_warning = drift > Decimal("0.5")
            message = (
                f"Drift: {drift:.2f}%. Our proceeds: {total_proceeds_foreign:.2f}, "
                f"Revolut: {revolut_total:.2f}. Effective rate: {effective_rate:.6f}"
            )
            return drift, is_warning, message

    return Decimal(0), False, "Revolut totals not provided for comparison"


def nbp_url(currency: str, date) -> str:
    """
    Generate NBP API URL for verification.

    Converts a date and currency into the official NBP API URL that can be used
    to verify the rate we used in calculations.

    Args:
        currency: Currency code (e.g., 'USD', 'EUR')
        date: Date object or string (YYYY-MM-DD format)

    Returns:
        Full URL to NBP API endpoint for the given currency and date

    Example:
        >>> nbp_url('USD', '2025-06-13')
        'https://api.nbp.pl/api/exchangerates/rates/A/USD/2025-06-13/?format=json'
    """
    from datetime import datetime, date as date_type

    if isinstance(date, datetime):
        date_str = date.date().isoformat()
    elif isinstance(date, date_type):
        date_str = date.isoformat()
    else:
        date_str = str(date)

    # NBP API format: /api/exchangerates/rates/A/{currency}/{date}/
    # A = average rate for the day
    return f"https://api.nbp.pl/api/exchangerates/rates/A/{currency}/{date_str}/?format=json"


def audit_transaction(
    position: Dict,
    crypto: bool = False,
) -> Dict:
    """
    Create an audit record for a single transaction.

    Generates a detailed audit record that can be used to manually verify
    the calculation of a single position.

    Args:
        position: Position dict with all calculation details
        crypto: If True, assume crypto asset; if False, assume stock

    Returns:
        Dict with audit trail including formulas, rates, and verification links
    """
    audit = {
        "symbol": position.get("symbol", ""),
        "date_acquired": position.get("date_acquired", ""),
        "date_sold": position.get("date_sold", ""),
        "quantity": position.get("quantity", Decimal(0)),
        "currency": position.get("currency", "USD"),
        # Foreign amounts
        "cost_basis_foreign": position.get("cost_basis_foreign", Decimal(0)),
        "proceeds_foreign": position.get("proceeds_foreign", Decimal(0)),
        # NBP rates
        "nbp_rate_acquired": position.get("cost_rate_nbp", Decimal(0)),
        "nbp_rate_sold": position.get("sell_rate_nbp", Decimal(0)),
        # PLN amounts
        "cost_basis_pln": position.get("cost_basis_pln", Decimal(0)),
        "proceeds_pln": position.get("proceeds_pln", Decimal(0)),
        "gain_pln": position.get("gain_pln", Decimal(0)),
        # Verification URLs
        "nbp_url_acquired": nbp_url(
            position.get("currency", "USD"),
            position.get("date_acquired", ""),
        ),
        "nbp_url_sold": nbp_url(
            position.get("currency", "USD"),
            position.get("date_sold", ""),
        ),
        # Formulas for manual verification
        "formulas": {
            "cost_pln": f"{position.get('cost_basis_foreign', Decimal(0))} * {position.get('cost_rate_nbp', Decimal(0))}",
            "proceeds_pln": f"{position.get('proceeds_foreign', Decimal(0))} * {position.get('sell_rate_nbp', Decimal(0))}",
            "gain_pln": f"{position.get('proceeds_pln', Decimal(0))} - {position.get('cost_basis_pln', Decimal(0))}",
        },
    }
    return audit


def generate_audit_trail(
    stocks: List[Dict],
    crypto: List[Dict],
    dividends: List[Dict],
    nbp_rates: Dict[str, Decimal],
) -> Dict:
    """
    Generate complete audit trail for all transactions.

    Creates a comprehensive audit record that documents every calculation step
    with formulas and links to source data.

    Args:
        stocks: List of closed stock positions
        crypto: List of closed crypto positions
        dividends: List of dividend income items
        nbp_rates: Dict of all NBP rates used

    Returns:
        Dict with audit trail for all sections
    """
    audit_trail = {
        "stocks": [audit_transaction(s, crypto=False) for s in stocks],
        "crypto": [audit_transaction(c, crypto=True) for c in crypto],
        "dividends": [
            {
                "symbol": d.get("symbol", ""),
                "date": d.get("date", ""),
                "gross_foreign": d.get("gross_foreign", Decimal(0)),
                "wht_foreign": d.get("wht_foreign", Decimal(0)),
                "currency": d.get("currency", "USD"),
                "nbp_rate": d.get("nbp_rate", Decimal(0)),
                "gross_pln": d.get("gross_pln", Decimal(0)),
                "wht_pln": d.get("wht_pln", Decimal(0)),
                "country_code": d.get("country_code", ""),
                "treaty_rate": d.get("treaty_rate", Decimal(0)),
                "nbp_url": nbp_url(d.get("currency", "USD"), d.get("date", "")),
            }
            for d in dividends
        ],
        "nbp_rates_used": [
            {
                "currency": k.split("_")[0],
                "date": k.split("_")[1] if "_" in k else "",
                "rate": v,
                "url": nbp_url(k.split("_")[0], k.split("_")[1] if "_" in k else ""),
            }
            for k, v in nbp_rates.items()
        ],
    }
    return audit_trail
