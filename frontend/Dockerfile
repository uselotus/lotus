# ---------------------------------------
# Development stage
# ---------------------------------------
FROM node:18.11.0-alpine AS development
WORKDIR /frontend
COPY package*.json yarn.lock tsconfig.json \
    vite.config.ts tsconfig.node.json postcss.config.cjs\
    tailwind.config.cjs ./
RUN apk add --no-cache \
    chromium \
    && rm -rf /var/cache/apk/* /tmp/*
RUN yarn config set network-timeout 300000 && \
    yarn install --frozen-lockfile
# Bundle app source
COPY public/ ./public/
COPY src/ ./src/
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
COPY --from=build /frontend/src/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

ENTRYPOINT ["nginx", "-g", "daemon off;"]
