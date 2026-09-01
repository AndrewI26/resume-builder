# The API and the PDF worker run from this one image: the worker needs pdfTeX,
# the API needs the same source tree, and one image is less to build than two.

FROM python:3.13-slim-trixie AS dependencies
COPY --from=ghcr.io/astral-sh/uv:0.9.9 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project


# TinyTeX rather than Debian's texlive-*: the template needs fontawesome5 and
# marvosym, which on Debian drag in texlive-fonts-extra (gigabytes). This is
# the ~200MB base plus the dozen packages the preamble actually loads.
FROM python:3.13-slim-trixie AS texlive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates wget perl xz-utils fontconfig \
 && rm -rf /var/lib/apt/lists/*
RUN wget -qO- https://yihui.org/tinytex/install-bin-unix.sh | sh \
 && mv /root/.TinyTeX /opt/texlive \
 && rm -rf /root/bin
ENV PATH=/opt/texlive/bin/aarch64-linux:/opt/texlive/bin/x86_64-linux:$PATH
RUN tlmgr install \
      tools preprint titlesec marvosym enumitem fancyhdr babel-english \
      fontawesome5 xcolor \
 # nothing here runs tlmgr again, and pdfTeX reads none of this
 && rm -rf /opt/texlive/texmf-dist/doc \
           /opt/texlive/texmf-dist/source \
           /opt/texlive/tlpkg/tlpobj


FROM python:3.13-slim-trixie
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
 && rm -rf /var/lib/apt/lists/* \
 # TeX writes its font cache under $HOME, and a compile runs as this user
 && useradd --create-home --uid 10001 app

COPY --from=texlive /opt/texlive /opt/texlive
COPY --from=dependencies --chown=app:app /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:/opt/texlive/bin/aarch64-linux:/opt/texlive/bin/x86_64-linux:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# The source keeps its place in the repo layout: config.py looks two
# directories up for the .env, and a shallower path would be an IndexError.
WORKDIR /app/apps/api
COPY --chown=app:app . .

USER app
ENV HOME=/home/app

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
