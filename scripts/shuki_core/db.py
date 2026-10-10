"""Per-feature SQLite databases: location, connection settings and schema versions.

Each feature owns one database at ``<data_dir>/<feature>/<feature>.db`` and an
ordered ``MIGRATIONS`` list. ``PRAGMA user_version`` records how many steps are
applied; a database newer than the running code is refused, never downgraded.

Location follows the guarded storage migration: an activation marker always
wins and must point at an existing database. Without one, an install that still
has the feature's legacy files keeps using them (``None``), and a fresh install
uses the database directly. Resolving never creates or converts data.
"""
from contextlib import contextmanager
from pathlib import Path
import sqlite3

import shuki_paths


class SchemaTooNew(RuntimeError):
    pass


def feature_db(key, legacy_paths=()):
    """Return the database path to use, or None while legacy files stay authoritative."""
    target = shuki_paths.runtime_target(key)
    entry = shuki_paths.storage_activation()["stores"].get(key)
    if entry is not None:
        if entry["kind"] != "sqlite" or not target.is_file():
            raise FileNotFoundError("activated feature database is missing: " + key)
        return target
    if any(Path(path).exists() for path in legacy_paths):
        return None
    return target


def connect(path, migrations, readonly=False):
    """Open a feature database in autocommit mode and bring its schema up to date.

    Writes use ``write(conn)`` so each logical change is one transaction.
    A read-only connection checks the version but never migrates or creates.
    """
    path = Path(path)
    if readonly:
        conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=10,
                               isolation_level=None)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        if readonly:
            _check_version(conn, migrations)
        else:
            conn.execute("PRAGMA journal_mode=WAL")
            migrate(conn, migrations)
    except BaseException:
        conn.close()
        raise
    return conn


def _check_version(conn, migrations):
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > len(migrations):
        raise SchemaTooNew(f"database schema {version} is newer than this code ({len(migrations)})")
    return version


def migrate(conn, migrations):
    """Apply missing steps in one transaction. Each step is a list of SQL statements."""
    if _check_version(conn, migrations) == len(migrations):
        return
    with write(conn):
        # Re-read under the write lock: another process may have migrated meanwhile.
        version = _check_version(conn, migrations)
        for step in migrations[version:]:
            for statement in step:
                conn.execute(statement)
        conn.execute(f"PRAGMA user_version={len(migrations)}")


@contextmanager
def write(conn):
    """One immediate transaction; rolled back on any error."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
