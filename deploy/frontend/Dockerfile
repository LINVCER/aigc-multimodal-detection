# 用户端 Web：Vite build → Nginx serve
# 上下文 = 仓库根（compose 里 context: .. 已设置）

FROM node:20-alpine AS builder

ARG VITE_API_BASE=""
ENV VITE_API_BASE=${VITE_API_BASE}

WORKDIR /app

# 拷 package 与 lock 优先，利用层缓存
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm config set registry https://registry.npmmirror.com && \
    npm install --frozen-lockfile || npm install

# 拷源码
COPY frontend/ ./

RUN npm run build && ls -lh dist

# ============ Runtime ============
FROM nginx:1.27-alpine

RUN rm -rf /usr/share/nginx/html/*

COPY --from=builder /app/dist /usr/share/nginx/html

# SPA history 路由需要 fallback 到 index.html
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
