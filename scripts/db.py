from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "scripts" / "sql"


@dataclass(frozen=True)
class DbUrl:
    scheme: str
    host: str
    port: int
    user: str
    password: str
    database: str

    @property
    def safe_display(self) -> str:
        pw = "****" if self.password else ""
        user = self.user or ""
        auth = f"{user}:{pw}@" if (user or pw) else ""
        return f"{self.scheme}://{auth}{self.host}:{self.port}/{self.database}"


def _parse_database_url(raw: str) -> DbUrl:
    if not raw:
        raise SystemExit("DATABASE_URL is not set.")

    u = urlparse(raw)
    if u.scheme not in {"postgres", "postgresql"}:
        raise SystemExit(f"Unsupported DATABASE_URL scheme: {u.scheme!r}. Expected postgres/postgresql.")
    if not u.hostname:
        raise SystemExit("DATABASE_URL missing hostname.")
    if not u.path or u.path == "/":
        raise SystemExit("DATABASE_URL missing database name in path.")

    return DbUrl(
        scheme=u.scheme,
        host=u.hostname,
        port=int(u.port or 5432),
        user=unquote(u.username or ""),
        password=unquote(u.password or ""),
        database=unquote(u.path.lstrip("/")),
    )


def _which(cmd: str) -> str | None:
    return shutil.which(cmd)


def _run(cmd: list[str], *, env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, env=env, check=check)


def _compose_cmd() -> list[str]:
    """
    Prefer `docker compose` but fall back to `docker-compose`.
    """
    if _which("docker") is None:
        raise SystemExit("docker is not installed or not on PATH.")
    try:
        p = subprocess.run(["docker", "compose", "version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if p.returncode == 0:
            return ["docker", "compose"]
    except Exception:
        pass
    if _which("docker-compose") is not None:
        return ["docker-compose"]
    raise SystemExit("Could not find `docker compose` or `docker-compose`.")


def _psql_base(db: DbUrl, *, prefer_local: bool) -> list[str]:
    """
    Returns base command for psql, either local binary or via docker compose exec.
    """
    if prefer_local and _which("psql"):
        return ["psql"]
    compose = _compose_cmd()
    return [*compose, "exec", "-T", "postgres", "psql"]


def _pg_dump_base(db: DbUrl, *, prefer_local: bool) -> list[str]:
    if prefer_local and _which("pg_dump"):
        return ["pg_dump"]
    compose = _compose_cmd()
    return [*compose, "exec", "-T", "postgres", "pg_dump"]


def _pg_restore_stream_via_psql(db: DbUrl, dump_path: Path, *, prefer_local: bool) -> None:
    """
    Use psql to restore a SQL dump file.
    """
    env = os.environ.copy()
    if db.password:
        env["PGPASSWORD"] = db.password

    base = _psql_base(db, prefer_local=prefer_local)
    cmd = [
        *base,
        "-h",
        db.host,
        "-p",
        str(db.port),
        "-U",
        db.user,
        "-d",
        db.database,
        "-v",
        "ON_ERROR_STOP=1",
        "-f",
        str(dump_path),
    ]
    _run(cmd, env=env, check=True)


def _psql_exec_sql(db: DbUrl, sql: str, *, prefer_local: bool) -> None:
    env = os.environ.copy()
    if db.password:
        env["PGPASSWORD"] = db.password

    base = _psql_base(db, prefer_local=prefer_local)
    cmd = [
        *base,
        "-h",
        db.host,
        "-p",
        str(db.port),
        "-U",
        db.user,
        "-d",
        db.database,
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        sql,
    ]
    _run(cmd, env=env, check=True)


def _psql_exec_file(db: DbUrl, file_path: Path, *, prefer_local: bool) -> None:
    if not file_path.exists():
        raise SystemExit(f"SQL file not found: {file_path}")

    env = os.environ.copy()
    if db.password:
        env["PGPASSWORD"] = db.password

    base = _psql_base(db, prefer_local=prefer_local)
    cmd = [
        *base,
        "-h",
        db.host,
        "-p",
        str(db.port),
        "-U",
        db.user,
        "-d",
        db.database,
        "-v",
        "ON_ERROR_STOP=1",
        "-f",
        str(file_path),
    ]
    _run(cmd, env=env, check=True)


def cmd_info(args: argparse.Namespace) -> int:
    db = _parse_database_url(os.environ.get("DATABASE_URL", ""))
    print(db.safe_display)
    print(f"prefer_local={args.prefer_local}")
    print(f"schema_sql={SQL_DIR / 'schema.sql'}")
    print(f"seed_sql={SQL_DIR / 'seed.sql'}")
    return 0


def cmd_wait(args: argparse.Namespace) -> int:
    db = _parse_database_url(os.environ.get("DATABASE_URL", ""))
    deadline = time.time() + args.timeout_s
    last_err: Exception | None = None

    while time.time() < deadline:
        try:
            _psql_exec_sql(db, "SELECT 1;", prefer_local=args.prefer_local)
            print("OK")
            return 0
        except Exception as e:
            last_err = e
            time.sleep(args.interval_s)

    print("Timed out waiting for database connection.", file=sys.stderr)
    if last_err:
        print(str(last_err), file=sys.stderr)
    return 2


def cmd_schema(args: argparse.Namespace) -> int:
    db = _parse_database_url(os.environ.get("DATABASE_URL", ""))
    _psql_exec_file(db, SQL_DIR / "schema.sql", prefer_local=args.prefer_local)
    return 0


def cmd_seed(args: argparse.Namespace) -> int:
    db = _parse_database_url(os.environ.get("DATABASE_URL", ""))
    _psql_exec_file(db, SQL_DIR / "seed.sql", prefer_local=args.prefer_local)
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    db = _parse_database_url(os.environ.get("DATABASE_URL", ""))
    # Drops and recreates public schema. Destructive.
    _psql_exec_sql(db, "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;", prefer_local=args.prefer_local)
    if args.with_schema:
        cmd_schema(args)
    if args.with_seed:
        cmd_seed(args)
    return 0


def cmd_dump(args: argparse.Namespace) -> int:
    db = _parse_database_url(os.environ.get("DATABASE_URL", ""))
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    if db.password:
        env["PGPASSWORD"] = db.password

    base = _pg_dump_base(db, prefer_local=args.prefer_local)
    cmd = [
        *base,
        "-h",
        db.host,
        "-p",
        str(db.port),
        "-U",
        db.user,
        "-d",
        db.database,
        "--no-owner",
        "--no-privileges",
        "--format=p",
        "--file",
        str(out),
    ]
    _run(cmd, env=env, check=True)
    print(str(out))
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    db = _parse_database_url(os.environ.get("DATABASE_URL", ""))
    dump_path = Path(args.path).resolve()
    if not dump_path.exists():
        raise SystemExit(f"Dump file not found: {dump_path}")
    _pg_restore_stream_via_psql(db, dump_path, prefer_local=args.prefer_local)
    return 0


def cmd_psql(args: argparse.Namespace) -> int:
    """
    Opens interactive psql if local exists, otherwise runs it inside container.
    """
    db = _parse_database_url(os.environ.get("DATABASE_URL", ""))
    env = os.environ.copy()
    if db.password:
        env["PGPASSWORD"] = db.password

    base = _psql_base(db, prefer_local=args.prefer_local)
    cmd = [
        *base,
        "-h",
        db.host,
        "-p",
        str(db.port),
        "-U",
        db.user,
        "-d",
        db.database,
    ]
    # If we go through docker compose exec, this is still interactive in most terminals.
    p = subprocess.run(cmd, env=env)
    return int(p.returncode or 0)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="db",
        description="Database utility for TARA (PostgreSQL via DATABASE_URL).",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument(
        "--prefer-local",
        action="store_true",
        help="Prefer local psql/pg_dump if available (default: use docker compose exec).",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("info", help="Show parsed DATABASE_URL and SQL paths.")
    sp.set_defaults(func=cmd_info)

    sp = sub.add_parser("wait", help="Wait until DB is reachable (SELECT 1).")
    sp.add_argument("--timeout-s", type=float, default=60.0)
    sp.add_argument("--interval-s", type=float, default=2.0)
    sp.set_defaults(func=cmd_wait)

    sp = sub.add_parser("schema", help="Apply schema SQL (idempotent).")
    sp.set_defaults(func=cmd_schema)

    sp = sub.add_parser("seed", help="Seed sample data (safe to re-run).")
    sp.set_defaults(func=cmd_seed)

    sp = sub.add_parser("reset", help="Drop+recreate public schema (DESTRUCTIVE).")
    sp.add_argument("--with-schema", action="store_true", help="Re-apply schema.sql after reset.")
    sp.add_argument("--with-seed", action="store_true", help="Re-apply seed.sql after reset.")
    sp.set_defaults(func=cmd_reset)

    sp = sub.add_parser("dump", help="Create a SQL dump to a file.")
    sp.add_argument("--out", default=str(ROOT / "backups" / "tara.sql"))
    sp.set_defaults(func=cmd_dump)

    sp = sub.add_parser("restore", help="Restore from a SQL dump file.")
    sp.add_argument("path", help="Path to .sql dump")
    sp.set_defaults(func=cmd_restore)

    sp = sub.add_parser("psql", help="Open psql session.")
    sp.set_defaults(func=cmd_psql)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

