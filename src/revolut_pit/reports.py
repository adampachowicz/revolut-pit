"""Generate Excel and Markdown reports."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment


class ReportGenerator:
    """Generate Excel and Markdown reports from tax calculations."""

    def __init__(self, output_dir: Path):
        """Initialize report generator."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_excel(
        self,
        pit38_result: Dict,
        stocks: List[Dict],
        crypto: List[Dict],
        dividends: List[Dict],
        nbp_rates_used: Dict,
        filename: str = "pit38_report.xlsx",
    ) -> Path:
        """
        Generate comprehensive Excel report.

        Sheets: summary, stocks, crypto, dividends, nbp_rates
        """
        filepath = self.output_dir / filename
        wb = Workbook()
        wb.remove(wb.active)  # Remove default sheet

        # Summary sheet
        self._add_summary_sheet(wb, pit38_result)

        # Stocks sheet
        if stocks:
            self._add_stocks_sheet(wb, stocks)

        # Crypto sheet
        if crypto:
            self._add_crypto_sheet(wb, crypto)

        # Dividends sheet
        if dividends:
            self._add_dividends_sheet(wb, dividends)

        # NBP rates sheet
        if nbp_rates_used:
            self._add_nbp_rates_sheet(wb, nbp_rates_used)

        wb.save(filepath)
        return filepath

    def generate_markdown(
        self,
        pit38_result: Dict,
        stocks: List[Dict],
        crypto: List[Dict],
        dividends: List[Dict],
        filename: str = "pit38_report.md",
    ) -> Path:
        """Generate markdown report."""
        filepath = self.output_dir / filename

        lines = [
            "# PIT-38 Tax Report",
            f"\n**Rok podatkowy:** {pit38_result['rok_podatkowy']}",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "\n## Summary\n",
        ]

        # Summary section
        c = pit38_result["czesc_C"]
        lines.extend(
            [
                "### Part C: Securities (Papiery wartościowe)",
                f"- Revenue (przychód): {c['przychod_pln']:,.2f} PLN",
                f"- Cost (koszt): {c['koszt_pln']:,.2f} PLN",
                f"- Income (dochód): {c['dochod_pln']:,.2f} PLN",
                f"- Tax @ 19%: {c['dochod_pln'] * Decimal('0.19'):,.2f} PLN",
            ]
        )

        c = pit38_result["czesc_E"]
        lines.extend(
            [
                "\n### Part E: Crypto",
                f"- Revenue (przychód): {c['przychod_pln']:,.2f} PLN",
                f"- Cost (koszt): {c['koszt_pln']:,.2f} PLN",
                f"- Income (dochód): {c['dochod_pln']:,.2f} PLN",
                f"- Tax @ 19%: {c['dochod_pln'] * Decimal('0.19'):,.2f} PLN",
            ]
        )

        c = pit38_result["czesc_D"]
        lines.extend(
            [
                "\n### Part D: Dividends",
                f"- Gross income (przychód): {c['przychod_pln']:,.2f} PLN",
                f"- Polish tax @ 19%: {c['podatek_pl_19']:,.2f} PLN",
                f"- Foreign tax (WHT): {c['podatek_zagraniczny']:,.2f} PLN",
                f"- Tax to pay: {c['podatek_do_zaplaty']:,.2f} PLN",
            ]
        )

        lines.extend(
            [
                "\n## Bottom Line",
                f"- **Total income: {pit38_result['dochod_razem']:,.2f} PLN**",
                f"- **Tax to pay: {pit38_result['podatek_do_zaplaty']:,.2f} PLN**",
            ]
        )

        if pit38_result["warnings"]:
            lines.append("\n## Warnings")
            for warning in pit38_result["warnings"]:
                lines.append(f"- {warning}")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return filepath

    def _add_summary_sheet(self, wb: Workbook, pit38_result: Dict):
        """Add summary sheet to workbook."""
        ws = wb.create_sheet("Summary")

        headers = ["Category", "Amount (PLN)"]
        ws.append(headers)

        rows = [
            ["Securities - Revenue", pit38_result["czesc_C"]["przychod_pln"]],
            ["Securities - Cost", pit38_result["czesc_C"]["koszt_pln"]],
            ["Securities - Income", pit38_result["czesc_C"]["dochod_pln"]],
            ["Securities - Tax @ 19%", pit38_result["czesc_C"]["dochod_pln"] * Decimal("0.19")],
            ["Crypto - Revenue", pit38_result["czesc_E"]["przychod_pln"]],
            ["Crypto - Cost", pit38_result["czesc_E"]["koszt_pln"]],
            ["Crypto - Income", pit38_result["czesc_E"]["dochod_pln"]],
            ["Crypto - Tax @ 19%", pit38_result["czesc_E"]["dochod_pln"] * Decimal("0.19")],
            ["Dividends - Gross", pit38_result["czesc_D"]["przychod_pln"]],
            ["Dividends - Tax to pay", pit38_result["czesc_D"]["podatek_do_zaplaty"]],
            ["TOTAL INCOME", pit38_result["dochod_razem"]],
            ["TOTAL TAX TO PAY", pit38_result["podatek_do_zaplaty"]],
        ]

        for row in rows:
            ws.append(row)

        # Format
        for cell in ws["A"]:
            cell.font = Font(bold=True)
        for i in range(2, len(rows) + 2):
            ws[f"B{i}"].number_format = "#,##0.00"

    def _add_stocks_sheet(self, wb: Workbook, stocks: List[Dict]):
        """Add stocks sheet."""
        ws = wb.create_sheet("Stocks")

        headers = ["Symbol", "Quantity", "Cost Basis (PLN)", "Proceeds (PLN)", "Gain (PLN)"]
        ws.append(headers)

        for stock in stocks:
            ws.append(
                [
                    stock.get("symbol", ""),
                    stock.get("quantity", ""),
                    stock.get("cost_basis_pln", ""),
                    stock.get("proceeds_pln", ""),
                    stock.get("gain_pln", ""),
                ]
            )

        for i in range(2, len(stocks) + 2):
            for col in ["C", "D", "E"]:
                ws[f"{col}{i}"].number_format = "#,##0.00"

    def _add_crypto_sheet(self, wb: Workbook, crypto: List[Dict]):
        """Add crypto sheet."""
        ws = wb.create_sheet("Crypto")

        headers = ["Symbol", "Quantity", "Cost Basis (PLN)", "Proceeds (PLN)", "Gain (PLN)"]
        ws.append(headers)

        for tx in crypto:
            ws.append(
                [
                    tx.get("symbol", ""),
                    tx.get("quantity", ""),
                    tx.get("cost_basis_pln", ""),
                    tx.get("proceeds_pln", ""),
                    tx.get("gain_pln", ""),
                ]
            )

        for i in range(2, len(crypto) + 2):
            for col in ["C", "D", "E"]:
                ws[f"{col}{i}"].number_format = "#,##0.00"

    def _add_dividends_sheet(self, wb: Workbook, dividends: List[Dict]):
        """Add dividends sheet."""
        ws = wb.create_sheet("Dividends")

        headers = [
            "Symbol",
            "Country",
            "Gross (PLN)",
            "WHT Paid (PLN)",
            "Treaty Rate",
            "Tax to Pay (PLN)",
        ]
        ws.append(headers)

        for div in dividends:
            ws.append(
                [
                    div.get("symbol", ""),
                    div.get("country_code", ""),
                    div.get("gross_pln", ""),
                    div.get("wht_paid_pln", ""),
                    f"{div.get('treaty_rate', Decimal(0)) * 100:.1f}%",
                    div.get("tax_to_pay", ""),
                ]
            )

        for i in range(2, len(dividends) + 2):
            for col in ["C", "D", "F"]:
                ws[f"{col}{i}"].number_format = "#,##0.00"

    def _add_nbp_rates_sheet(self, wb: Workbook, nbp_rates: Dict):
        """Add NBP rates sheet."""
        ws = wb.create_sheet("NBP Rates")

        headers = ["Currency", "Date", "Rate"]
        ws.append(headers)

        for key, rate in sorted(nbp_rates.items()):
            currency, date_str = key.split("_")
            ws.append([currency, date_str, rate])

        for i in range(2, len(nbp_rates) + 2):
            ws[f"C{i}"].number_format = "0.0000"
