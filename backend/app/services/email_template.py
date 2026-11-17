"""邮件模板：验证码 + 密码重置 两套模板，纯文本 + HTML 双版本。

反垃圾要点：主题不带方括号、正文含品牌上下文与"非本人操作"说明、
HTML 结构完整（卡片式居中布局）、文本/HTML 双版本（multipart/alternative）。
"""
from __future__ import annotations


# ===== 验证码邮件 =====

def build_subject(code: str) -> str:
    return f"文问 WenWen 验证码 {code}（10 分钟内有效）"


def build_text(code: str) -> str:
    return (
        f"你的邮箱验证码：{code}\n"
        f"10 分钟内有效。\n\n"
        f"如非本人操作，请忽略本邮件，你的账号不会受任何影响。\n"
        f"—— 文问 WenWen · 上传文档，直接提问，答案可核对"
    )


def build_html(code: str) -> str:
    # 邮件客户端只支持内联样式
    return f"""
<div style="margin:0;padding:32px 16px;background:#f2f3f5;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;">
  <div style="max-width:460px;margin:0 auto;background:#ffffff;border-radius:16px;padding:40px 36px;text-align:center;border:1px solid #ececec;">
    <div style="width:48px;height:48px;line-height:48px;margin:0 auto 16px;background:#c2402a;color:#ffffff;border-radius:10px;font-size:22px;font-weight:700;">文</div>
    <div style="font-size:15px;color:#1c1e21;font-weight:600;">文问 WenWen · 邮箱验证</div>
    <p style="margin:18px 0 8px;font-size:14px;color:#5b5f66;">你的验证码（10 分钟内有效）：</p>
    <div style="margin:14px 0 6px;">
      <span style="display:inline-block;font-size:34px;font-weight:800;letter-spacing:10px;text-indent:10px;color:#1c1e21;padding:14px 24px;background:#fafaf7;border:1px solid #ececec;border-radius:12px;">{code}</span>
    </div>
    <p style="margin:18px 0 0;font-size:13px;line-height:1.7;color:#8a8f98;">
      请在 10 分钟内输入验证码完成验证。<br/>
      如非本人操作，请忽略本邮件，你的账号不会受任何影响。
    </p>
  </div>
  <p style="max-width:460px;margin:14px auto 0;font-size:12px;color:#b0b4ba;text-align:center;">
    文问 WenWen · 上传文档，直接提问，答案可核对
  </p>
</div>
"""


# ===== 密码重置邮件 =====

def build_reset_subject() -> str:
    return "文问 WenWen · 密码重置链接（15 分钟内有效）"


def build_reset_text(reset_url: str) -> str:
    return (
        f"你正在申请重置文问账号密码。\n\n"
        f"点击以下链接即可设置新密码（15 分钟内有效）：\n{reset_url}\n\n"
        f"如果链接无法点击，请将上方地址复制到浏览器打开。\n\n"
        f"如非本人操作，请忽略本邮件，你的密码不会改变。\n"
        f"—— 文问 WenWen · 上传文档，直接提问，答案可核对"
    )


def build_reset_html(reset_url: str) -> str:
    return f"""
<div style="margin:0;padding:32px 16px;background:#f2f3f5;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;">
  <div style="max-width:460px;margin:0 auto;background:#ffffff;border-radius:16px;padding:40px 36px;text-align:center;border:1px solid #ececec;">
    <div style="width:48px;height:48px;line-height:48px;margin:0 auto 16px;background:#c2402a;color:#ffffff;border-radius:10px;font-size:22px;font-weight:700;">文</div>
    <div style="font-size:15px;color:#1c1e21;font-weight:600;">文问 WenWen · 密码重置</div>
    <p style="margin:18px 0 8px;font-size:14px;color:#5b5f66;">你正在申请重置账号密码，点击下方按钮设置新密码：</p>
    <div style="margin:16px 0;">
      <a href="{reset_url}" style="display:inline-block;font-size:14px;font-weight:600;color:#ffffff;text-decoration:none;padding:12px 32px;background:#c2402a;border-radius:12px;">设置新密码</a>
    </div>
    <p style="margin:0;font-size:13px;line-height:1.7;color:#8a8f98;">
      链接 15 分钟内有效。<br/>
      如果按钮无法点击，请复制以下地址到浏览器打开：<br/>
      <span style="word-break:break-all;color:#c2402a;">{reset_url}</span>
    </p>
    <p style="margin:14px 0 0;font-size:12px;color:#8a8f98;">
      如非本人操作，请忽略本邮件，你的密码不会改变。
    </p>
  </div>
  <p style="max-width:460px;margin:14px auto 0;font-size:12px;color:#b0b4ba;text-align:center;">
    文问 WenWen · 上传文档，直接提问，答案可核对
  </p>
</div>
"""
