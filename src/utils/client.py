import primp
import secrets
from typing import Dict, Optional


async def create_client(proxy: Optional[str] = None) -> primp.AsyncClient:
    """
    创建通用的异步 HTTP 客户端。

    Args:
        proxy: 可选的代理字符串，例如 "user:pass@host:port"。

    Returns:
        配置好的 primp.AsyncClient 实例。
    """
    session = primp.AsyncClient(impersonate="chrome_131", verify=False)

    if proxy:
        session.proxy = proxy

    session.timeout = 30
    session.headers.update(HEADERS)

    return session


HEADERS = {
    "accept": "*/*",
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8,ru;q=0.7,zh-TW;q=0.6,zh;q=0.5",
    "content-type": "application/json",
    "priority": "u=1, i",
    "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not=A?Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}


async def create_twitter_client(proxy: Optional[str] = None, auth_token: Optional[str] = None) -> primp.AsyncClient:
    """
    创建 Twitter 专用的异步 HTTP 客户端。

    Args:
        proxy: 可选的代理字符串，例如 "user:pass@host:port"。
        auth_token: Twitter 认证令牌。

    Returns:
        配置好的 primp.AsyncClient 实例。
    """
    session = primp.AsyncClient(impersonate="chrome_131")

    if proxy:
        session.proxies.update({
            "http": f"http://{proxy}",
            "https": f"http://{proxy}",
        })

    session.timeout_seconds = 30

    # 生成 CSRF 令牌
    csrf_token = secrets.token_hex(16)
    cookies = {"ct0": csrf_token}
    if auth_token:
        cookies["auth_token"] = auth_token

    session.cookies.update(cookies)
    session.headers.update({"x-csrf-token": csrf_token})
    session.headers = get_headers(session)

    return session


def get_headers(session: primp.AsyncClient, **kwargs) -> Dict[str, str]:
    """
    生成 Twitter 认证请求所需的头信息。

    Args:
        session: primp.AsyncClient 实例，包含 cookies。
        **kwargs: 额外的头信息键值对。

    Returns:
        排序后的头信息字典。
    """
    cookies = session.cookies
    headers = {
        "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
        "referer": "https://x.com/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "x-csrf-token": cookies.get("ct0", ""),
        "x-twitter-active-user": "yes",
        "x-twitter-client-language": "en",
        "x-twitter-auth-type": "OAuth2Session" if cookies.get("auth_token") else "",
    }

    # 合并额外头信息并规范化
    headers.update(kwargs)
    return dict(sorted({k.lower(): v for k, v in headers.items() if v}))