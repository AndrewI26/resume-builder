#!/bin/sh
# Typeset a LaTeX document read from stdin and write the PDF to stdout.
#
# stdin and stdout are the entire interface: nothing is mounted into this
# container and it has no network, so the document arrives on the pipe and
# leaves on it. Diagnostics go to stderr, which is where the caller reads the
# engine's log from when a compile fails.
#
# Exit 3 means "the document is at fault" and nothing else does. Docker's own
# failures — no such image, daemon unreachable — come back as 1 or 125, so the
# caller can tell a resume it should reject from an engine it could not run,
# which is the difference between answering 422 and 503.
set -eu

REJECTED=3

# The only writable place in the container: the root filesystem is read-only
# and this is a tmpfs that dies with the run.
cd /tmp
cat > main.tex

# stdout is the PDF, so nothing else may be written to it. pdfTeX is chatty on
# success, and its noise would corrupt the file.
if pdflatex \
    -interaction=nonstopmode \
    -halt-on-error \
    -no-shell-escape \
    -output-directory=. \
    main.tex >/dev/null 2>compile.err; then

    # a zero exit with no PDF means the engine gave up quietly
    [ -f main.pdf ] || { cat main.log >&2 2>/dev/null; exit "$REJECTED"; }
    cat main.pdf
    exit 0
fi

# main.log is where pdfTeX explains itself; stderr almost never says anything
cat compile.err >&2 2>/dev/null || true
cat main.log >&2 2>/dev/null || true
exit "$REJECTED"
