#!/usr/bin/env bash
set -euo pipefail

# SSGDFS 线上运维脚本
# 功能：
# 1) 拉取最新代码
# 2) 查看服务状态
# 3) 重启服务
# 4) 查看实时日志
# 5) 检查并重载 Nginx

APP_DIR="/home/ubuntu/ssgdfs-web"
SERVICE_NAME="ssgdfs-web"
NGINX_SITE_FILE="/etc/nginx/sites-available/lubanos"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
  echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $*"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    log_error "缺少命令: $1"
    exit 1
  }
}

pull_latest_code() {
  log_info "拉取最新代码..."
  cd "$APP_DIR"
  if [[ -d ".git" ]]; then
    require_cmd git
    git fetch --all --prune
    git checkout main
    git pull --ff-only origin main
    log_info "代码拉取完成。"
  else
    log_warn "当前目录不是 Git 仓库（无 .git）。"
    log_warn "请在本地执行上传命令同步代码，例如："
    echo "  scp -r <本地项目文件> ubuntu@lubanos.com:/home/ubuntu/ssgdfs-web/"
    log_warn "本步骤已跳过，不影响后续重启与 Nginx 重载。"
  fi
}

show_service_status() {
  log_info "查看服务状态: ${SERVICE_NAME}"
  sudo systemctl status "$SERVICE_NAME" --no-pager -l
}

restart_service() {
  log_info "重启服务: ${SERVICE_NAME}"
  sudo systemctl restart "$SERVICE_NAME"
  sudo systemctl status "$SERVICE_NAME" --no-pager -l | sed -n '1,30p'
}

show_live_logs() {
  log_info "实时日志: ${SERVICE_NAME}（按 Ctrl+C 退出）"
  sudo journalctl -u "$SERVICE_NAME" -f
}

reload_nginx() {
  log_info "检查并重载 Nginx..."
  require_cmd nginx
  if [[ -f "$NGINX_SITE_FILE" ]]; then
    log_info "当前站点配置文件: $NGINX_SITE_FILE"
  else
    log_warn "未找到站点配置文件: $NGINX_SITE_FILE（继续执行 nginx -t）"
  fi
  sudo nginx -t
  sudo systemctl reload nginx
  log_info "Nginx 重载完成。"
}

full_deploy() {
  pull_latest_code
  restart_service
  reload_nginx
  show_service_status
}

usage() {
  cat <<'EOF'
用法:
  bash ssgdfs_ops.sh <命令>
  bash ssgdfs_ops.sh          # 进入交互菜单

命令:
  pull        拉取最新代码
  status      查看服务状态
  restart     重启服务
  logs        查看实时日志
  nginx       检查并重载 Nginx
  deploy      一键发布（pull + restart + nginx + status）
  help        显示帮助
EOF
}

interactive_menu() {
  while true; do
    echo
    echo "========== SSGDFS 运维菜单 =========="
    echo "1) 拉取最新代码"
    echo "2) 查看服务状态"
    echo "3) 重启服务"
    echo "4) 查看实时日志"
    echo "5) 检查并重载 Nginx"
    echo "6) 一键发布（pull + restart + nginx + status）"
    echo "0) 退出"
    echo "===================================="
    read -rp "请输入选项: " choice
    case "${choice:-}" in
      1) pull_latest_code ;;
      2) show_service_status ;;
      3) restart_service ;;
      4) show_live_logs ;;
      5) reload_nginx ;;
      6) full_deploy ;;
      0) exit 0 ;;
      *) log_warn "无效选项，请重新输入。" ;;
    esac
  done
}

main() {
  case "${1:-}" in
    pull) pull_latest_code ;;
    status) show_service_status ;;
    restart) restart_service ;;
    logs) show_live_logs ;;
    nginx) reload_nginx ;;
    deploy) full_deploy ;;
    help|-h|--help) usage ;;
    "") interactive_menu ;;
    *)
      log_error "未知命令: $1"
      usage
      exit 1
      ;;
  esac
}

main "$@"
