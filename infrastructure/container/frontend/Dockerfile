FROM node:24.22.3-alpine3.24@sha256:116b800c3754b440ee0aa3ed2f20f5bf3d99a554bfd9adeea09ea8017f6e85f5 AS build

ARG VCS_REF=unknown
WORKDIR /workspace/frontend

RUN corepack enable && corepack prepare pnpm@11.25.0 --activate
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
COPY contracts/ /workspace/contracts/
RUN pnpm build

FROM nginx/nginx-unprivileged:1.30.7-alpine3.24-slim@sha256:8432c57ac86f178741af2b89948bd9087cb9df1c415bc1ab4d23735c4f0e3e61 AS runtime

ARG VCS_REF=unknown
LABEL org.opencontainers.image.source="https://github.com/hankgalt/ai_finance_assitant" \
      org.opencontainers.image.revision="${VCS_REF}"

COPY infrastructure/container/frontend/nginx.conf /etc/nginx/nginx.conf
COPY --from=build /workspace/frontend/dist /usr/share/nginx/html/finance_assistant

USER 101:101
EXPOSE 8080

