#!/usr/bin/env bash
# 文问一键部署脚本（在云服务器上执行）
# 用法：把整个项目目录 rsync 到服务器后，sudo bash deploy/deploy.sh
set -euo pipefail

INSTALL_ROOT=/opt/wenwen
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_USER="${SERVICE_USER:-$(logname 2>/dev/null || echo mahao)}"

echo "==> 1/7 系统依赖"
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip nginx curl rsync > /dev/null
command -v node >/dev/null || { echo "未检测到 Node.js（需要 ≥18），请先安装：curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs"; exit 1; }

echo "==> 2/7 同步代码到 $INSTALL_ROOT"
mkdir -p "$INSTALL_ROOT"
rsync -a --delete \
  --exclude ".venv" --exclude "node_modules" --exclude ".next" \
  --exclude "wenwen.db" --exclude "vectors" --exclude "uploads" \
  --exclude "chroma_data" --exclude ".git" \
  "$PROJECT_DIR/" "$INSTALL_ROOT/"
chown -R "$SERVICE_USER":"$SERVICE_USER" "$INSTALL_ROOT"

echo "==> 3/7 后端环境（含 PyMuPDF/PaddleOCR 依赖）"
sudo -u "$SERVICE_USER" bash -c "
  cd $INSTALL_ROOT/backend
  [ -d .venv ] || python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/
  .venv/bin/pip install -q torch --index-url https://download.pytorch.org/whl/cpu
  .venv/bin/pip install -q -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
"
# .env：首次部署从 example 生成（已存在则保留，密钥不覆盖）
if [ ! -f "$INSTALL_ROOT/backend/.env" ]; then
  cp "$INSTALL_ROOT/backend/.env.example" "$INSTALL_ROOT/backend/.env"
  chown "$SERVICE_USER":"$SERVICE_USER" "$INSTALL_ROOT/backend/.env"
  chmod 600 "$INSTALL_ROOT/backend/.env"
  echo "!! 已生成 $INSTALL_ROOT/backend/.env —— 请填入 DEEPSEEK_API_KEY 等配置后重跑本脚本"
  exit 0
fi

echo "==> 4/7 前端构建"
sudo -u "$SERVICE_USER" bash -c "
  cd $INSTALL_ROOT/frontend
  [ -d node_modules ] || npm install --registry=https://registry.npmmirror.com
  npm run build
"
# 前端生产环境走同源（nginx 统一入口），构建期清空 API 基址
rm -f "$INSTALL_ROOT/frontend/.env.local" "$INSTALL_ROOT/frontend/.env.production"
sudo -u "$SERVICE_USER" bash -c "cd $INSTALL_ROOT/frontend && NEXT_PUBLIC_API_BASE='' npm run build"

echo "==> 5/7 systemd 服务"
sed -i "s|^User=.*|User=$SERVICE_USER|" /tmp/wenwen-backend.service /tmp/wenwen-frontend.service 2>/dev/null || true
cp "$INSTALL_ROOT/deploy/systemd/wenwen-backend.service" /etc/systemd/system/
cp "$INSTALL_ROOT/deploy/systemd/wenwen-frontend.service" /etc/systemd/system/
sed -i "s|^User=.*|User=$SERVICE_USER|" /etc/systemd/system/wenwen-backend.service /etc/systemd/system/wenwen-frontend.service
systemctl daemon-reload
systemctl enable --now wenwen-backend wenwen-frontend

echo "==> 6/7 nginx"
cp "$INSTALL_ROOT/deploy/nginx/wenwen-proxy.conf" /etc/nginx/snippets/wenwen-proxy.conf
cp "$INSTALL_ROOT/deploy/nginx/wenwen.conf" /etc/nginx/sites-available/wenwen.conf
ln -sf /etc/nginx/sites-available/wenwen.conf /etc/nginx/sites-enabled/wenwen.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo "==> 7/7 健康检查"
sleep 3
curl -sf http://127.0.0.1:8000/api/health >/dev/null && echo "backend OK"
curl -sf -o /dev/null http://127.0.0.1:3000/ && echo "frontend OK"
curl -sf -o /dev/null http://127.0.0.1/ && echo "nginx OK"
SERVER_IP=$(curl -s ifconfig.me || echo "<服务器IP>")
echo ""
echo "部署完成：http://$SERVER_IP"
echo "安全清单（务必检查）："
echo "  1. 云安全组只放行 22/80，8000/3000 不对公网开放"
echo "  2. backend/.env 已填 DEEPSEEK_API_KEY（兜底 Key）"
echo "  3. SSH 建议改密钥登录并限制来源 IP"
echo "  4. 对外推广前：买域名 + certbot 上 HTTPS"
