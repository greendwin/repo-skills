# check=skip=InvalidDefaultArgInFrom
ARG BASE_IMAGE

# The shared base image (Ubuntu 26.04) does not ship PHP 8.4, and the
# ondrej/php PPA builds for noble (24.04) cannot be mixed with resolute's
# libxml2/libzip. For the PHP variant we therefore bypass ${BASE_IMAGE} and
# build directly on ubuntu:24.04, replicating the base setup locally.
FROM ubuntu:24.04

ARG PHP_VERSION=8.4
ARG UID=1000
ARG GID=1000
ARG USERNAME=agent

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates git zsh neovim tmux ncurses-term gnupg \
    && rm -rf /var/lib/apt/lists/*

# Ubuntu 24.04 also ships a pre-created `ubuntu` user at 1000:1000. Remove it
# so the host UID/GID can be reused without collision.
RUN (userdel -r ubuntu && groupdel ubuntu) 2>/dev/null || true \
    && groupadd -g ${GID} ${USERNAME} \
    && useradd -m -u ${UID} -g ${GID} -s /bin/zsh ${USERNAME}

RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# PHP from ondrej/php PPA (noble). Fetch the signing key over HTTPS to avoid
# relying on dirmngr/keyserver inside the build sandbox.
RUN set -eux; \
    install -d -m 0755 /etc/apt/keyrings; \
    curl -fsSL "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x71DAEAAB4AD4CAB6" \
        | gpg --dearmor -o /etc/apt/keyrings/ondrej-php.gpg; \
    echo "deb [signed-by=/etc/apt/keyrings/ondrej-php.gpg] https://ppa.launchpadcontent.net/ondrej/php/ubuntu noble main" \
        > /etc/apt/sources.list.d/ondrej-php.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        php${PHP_VERSION}-cli \
        php${PHP_VERSION}-xml \
        php${PHP_VERSION}-mbstring \
        php${PHP_VERSION}-curl \
        php${PHP_VERSION}-zip \
        php${PHP_VERSION}-intl \
        php${PHP_VERSION}-sqlite3 \
        php${PHP_VERSION}-gd \
        unzip; \
    rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://getcomposer.org/installer | php -- \
        --install-dir=/usr/local/bin --filename=composer

RUN install -d -o ${UID} -g ${GID} /work

USER ${USERNAME}

ENV USERNAME=${USERNAME}
ENV PATH="/home/${USERNAME}/.local/bin:${PATH}"

RUN curl -fsSL https://claude.ai/install.sh | bash

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

RUN git config --global user.name "Claude Agent" \
    && git config --global user.email "agent@claude.ai"

# Pre-create volume mount points so named-volume init inherits user ownership
# instead of being created as root by the Docker daemon.
RUN mkdir -p /work/vendor

WORKDIR /work

CMD ["tmux", "new-session", "-A", "-s", "main"]
