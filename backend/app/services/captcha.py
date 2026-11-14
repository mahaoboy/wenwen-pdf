"""图片验证码：Pillow 生成干扰 PNG，内存存储（5 分钟有效、一次性）。"""
from __future__ import annotations

import base64
import io
import random
import secrets
import threading
import time
from collections import OrderedDict

from PIL import Image, ImageDraw, ImageFilter, ImageFont

TTL_SECONDS = 300
MAX_STORED = 512
CODE_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # 去掉易混淆的 I L O 0 1
CODE_LEN = 4

_store: OrderedDict[str, tuple[str, float]] = OrderedDict()
_lock = threading.Lock()


def _cleanup_locked(now: float) -> None:
    expired = [k for k, (_, exp) in _store.items() if exp <= now]
    for k in expired:
        _store.pop(k, None)
    while len(_store) > MAX_STORED:
        _store.popitem(last=False)


def new_captcha() -> tuple[str, str]:
    """生成验证码。返回 (captcha_id, data_url)。"""
    code = "".join(random.choices(CODE_CHARS, k=CODE_LEN))
    cid = secrets.token_urlsafe(16)
    now = time.time()
    with _lock:
        _cleanup_locked(now)
        _store[cid] = (code.upper(), now + TTL_SECONDS)

    png = _render(code)
    return cid, "data:image/png;base64," + base64.b64encode(png).decode()


def verify_captcha(cid: str, answer: str) -> bool:
    """一次性校验：无论对错，用过即销毁。"""
    if not cid or not answer:
        return False
    now = time.time()
    with _lock:
        _cleanup_locked(now)
        entry = _store.pop(cid, None)
    if entry is None:
        return False
    code, expires = entry
    return expires > now and answer.strip().upper() == code


def _render(code: str) -> bytes:
    width, height = 132, 44
    image = Image.new("RGB", (width, height), (250, 250, 247))
    draw = ImageDraw.Draw(image)

    # 干扰线与噪点
    for _ in range(4):
        x1, y1 = random.randint(0, width // 3), random.randint(0, height)
        x2, y2 = random.randint(width // 2, width), random.randint(0, height)
        draw.line([(x1, y1), (x2, y2)], fill=(180, 180, 180), width=1)
    for _ in range(160):
        x, y = random.randint(0, width), random.randint(0, height)
        draw.point((x, y), fill=(random.randint(140, 210),) * 3)

    # 逐字符绘制并随机旋转
    try:
        font = ImageFont.load_default(size=30)
    except TypeError:  # 旧版 Pillow 无 size 参数
        font = ImageFont.load_default()
    char_w = (width - 24) // CODE_LEN
    for i, ch in enumerate(code):
        tile = Image.new("RGBA", (char_w + 8, height), (0, 0, 0, 0))
        tdraw = ImageDraw.Draw(tile)
        color = random.choice([(44, 62, 80), (194, 64, 42), (30, 90, 60)])
        tdraw.text((4, 4), ch, font=font, fill=color)
        tile = tile.rotate(random.uniform(-22, 22), expand=True, resample=Image.BICUBIC)
        image.paste(tile, (12 + i * char_w, random.randint(-2, 4)), tile)

    image = image.filter(ImageFilter.SMOOTH)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()
