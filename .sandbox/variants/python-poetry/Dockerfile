# check=skip=InvalidDefaultArgInFrom
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG PYTHON_VERSION=3.12

# Use uv to manage the Python interpreter even for the poetry variant —
# it's the cleanest cross-version story and poetry will happily use it.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
 && uv python install ${PYTHON_VERSION}

RUN uv tool install poetry \
 && uv tool install pytest \
 && uv tool install mypy \
 && uv tool install black \
 && uv tool install isort \
 && uv tool install flake8

USER root
RUN npm install -g pyright && rm -rf /var/lib/apt/lists/*
USER ${USERNAME}

# Pre-create volume mount points so named-volume init inherits user ownership
# instead of being created as root by the Docker daemon.
RUN mkdir -p /work/.venv /work/.tox

# Keep poetry's venv inside the project dir so the .venv volume-shadow works.
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
ENV PATH="/work/.venv/bin:${PATH}"
