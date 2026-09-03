# PyInstaller build of the API, for the desktop app to run as a sidecar.
#
#   uv run pyinstaller resume-api.spec --noconfirm
#
# Most of this is the two kinds of thing a bundler cannot work out by reading
# imports: files that are read at runtime rather than imported, and modules that
# are imported by name rather than by an import statement.

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

HERE = Path(SPECPATH)

# Alembic finds migrations by walking a directory and loading each file by
# path, so nothing imports them and nothing would otherwise be collected. The
# .ini goes with them because services/local_bootstrap.py reads it to decide
# where the migrations are.
datas = [
    (str(HERE / "alembic"), "alembic"),
    (str(HERE / "alembic.ini"), "."),
]

hiddenimports = [
    # SQLAlchemy loads a dialect by name from a registry, so nothing imports
    # this and the desktop build would otherwise have no way to open its own
    # database.
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.dialects.sqlite.pysqlite",
    # uvicorn's implementation classes are likewise named as strings
    *collect_submodules("uvicorn"),
    # main:app is loaded by name, so the routers behind it are reached only
    # through that string
    *collect_submodules("routers"),
    *collect_submodules("services"),
    *collect_submodules("models"),
    *collect_submodules("schemas"),
    *collect_submodules("deps"),
]

analysis = Analysis(
    ["desktop_main.py"],
    pathex=[str(HERE)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=[
        # psycopg is NOT excluded. A desktop install opens a SQLite file and
        # never builds a Postgres engine, but routers/resume.py takes the
        # queue's notifier as a dependency and so imports deps.notify — and
        # that imports psycopg — whatever the mode. Leaving it out stops the
        # binary before it serves anything. The module-scope import is the
        # thing to fix if the driver is worth the megabytes.
        "psycopg2",
        # test and lint tooling that the dependency tree drags along
        "pytest",
        "mypy",
        "ruff",
        # The queue is Postgres now and a desktop install has neither. Nothing
        # imports these any more, so excluding them only makes sure they cannot
        # come back by accident.
        "redis",
        "arq",
    ],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="resume-api",
    console=True,
    # the shell reads the child's output to report why a start failed
    debug=False,
    strip=False,
    upx=False,
)

COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="resume-api",
)
