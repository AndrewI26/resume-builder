# The sandbox each resume is typeset in.
#
# One container per compile, started by a worker and gone a second later. The
# engine is the untrusted part of this application — a TeX document is a
# program, and this one is assembled from a user's own rows — so it runs here
# with no network, a read-only filesystem, no capabilities and no way to reach
# the API's environment, rather than as a child process of the API itself.
#
# It has to be pdfTeX specifically. The template calls \pdfgentounicode to make
# the output machine-readable for applicant tracking systems, and that is a
# pdfTeX primitive — XeTeX-based engines like Tectonic reject it outright.
# Tectonic would have made for a much smaller image; this is the price of a
# resume that parses.
FROM debian:bookworm-slim

# Skip the documentation and translations that come with TeX Live. They are the
# bulk of the install and nothing here ever reads them.
RUN printf '%s\n' \
      'path-exclude /usr/share/doc/*' \
      'path-exclude /usr/share/man/*' \
      'path-exclude /usr/share/locale/*' \
      'path-exclude /usr/share/texmf/doc/*' \
      'path-exclude /usr/share/texlive/texmf-dist/doc/*' \
      > /etc/dpkg/dpkg.cfg.d/01-exclude-docs

# texlive-fonts-extra carries fontawesome5 and marvosym; latex-extra carries
# titlesec and enumitem. Everything else the template needs is in the base and
# recommended sets.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        texlive-latex-base \
        texlive-latex-recommended \
        texlive-latex-extra \
        texlive-fonts-recommended \
        texlive-fonts-extra \
    && rm -rf /var/lib/apt/lists/*

# Prove at build time that the engine can actually compile the template's
# preamble. A missing package should fail the build, not the first export —
# there is no network at runtime to fetch one from.
COPY warmup.tex /tmp/warmup.tex
RUN cd /tmp \
    && pdflatex -interaction=nonstopmode -halt-on-error -no-shell-escape warmup.tex \
    && rm -f /tmp/warmup.*

COPY compile.sh /usr/local/bin/compile
RUN chmod +x /usr/local/bin/compile

# Paranoid mode: the document cannot read a file outside its own directory and
# the TeX tree, nor write outside its own directory. This is what stops
# \input{/etc/passwd} from reaching the PDF, and it holds even though the
# container has little else worth reading.
ENV openin_any=p \
    openout_any=p \
    # pins the timestamp TeX bakes in, so identical input gives an identical file
    SOURCE_DATE_EPOCH=0 \
    FORCE_SOURCE_DATE=1 \
    # TeX wants somewhere writable for generated font files; /tmp is the tmpfs
    TEXMFVAR=/tmp \
    HOME=/tmp

# Compiling a document someone else wrote is the whole job, so it does not get
# to run as root.
RUN useradd --system --uid 10001 --no-create-home compiler
USER 10001

ENTRYPOINT ["/usr/local/bin/compile"]
