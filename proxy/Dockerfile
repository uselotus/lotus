# ---------------------------------------
# Development stage
# ---------------------------------------
FROM nginx:1.23-alpine
#copy static files to nginx
RUN rm -rf /usr/share/nginx/html/*
COPY nginx.conf /etc/nginx/conf.d/default.conf

ENTRYPOINT ["nginx", "-g", "daemon off;"]
