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
        # Postgres belongs to the hosted deployment. A desktop install opens a
        # SQLite file and never builds a Postgres engine, so this is tens of
        # megabytes of driver that would never be called.
        "psycopg",
        "psycopg2",
        "psycopg_binary",
        # test and lint tooling that the dependency tree drags along
        "pytest",
        "mypy",
        "ruff",
    ],
    # redis and arq are deliberately NOT excluded. Nothing local uses a queue,
    # but routers/resume.py imports deps.redis at module scope whatever the
    # mode, so leaving them out stops the binary before it serves anything.
    # They are pure Python and small; the import is the thing to fix, and it is
    # being removed along with Redis itself.
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
