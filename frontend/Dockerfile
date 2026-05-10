# SmartSpend / EXIQO frontend container.
# Two-stage build: node 18 compiles the React app, nginx alpine serves it.
# REACT_APP_API_URL is set to /api so all calls go through the reverse proxy
# defined in the repo-root nginx.conf.

# ── Stage 1: build ─────────────────────────────────────────────────────────
FROM node:18-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --no-audit --no-fund

COPY . .

# Production frontend talks to /api on the same origin — the repo-root
# nginx reverse proxy forwards /api to the backend container.
ENV REACT_APP_API_URL=/api

RUN npm run build

# ── Stage 2: serve ─────────────────────────────────────────────────────────
FROM nginx:alpine

COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx-frontend.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
