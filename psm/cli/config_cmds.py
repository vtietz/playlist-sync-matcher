"""Configuration display commands."""

from __future__ import annotations
import click
import json as _json

from .helpers import cli, _redact_spotify_config


@cli.command(name="config")
@click.option("--section", "-s", help="Only show a specific top-level section (e.g. providers, export, database).")
@click.option("--redact", is_flag=True, help="Redact sensitive values like client_id.")
@click.pass_context
def show_config(ctx: click.Context, section: str | None, redact: bool):
    """Show current configuration settings."""
    cfg = ctx.obj
    data = cfg
    if section:
        section = section.lower()
        if section not in data:
            raise click.UsageError(f"Unknown section '{section}'. Available: {', '.join(sorted(data.keys()))}")
        data = {section: data[section]}
    out = data
    if redact:
        out = _redact_spotify_config(out)
    click.echo(_json.dumps(out, indent=2, sort_keys=True))


__all__ = ["show_config"]
