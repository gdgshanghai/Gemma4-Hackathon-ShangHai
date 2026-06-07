# ---- Build stage ----
FROM node:22-alpine AS builder
WORKDIR /build

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

# VITE_API_BASE_URL is baked in at build time.
# Pass it via docker-compose build args (e.g. --build-arg VITE_API_BASE_URL=https://api.slide.shuaixr.dev)
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# ---- Production stage ----
FROM nginx:stable-alpine

COPY --from=builder /build/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
