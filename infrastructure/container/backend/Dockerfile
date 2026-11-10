FROM python:3.12.16-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS builder

ARG UV_VERSION=0.13.4

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    FASTEMBED_CACHE_PATH=/opt/fastembed-cache \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

RUN python -m pip install --no-cache-dir "uv==${UV_VERSION}"

COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/src ./src
RUN uv sync --frozen --no-dev --no-editable \
    && python -c "from ai_finance_assistant.knowledge.representations import FastEmbedEncoder; encoder = FastEmbedEncoder(); encoder.embed_dense(['cache warmup']); encoder.embed_sparse(['cache warmup'])"

FROM python:3.12.16-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS runtime

ARG VCS_REF=unknown

LABEL org.opencontainers.image.source="https://github.com/hankgalt/ai_finance_assitant" \
      org.opencontainers.image.revision="${VCS_REF}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/opt/fastembed-cache \
    PATH="/app/.venv/bin:${PATH}" \
    HF_HUB_OFFLINE=1

WORKDIR /app

RUN groupadd --gid 10001 aifa \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin aifa

COPY --from=builder --chown=10001:10001 /app /app
COPY --from=builder --chown=10001:10001 /opt/fastembed-cache /opt/fastembed-cache

USER 10001:10001
EXPOSE 8080

CMD ["uvicorn", "ai_finance_assistant.api.app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]

