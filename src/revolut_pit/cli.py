"""Command-line interface for revolut-pit."""

from decimal import Decimal
from pathlib import Path

import click

from . import __version__
from .nbp import NBPClient
from .pipeline import Pipeline
from .reports import ReportGenerator


@click.group()
def cli():
    """revolut-pit: Calculate Polish PIT-38 from Revolut data."""
    pass


@cli.command()
@click.option("--year", type=int, required=True, help="Tax year (e.g., 2025)")
@click.option(
    "--data-dir",
    type=click.Path(exists=True, file_okay=False),
    default="./data",
    show_default=True,
    help="Directory containing CSV files for the year",
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False),
    default="./output",
    show_default=True,
    help="Directory for output files",
)
@click.option(
    "--prior-loss-c",
    type=float,
    default=0.0,
    show_default=True,
    help="Loss carry-forward from prior years for Part C (securities, PLN). "
    "Per art. 9 ust. 6 PIT, securities losses can only offset securities gains.",
)
@click.option(
    "--prior-loss-e",
    type=float,
    default=0.0,
    show_default=True,
    help="Loss carry-forward from prior years for Part E (crypto, PLN). "
    "Per art. 22 ust. 14 PIT, crypto losses can only offset crypto gains.",
)
@click.option("--quiet", is_flag=True, help="Suppress progress logs")
def calc(
    year: int,
    data_dir: str,
    output_dir: str,
    prior_loss_c: float,
    prior_loss_e: float,
    quiet: bool,
):
    """Calculate PIT-38 from Revolut exports."""
    click.echo(f"revolut-pit v{__version__}")

    data_path = Path(data_dir)
    # If data_dir contains subfolders by year, descend
    if (data_path / str(year)).is_dir():
        data_path = data_path / str(year)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    pipeline = Pipeline(
        year=year,
        data_dir=data_path,
        nbp_client=NBPClient(),
        verbose=not quiet,
    )
    result = pipeline.run(
        prior_year_loss_c=Decimal(str(prior_loss_c)),
        prior_year_loss_e=Decimal(str(prior_loss_e)),
    )

    detail = result.pop("_detail", {})

    # Reports
    reporter = ReportGenerator(output_dir=output_path)
    xlsx_path = reporter.generate_excel(
        pit38_result=result,
        stocks=detail.get("stocks", []),
        crypto=detail.get("crypto", []),
        dividends=detail.get("dividends", []),
        nbp_rates_used=detail.get("nbp_rates_used", {}),
        filename=f"pit38_{year}.xlsx",
    )
    md_path = reporter.generate_markdown(
        pit38_result=result,
        stocks=detail.get("stocks", []),
        crypto=detail.get("crypto", []),
        dividends=detail.get("dividends", []),
        filename=f"pit38_{year}.md",
    )

    # Print summary
    click.echo("\n" + "=" * 60)
    click.echo(f"PIT-38 SUMMARY — rok {year}")
    click.echo("=" * 60)
    c = result["czesc_C"]
    click.echo(
        f"Część C (papiery wartościowe):  "
        f"przychód {c['przychod_pln']:,.2f}  "
        f"koszt {c['koszt_pln']:,.2f}  "
        f"dochód {c['dochod_pln']:,.2f} PLN"
    )
    e = result["czesc_E"]
    click.echo(
        f"Część E (kryptowaluty):         "
        f"przychód {e['przychod_pln']:,.2f}  "
        f"koszt {e['koszt_pln']:,.2f}  "
        f"dochód {e['dochod_pln']:,.2f} PLN"
    )
    d = result["czesc_D"]
    click.echo(
        f"Część D (dywidendy):            "
        f"brutto {d['przychod_pln']:,.2f}  "
        f"WHT {d['podatek_zagraniczny']:,.2f}  "
        f"do zapłaty {d['podatek_do_zaplaty']:,.2f} PLN"
    )
    click.echo("-" * 60)
    click.echo(f"Dochód razem:        {result['dochod_razem']:,.2f} PLN")
    click.echo(
        f"Podatek do zapłaty:  {result['podatek_do_zaplaty']:,.2f} PLN"
    )

    if result.get("warnings"):
        click.echo("\nWarnings:")
        for w in result["warnings"]:
            click.echo(f"  • {w}")

    click.echo(f"\n✓ Excel:    {xlsx_path}")
    click.echo(f"✓ Markdown: {md_path}")


@cli.command()
def cache_clear():
    """Clear NBP rate cache."""
    nbp = NBPClient()
    nbp.clear_cache()
    click.echo("NBP cache cleared.")


@cli.command()
def version():
    """Show version."""
    click.echo(f"revolut-pit {__version__}")


if __name__ == "__main__":
    cli()
