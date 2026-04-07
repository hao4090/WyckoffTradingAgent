# -*- coding: utf-8 -*-
"""
统一通知：飞书 + 企微 + 钉钉 + Telegram。按配置的 webhook 分别发送，互不影响。
"""
from __future__ import annotations

import os

import requests

# ── Telegram ──

TELEGRAM_MAX_LEN = 3900


def _split_telegram_message(content: str, max_len: int = TELEGRAM_MAX_LEN) -> list[str]:
    """将超长文本按行分割为多段，每段不超过 max_len 字符。"""
    if len(content) <= max_len:
        return [content]
    chunks: list[str] = []
    cur = ""
    for line in content.splitlines(keepends=True):
        if len(line) > max_len:
            if cur:
                chunks.append(cur.rstrip("\n"))
                cur = ""
            start = 0
            while start < len(line):
                chunks.append(line[start:start + max_len].rstrip("\n"))
                start += max_len
            continue
        if len(cur) + len(line) <= max_len:
            cur += line
        else:
            if cur:
                chunks.append(cur.rstrip("\n"))
            cur = line
    if cur:
        chunks.append(cur.rstrip("\n"))
    return chunks


def send_to_telegram(
    message_text: str,
    *,
    tg_bot_token: str,
    tg_chat_id: str,
) -> bool:
    """发送 Telegram Bot 消息。token 或 chat_id 为空则跳过。"""
    token = str(tg_bot_token or "").strip()
    chat_id = str(tg_chat_id or "").strip()
    if not token or not chat_id:
        print("[telegram] tg_bot_token/tg_chat_id 未配置，跳过 Telegram 推送")
        return False

    proxy_url = os.getenv("PROXY_URL", "").strip()
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    chunks = _split_telegram_message(message_text)
    for idx, chunk in enumerate(chunks, start=1):
        payload = {
            "chat_id": chat_id,
            "text": chunk if len(chunks) == 1 else f"[{idx}/{len(chunks)}]\n{chunk}",
            "disable_web_page_preview": True,
        }
        try:
            resp = requests.post(url, json=payload, timeout=15, proxies=proxies)
            if resp.status_code != 200:
                print(f"[telegram] 推送失败: status={resp.status_code}, body={resp.text[:200]}")
                return False
        except Exception as e:
            print(f"[telegram] 推送异常: {e}")
            return False
    return True


# ── 企微 ──


def send_wecom_notification(webhook_url: str, title: str, content: str) -> bool:
    """发送企业微信群机器人 Markdown 消息。URL 为空则返回 False。"""
    if not webhook_url or not webhook_url.strip():
        return False
    url = webhook_url.strip()
    # 企微 markdown 单条最长 4096 字节，过长则截断并注明
    max_len = 4000
    body = f"# {title}\n\n{content}" if title else content
    if len(body.encode("utf-8")) > max_len:
        body = body[: max_len // 2] + "\n\n...(内容过长已截断)"
    payload = {"msgtype": "markdown", "markdown": {"content": body}}
    try:
        resp = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=10)
        if resp.status_code != 200:
            print(f"[wecom] http {resp.status_code}: {resp.text[:200]}")
            return False
        data = resp.json()
        if data.get("errcode") != 0:
            print(f"[wecom] errcode {data.get('errcode')}: {data.get('errmsg', '')}")
            return False
        return True
    except Exception as e:
        print(f"[wecom] exception: {e}")
        return False


def send_dingtalk_notification(webhook_url: str, title: str, content: str) -> bool:
    """发送钉钉自定义机器人 Markdown 消息。URL 为空则返回 False。"""
    if not webhook_url or not webhook_url.strip():
        return False
    url = webhook_url.strip()
    # 钉钉 markdown text 建议不超过 2 万字符，这里按 4000 字节截断
    max_len = 4000
    text = f"# {title}\n\n{content}" if title else content
    if len(text.encode("utf-8")) > max_len:
        text = text[: max_len // 2] + "\n\n...(内容过长已截断)"
    payload = {"msgtype": "markdown", "markdown": {"title": title or "通知", "text": text}}
    try:
        resp = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=10)
        if resp.status_code != 200:
            print(f"[dingtalk] http {resp.status_code}: {resp.text[:200]}")
            return False
        data = resp.json()
        if data.get("errcode") != 0:
            print(f"[dingtalk] errcode {data.get('errcode')}: {data.get('errmsg', '')}")
            return False
        return True
    except Exception as e:
        print(f"[dingtalk] exception: {e}")
        return False


def send_all_webhooks(
    feishu_url: str,
    wecom_url: str,
    dingtalk_url: str,
    title: str,
    content: str,
    *,
    tg_bot_token: str = "",
    tg_chat_id: str = "",
) -> None:
    """
    向已配置的飞书、企微、钉钉、Telegram 各发一条通知；某个 URL/token 为空则跳过该渠道。
    飞书使用 utils.feishu.send_feishu_notification（支持分片）；企微/钉钉/Telegram 使用本模块。
    """
    if feishu_url and feishu_url.strip():
        try:
            from utils.feishu import send_feishu_notification
            send_feishu_notification(feishu_url.strip(), title, content)
        except Exception as e:
            print(f"[notify] feishu failed: {e}")
    if wecom_url and wecom_url.strip():
        try:
            send_wecom_notification(wecom_url.strip(), title, content)
        except Exception as e:
            print(f"[notify] wecom failed: {e}")
    if dingtalk_url and dingtalk_url.strip():
        try:
            send_dingtalk_notification(dingtalk_url.strip(), title, content)
        except Exception as e:
            print(f"[notify] dingtalk failed: {e}")
    if tg_bot_token and tg_chat_id:
        try:
            tg_content = f"{title}\n\n{content}" if title else content
            send_to_telegram(tg_content, tg_bot_token=tg_bot_token, tg_chat_id=tg_chat_id)
        except Exception as e:
            print(f"[notify] telegram failed: {e}")
