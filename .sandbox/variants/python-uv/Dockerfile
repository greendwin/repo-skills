# check=skip=InvalidDefaultArgInFrom
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG PYTHON_VERSION="3.10 3.11 3.12"

RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
 && uv python install ${PYTHON_VERSION}

RUN uv tool install tox \
 && uv tool install pytest \
 && uv tool install mypy \
 && uv tool install black \
 && uv tool install isort \
 && uv tool install flake8 \
 && uv tool install mcp-tasker

USER root
RUN npm install -g pyright && rm -rf /var/lib/apt/lists/*
USER ${USERNAME}

# Pre-create volume mount points so named-volume init inherits user ownership
# instead of being created as root by the Docker daemon.
RUN mkdir -p /work/.venv /work/.tox

ENV PATH="/work/.venv/bin:${PATH}"
