#!/usr/bin/env bash
# 本地构建 backend/web/admin 三镜像并推送到 ghcr.io（替代 GitHub Actions）。
#
# 前置：先登录镜像仓库（GitHub Packages），token 需有 write:packages 权限：
#   echo <你的GHCR_TOKEN> | docker login ghcr.io -u <GitHub用户名> --password-stdin
#
# 用法：
#   ./scripts/build-and-push.sh              # 构建并推送三镜像（:latest + :<git短SHA>）
#   IMAGE_REPO=owner/repo ./scripts/...       # 覆盖镜像仓库前缀
#   SERVICES="backend web" ./scripts/...      # 只构建部分
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REGISTRY="${REGISTRY:-ghcr.io}"
PLATFORM="${PLATFORM:-linux/amd64}"   # 部署机是 Linux/amd64，mac 上需交叉构建
SERVICES="${SERVICES:-backend web admin}"

info(){ printf "\033[36m▸ %s\033[0m\n" "$*"; }
ok(){ printf "\033[32m✓ %s\033[0m\n" "$*"; }
err(){ printf "\033[31m✗ %s\033[0m\n" "$*"; }

command -v docker >/dev/null 2>&1 || { err "缺少 docker"; exit 1; }
docker info >/dev/null 2>&1 || { err "Docker 未运行，请先启动 Docker Desktop"; exit 1; }

# 镜像仓库前缀：优先 IMAGE_REPO，其次从 git remote 解析，兜底默认。
repo="${IMAGE_REPO:-}"
if [ -z "$repo" ]; then
  url="$(git -C "$ROOT" remote get-url origin 2>/dev/null || true)"
  repo="$(printf '%s' "$url" | sed -E 's#(git@github.com:|https://github.com/)##; s/\.git$//')"
fi
repo="$(printf '%s' "${repo:-wangguo1230/aggregated_recharge}" | tr 'A-Z' 'a-z')"

SHA="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo local)"
info "镜像前缀：${REGISTRY}/${repo}-<svc>   标签：latest, ${SHA}   平台：${PLATFORM}"

for svc in $SERVICES; do
  image="${REGISTRY}/${repo}-${svc}"
  info "构建 ${image} …"
  docker build --platform "${PLATFORM}" \
    -t "${image}:latest" -t "${image}:${SHA}" \
    "${ROOT}/${svc}"
  info "推送 ${image} …"
  docker push "${image}:latest"
  docker push "${image}:${SHA}"
  ok "${image} 已推送"
done

ok "全部完成：${REGISTRY}/${repo}-{$(echo "$SERVICES" | tr ' ' ',')} :latest / :${SHA}"
echo "  部署机执行：cd deploy && docker compose pull && docker compose up -d"
