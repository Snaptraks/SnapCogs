from pathlib import Path


def read_sql_query(sql_path: Path) -> str:
    """Read SQL file and return the query as string."""

    return Path(sql_path).read_text()
