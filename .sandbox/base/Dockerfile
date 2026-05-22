FROM ubuntu:26.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates git zsh neovim tmux ncurses-term \
    && rm -rf /var/lib/apt/lists/*

ARG UID=1000
ARG GID=1000
ARG USERNAME=agent

# Ubuntu 26.04 ships a pre-created `ubuntu` user at 1000:1000. Remove it so the
# host's UID/GID can be reused without collision.
RUN (userdel -r ubuntu && groupdel ubuntu) 2>/dev/null || true \
    && groupadd -g ${GID} ${USERNAME} \
    && useradd -m -u ${UID} -g ${GID} -s /bin/zsh ${USERNAME}

RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

USER ${USERNAME}
ENV USERNAME=${USERNAME}
ENV PATH="/home/${USERNAME}/.local/bin:${PATH}"

RUN curl -fsSL https://claude.ai/install.sh | bash

RUN git config --global user.name "Claude Agent" \
    && git config --global user.email "agent@claude.ai"

WORKDIR /work

CMD ["tmux", "new-session", "-A", "-s", "main"]
