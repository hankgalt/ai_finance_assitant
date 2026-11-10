FROM node:24.11.0-alpine3.22@sha256:f36fed0b2129a8492535e2853c64fbdbd2d29dc1219ee3217023ca48aebd3787 AS build

ARG VCS_REF=unknown
WORKDIR /workspace/frontend

RUN corepack enable && corepack prepare pnpm@11.25.0 --activate
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
COPY contracts/ /workspace/contracts/
RUN pnpm build

FROM nginxinc/nginx-unprivileged:1.29.3-alpine3.22-slim@sha256:df9d99123d80117ea348470175f20abe85befd1ed361ea6207eaf49ab5a30ed9

ARG VCS_REF=unknown
LABEL org.opencontainers.image.source="https://github.com/hankgalt/ai_finance_assitant" \
      org.opencontainers.image.revision="${VCS_REF}"

COPY infrastructure/container/frontend/nginx.conf /etc/nginx/nginx.conf
COPY --from=build /workspace/frontend/dist /usr/share/nginx/html/finance_assistant

USER 101:101
EXPOSE 8080

