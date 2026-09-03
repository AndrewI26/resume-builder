"""The API as the desktop app starts it.

A packaged application cannot be run with ``uvicorn main:app`` — there is no
uvicorn on the machine and no source tree to point it at — so this is the entry
point PyInstaller builds into a binary, and everything it needs is decided here
rather than on a command line the shell would have to get right.

The port is the one argument, because the shell picks a free one at launch. Not
a fixed port: another program may already hold whatever we chose, and a resume
tool that refuses to open because of that is indefensible.
"""

import argparse
import sys

import uvicorn

# Imported rather than named as "main:app". A bundler collects what is
# imported, and a module named only inside a string is a module it has no
# reason to include — the packaged binary would start and then fail to find
# its own application.
from main import app


def main() -> int:
    parser = argparse.ArgumentParser(prog="resume-api")
    parser.add_argument("--port", type=int, required=True)
    # loopback only, and not configurable: this API answers one window on this
    # machine, and binding anywhere else would put a person's library on their
    # network
    arguments = parser.parse_args()

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=arguments.port,
        # the access log is noise in the shell's console; failures still print
        access_log=False,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
