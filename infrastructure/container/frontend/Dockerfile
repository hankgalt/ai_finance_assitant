FROM node:24.22.2-alpine3.24@sha256:a34ab6d7f6f4813f4d0c5469d74685604b962fbdbf5793a7bc7b4998ecb867c8 AS build

ARG VCS_REF=unknown
WORKDIR /workspace/frontend

RUN corepack enable && corepack prepare pnpm@11.25.0 --activate
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
COPY contracts/ /workspace/contracts/
RUN pnpm build

FROM nginx/nginx-unprivileged:1.30.6-alpine3.24-slim@sha256:e333a5b95605942b5e495645ee54fab02b112081de6dbe45d2ead3ef38e03e31 AS runtime

ARG VCS_REF=unknown
LABEL org.opencontainers.image.source="https://github.com/hankgalt/ai_finance_assitant" \
      org.opencontainers.image.revision="${VCS_REF}"

COPY infrastructure/container/frontend/nginx.conf /etc/nginx/nginx.conf
COPY --from=build /workspace/frontend/dist /usr/share/nginx/html/finance_assistant

USER 101:101
EXPOSE 8080

