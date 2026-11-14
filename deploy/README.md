# 部署指南（云服务器 · 免费版）

## 前提

- 云服务器：Ubuntu 22.04+，建议 ≥2C/4G（含 2G swap 更稳，嵌入模型推理需要内存）
- Node.js ≥18 与系统 Python 3.10+
- 云安全组：**只放行 22 / 80**；8000、3000 一律不对公网开放
- 系统兜底 Key：`~/token/deepseektoken` 的内容填入 `backend/.env` 的 `DEEPSEEK_API_KEY`

## 步骤

```bash
# 1. 本机同步代码到服务器（把 <server-ip> 换成你的公网 IP）
rsync -av --exclude .venv --exclude node_modules --exclude .next --exclude .git \
  /home/mahao/coding/PDF文档问答/ mahao@<server-ip>:/tmp/wenwen-src/

# 2. 服务器上执行
ssh mahao@<server-ip>
cd /tmp/wenwen-src && sudo bash deploy/deploy.sh
# 首次运行会生成 /opt/wenwen/backend/.env，填入 DEEPSEEK_API_KEY 后重跑一遍脚本

# 3. 验证
curl http://<server-ip>/          # 首页
curl http://<server-ip>/api/health # 后端健康
```

## 安全设计（默认已含）

| 层 | 措施 |
|----|------|
| 网络入口 | 仅 nginx 80 对公网；后端/前端只绑 127.0.0.1 |
| 防爆破 | /api/auth/* 每 IP 每分钟 5 次（429） |
| 防滥用 | 其他 API 每 IP 每秒 10 次；上传 ≤20MB |
| 成本护栏 | 免费额度 3 文档 / 20 提问（应用层硬限制） |
| 响应头 | X-Frame-Options / nosniff / Referrer-Policy |
| 服务隔离 | systemd 加固（NoNewPrivileges / ProtectSystem） |

## 上线前加做（对外推广时）

1. **域名 + HTTPS**：域名解析到服务器 IP → `apt install certbot python3-certbot-nginx && certbot --nginx` → 自动改 443 配置
2. **注册防刷**：注册接口加图形验证码或邮箱验证（防批量注册烧兜底 Key）
3. **fail2ban**：`apt install fail2ban` 防 SSH 爆破
4. **自动备份**：SQLite + uploads 目录定时快照（用户文档是敏感数据）

## 已知限制（免费版）

- HTTP 明文传输（IP 部署无证书）——自用可接受，对外推广必须上 HTTPS
- 用户自备 Key 明文存 SQLite——生产化时加密
- 单机 SQLite——并发数百用户内够用，再大迁 PostgreSQL
