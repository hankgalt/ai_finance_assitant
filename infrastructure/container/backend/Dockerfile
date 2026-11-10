FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c

ARG UV_VERSION=0.12.5
ARG VCS_REF=unknown

LABEL org.opencontainers.image.source="https://github.com/hankgalt/ai_finance_assitant" \
      org.opencontainers.image.revision="${VCS_REF}"

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
    && python -c "from ai_finance_assistant.knowledge.representations import FastEmbedEncoder; encoder = FastEmbedEncoder(); encoder.embed_dense(['cache warmup']); encoder.embed_sparse(['cache warmup'])" \
    && groupadd --gid 10001 aifa \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin aifa \
    && chown -R 10001:10001 /app /opt/fastembed-cache

ENV HF_HUB_OFFLINE=1

USER 10001:10001
EXPOSE 8080

CMD ["uvicorn", "ai_finance_assistant.api.app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]

