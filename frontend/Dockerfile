# ---------------------------------------
# Development stage
# ---------------------------------------
FROM --platform=linux/amd64 node:18.7.0-alpine AS development
ENV DOCKER_BUILDKIT 0
ENV COMPOSE_DOCKER_CLI_BUILD 0
WORKDIR /frontend
COPY package*.json yarn.lock tsconfig.json ./
RUN yarn config set network-timeout 300000 && \
    yarn install --frozen-lockfile
# Bundle app source
COPY . ./
# ---------------------------------------
# Build stage
# ---------------------------------------
FROM development AS build
RUN yarn run build
# ---------------------------------------
# Production stage
# ---------------------------------------
FROM nginx:1.23-alpine AS production
#copy static files to nginx
RUN rm -rf /usr/share/nginx/html/*
COPY --from=build frontend/src/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

ENTRYPOINT ["nginx", "-g", "daemon off;"]