# 管理端 Web (plus-ui) —— 若依 RuoYi-Vue-Plus 配套管理界面
# 上下文 = deploy/admin-web

FROM node:20-alpine AS builder

ARG PLUS_UI_GIT_URL=https://gitee.com/JavaLionLi/plus-ui.git
ARG PLUS_UI_BRANCH=master
ARG VITE_APP_BASE_API=/admin-api

RUN apk add --no-cache git

WORKDIR /build

RUN git clone --depth 1 --branch ${PLUS_UI_BRANCH} ${PLUS_UI_GIT_URL} plus-ui && cd plus-ui && ls -la

WORKDIR /build/plus-ui

RUN npm config set registry https://registry.npmmirror.com && \
    (npm install --frozen-lockfile || npm install)

# 写入生产环境 API base（Nginx 会把 /admin-api/ 反代到 backend）
RUN cat > .env.production <<EOF
VITE_APP_TITLE = 论文AIGC检测·管理后台
VITE_APP_ENV = 'production'
VITE_APP_BASE_API = '${VITE_APP_BASE_API}'
VITE_APP_MONITOR_ADMIN = '/admin'
VITE_APP_SNAILJOB_ADMIN = '/snail-job'
EOF

RUN npm run build:prod && ls -lh dist

# ============ Runtime ============
FROM nginx:1.27-alpine

RUN rm -rf /usr/share/nginx/html/*

COPY --from=builder /build/plus-ui/dist /usr/share/nginx/html

RUN cat > /etc/nginx/conf.d/default.conf <<'EOF'
server {
  listen 80;
  server_name _;
  root /usr/share/nginx/html;
  index index.html;

  gzip on;
  gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss;

  location / {
    try_files $uri $uri/ /index.html;
  }

  location = /health {
    access_log off;
    return 200 'ok';
    add_header Content-Type text/plain;
  }
}
EOF

EXPOSE 80
