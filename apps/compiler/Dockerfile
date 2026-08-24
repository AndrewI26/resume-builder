# Build the service.
FROM golang:1.23-alpine AS build

WORKDIR /src
COPY go.mod ./
RUN go mod download

COPY *.go ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/compiler .

# Run it next to a TeX engine.
#
# It has to be pdfTeX specifically. The template calls \pdfgentounicode to make
# the output machine-readable for applicant tracking systems, and that is a
# pdfTeX primitive — XeTeX-based engines like Tectonic reject it outright.
# Tectonic would have made for a much smaller image; this is the price of a
# resume that parses.
FROM debian:bookworm-slim AS runtime

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

COPY --from=build /out/compiler /usr/local/bin/compiler

# Prove at build time that the engine can actually compile the template's
# preamble. A missing package should fail the build, not the first request.
COPY warmup.tex /tmp/warmup.tex
RUN cd /tmp \
    && pdflatex -interaction=nonstopmode -halt-on-error -no-shell-escape warmup.tex \
    && rm -f /tmp/warmup.*

# Compiling a document someone else wrote is the whole job, so it does not get
# to run as root.
RUN useradd --system --uid 10001 --no-create-home compiler
USER compiler

EXPOSE 8100

# The binary probes itself: this image has no curl, and its /bin/sh is dash,
# which has no /dev/tcp.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD ["/usr/local/bin/compiler", "-healthcheck"]

ENTRYPOINT ["/usr/local/bin/compiler"]
