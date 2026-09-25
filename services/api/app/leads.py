"""Lead tools. Usage: python -m app.leads export [--status new] > leads.csv"""

import argparse
import asyncio
import io
import sys

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models.enums import LeadStatus
from app.services.leads import export_csv


async def _export(status: LeadStatus | None) -> None:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(newline="")  # the csv module writes its own line endings
    engine = create_async_engine(get_settings().database_url)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    async with sessionmaker() as db:
        n = await export_csv(db, sys.stdout, status)
    await engine.dispose()
    print(f"{n} leads exported", file=sys.stderr)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.leads")
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="write leads as CSV to stdout")
    export.add_argument("--status", choices=[s.value for s in LeadStatus])
    args = parser.parse_args(argv)
    asyncio.run(_export(LeadStatus(args.status) if args.status else None))


if __name__ == "__main__":
    main()
