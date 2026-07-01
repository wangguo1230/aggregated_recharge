#!/usr/bin/env bash
# 本地一键启动：Docker PostgreSQL + 后端(uv) + 充值端 web(vite) + 管理端 admin(vite)
# 用法：
#   ./dev.sh          启动（幂等，可重复执行）
#   ./dev.sh stop     停止所有
#   ./dev.sh restart  重启
#   ./dev.sh logs     跟踪后端日志
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT/.devlogs"
mkdir -p "$LOG_DIR"

# ---- 可调参数 ----
PG_NAME="askwhy-pg"
PG_USER="askwhy"; PG_PASS="askwhy_dev_password"; PG_DB="askwhy"; PG_PORT="5432"
BACKEND_PORT="18424"; WEB_PORT="5173"; ADMIN_PORT="5174"
ADMIN_TOKEN_DEFAULT="devadmintoken123456"

info(){ printf "\033[36m▸ %s\033[0m\n" "$*"; }
ok(){ printf "\033[32m✓ %s\033[0m\n" "$*"; }
err(){ printf "\033[31m✗ %s\033[0m\n" "$*"; }

# ==================== 停止 ====================
stop_all(){
  info "停止 web / admin / 后端 …"
  pkill -f "vite.*--port ${WEB_PORT}" 2>/dev/null || true
  pkill -f "vite.*--port ${ADMIN_PORT}" 2>/dev/null || true
  pkill -f "askwhy-center" 2>/dev/null || true
  ok "已停止前后端进程（PostgreSQL 容器保留，数据不丢；如需停库：docker stop ${PG_NAME}）"
}

# ==================== 依赖检查 ====================
need(){ command -v "$1" >/dev/null 2>&1 || { err "缺少命令：$1，请先安装"; exit 1; }; }

ensure_docker(){
  need docker
  if docker info >/dev/null 2>&1; then return; fi
  info "Docker 未运行，尝试启动 Docker Desktop …"
  open -a Docker 2>/dev/null || { err "无法启动 Docker，请手动打开 Docker Desktop"; exit 1; }
  for _ in $(seq 1 60); do docker info >/dev/null 2>&1 && break; sleep 3; done
  docker info >/dev/null 2>&1 || { err "Docker 守护进程未就绪"; exit 1; }
  ok "Docker 已就绪"
}

ensure_pg(){
  if docker ps --format '{{.Names}}' | grep -q "^${PG_NAME}$"; then
    ok "PostgreSQL 容器已在运行"
  elif docker ps -a --format '{{.Names}}' | grep -q "^${PG_NAME}$"; then
    info "启动已存在的 PostgreSQL 容器 …"; docker start "${PG_NAME}" >/dev/null
  else
    info "创建并启动 PostgreSQL 容器 …"
    docker run -d --name "${PG_NAME}" \
      -e POSTGRES_USER="${PG_USER}" -e POSTGRES_PASSWORD="${PG_PASS}" -e POSTGRES_DB="${PG_DB}" \
      -p "${PG_PORT}:5432" postgres:16-alpine >/dev/null
  fi
  info "等待 PostgreSQL 就绪 …"
  for _ in $(seq 1 30); do docker exec "${PG_NAME}" pg_isready -U "${PG_USER}" >/dev/null 2>&1 && { ok "PostgreSQL 就绪"; return; }; sleep 2; done
  err "PostgreSQL 未就绪"; exit 1
}

ensure_env(){
  local env_file="$ROOT/backend/.env"
  if [ -f "$env_file" ]; then ok "已存在 backend/.env（沿用现有配置）"; return; fi
  info "生成 backend/.env（本地开发）…"
  local secret; secret="$(python3 -c 'import secrets;print(secrets.token_hex(32))')"
  cat > "$env_file" <<EOF
# 本地开发用（dev.sh 生成，勿提交）
ASKWHY_DATABASE_URL=postgresql+psycopg://${PG_USER}:${PG_PASS}@127.0.0.1:${PG_PORT}/${PG_DB}
ASKWHY_SECRET_KEY=${secret}
ASKWHY_ADMIN_TOKEN=${ADMIN_TOKEN_DEFAULT}
ASKWHY_HOST=0.0.0.0
ASKWHY_PORT=${BACKEND_PORT}
ASKWHY_CORS_ALLOW_ORIGINS=*
EOF
  ok "已生成 backend/.env（管理口令：${ADMIN_TOKEN_DEFAULT}）"
}

# ==================== 启动各服务 ====================
start_backend(){
  pkill -f "askwhy-center" 2>/dev/null || true; sleep 1
  info "安装后端依赖（uv sync）…"
  ( cd "$ROOT/backend" && uv sync >/dev/null 2>&1 ) || { err "uv sync 失败"; exit 1; }
  info "启动后端 :${BACKEND_PORT} …"
  ( cd "$ROOT/backend" && nohup uv run askwhy-center > "$LOG_DIR/backend.log" 2>&1 & )
  for _ in $(seq 1 30); do curl -s "http://127.0.0.1:${BACKEND_PORT}/api/askwhy/health" 2>/dev/null | grep -q '"ok":true' && { ok "后端已就绪"; return; }; sleep 1; done
  err "后端未就绪，看日志：$LOG_DIR/backend.log"; tail -15 "$LOG_DIR/backend.log"; exit 1
}

start_front(){ # $1=dir $2=name $3=port
  local dir="$1" name="$2" port="$3"
  pkill -f "vite.*--port ${port}" 2>/dev/null || true
  if [ ! -d "$ROOT/$dir/node_modules" ]; then
    info "安装 ${name} 依赖（npm install，首次较慢）…"
    ( cd "$ROOT/$dir" && npm install > "$LOG_DIR/${name}-install.log" 2>&1 ) || { err "${name} npm install 失败"; exit 1; }
  fi
  info "启动 ${name} :${port} …"
  ( cd "$ROOT/$dir" && nohup npm run dev -- --port "${port}" --strictPort > "$LOG_DIR/${name}.log" 2>&1 & )
  for _ in $(seq 1 30); do [ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${port}/" 2>/dev/null)" = "200" ] && { ok "${name} 已就绪"; return; }; sleep 1; done
  err "${name} 未就绪，看日志：$LOG_DIR/${name}.log"
}

start_all(){
  ensure_docker
  ensure_pg
  ensure_env
  start_backend
  start_front web web "${WEB_PORT}"
  start_front admin admin "${ADMIN_PORT}"
  local token; token="$(grep -E '^ASKWHY_ADMIN_TOKEN=' "$ROOT/backend/.env" | head -1 | cut -d= -f2-)"
  echo
  ok "全部启动完成"
  echo "  充值端(客户) : http://127.0.0.1:${WEB_PORT}"
  echo "  管理端       : http://127.0.0.1:${ADMIN_PORT}   口令: ${token}"
  echo "  后端 API     : http://127.0.0.1:${BACKEND_PORT}"
  echo "  日志目录     : $LOG_DIR （./dev.sh logs 跟踪后端）"
  echo "  停止         : ./dev.sh stop"
}

case "${1:-start}" in
  start)   start_all ;;
  stop)    stop_all ;;
  restart) stop_all; sleep 1; start_all ;;
  logs)    tail -f "$LOG_DIR/backend.log" ;;
  *) echo "用法: ./dev.sh [start|stop|restart|logs]"; exit 1 ;;
esac
