# The UI: the built shop app served by nginx. API calls (/v1, /demo, /payment, /static) are proxied to the
# backend service, so the browser sees ONE origin (needed for the fingerprint login and the voice socket).
# Build from mvp/:  docker build -f deployment/ui.Dockerfile -t talktobuy-ui .
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
COPY packages/assistant-widget/package.json packages/assistant-widget/package.json
COPY apps/shop/package.json apps/shop/package.json
RUN npm ci
COPY packages/assistant-widget packages/assistant-widget
COPY apps/shop apps/shop
RUN npm run build -w apps/shop

FROM nginx:1.27-alpine
COPY --from=build /app/apps/shop/dist /usr/share/nginx/html
# nginx fills ${BACKEND_HOST} from the environment when the container starts.
COPY deployment/nginx-ui.conf.template /etc/nginx/templates/default.conf.template
ENV BACKEND_HOST=localhost CANONICAL_HOST=localhost
EXPOSE 8080
