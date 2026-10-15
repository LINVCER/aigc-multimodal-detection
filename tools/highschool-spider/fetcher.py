"""
抓取公共层：robots.txt 合规 + 每域限速 + 取页 + 正文/链接解析
=============================================================

借 spider-v2 的分层思路，把「怎么礼貌地把一页 HTML 拿下来」从业务里拆出来做公共层。
硬约束：遵守 robots.txt、每域限速、只读 HTML、限大小，不碰任何鉴权。
"""
from __future__ import annotations

import logging
import time
import urllib.robotparser
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("hsspider.fetch")

UA = ("HighschoolSpider/0.1 (+https://zhiyuan.app/about/crawler; "
      "高校学位论文政策公开信息收集; 遵守robots; 联系 ops@zhiyuan.app)")

CN_PUBLIC_SUFFIX = (".edu.cn", ".gov.cn", ".com.cn", ".net.cn", ".org.cn", ".ac.cn")


def registrable_domain(host: str) -> str:
    """可注册域：xxx.edu.cn 取后 3 段，普通域取后 2 段，用于把爬取限制在本校域内。"""
    host = (host or "").lower().strip(".")
    labels = host.split(".")
    if host.endswith(CN_PUBLIC_SUFFIX) and len(labels) >= 3:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


class Politeness:
    """robots.txt 解析缓存 + 每域最小间隔。"""

    def __init__(self, delay: float):
        self.delay = delay
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._last_hit: dict[str, float] = {}

    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser:
        p = urlparse(url)
        base = f"{p.scheme}://{p.netloc}"
        if base not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(urljoin(base, "/robots.txt"))
            try:
                rp.read()
            except Exception as e:
                log.warning("robots 读取失败 %s：%s（按允许处理，但照常限速）", base, e)
                rp.allow_all = True
            self._robots[base] = rp
        return self._robots[base]

    def can_fetch(self, url: str) -> bool:
        try:
            return self._robots_for(url).can_fetch(UA, url)
        except Exception:
            return True

    def wait(self, url: str) -> None:
        host = urlparse(url).netloc
        try:
            cd = self._robots_for(url).crawl_delay(UA)
        except Exception:
            cd = None
        delay = max(self.delay, cd or 0)
        gap = time.time() - self._last_hit.get(host, 0)
        if gap < delay:
            time.sleep(delay - gap)
        self._last_hit[host] = time.time()


def fetch_html(url: str, session: requests.Session, timeout: int, max_bytes: int) -> str | None:
    """只收 200 的 text/html，超 max_bytes 截断；GBK/UTF-8 自动判。"""
    try:
        resp = session.get(url, timeout=timeout, stream=True, headers={"User-Agent": UA})
    except requests.RequestException as e:
        log.warning("请求失败 %s：%s", url, e)
        return None
    try:
        if resp.status_code != 200 or "html" not in resp.headers.get("Content-Type", "").lower():
            return None
        raw = b""
        for chunk in resp.iter_content(8192):
            raw += chunk
            if len(raw) > max_bytes:
                break
    finally:
        resp.close()
    enc = resp.apparent_encoding or resp.encoding or "utf-8"
    try:
        return raw.decode(enc, errors="replace")
    except (LookupError, TypeError):
        return raw.decode("utf-8", errors="replace")


def parse_page(html: str) -> tuple[str, str, list[tuple[str, str]]]:
    """返回 (标题, 正文纯文本, [(锚文本, href)])。"""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = soup.title.get_text(strip=True) if soup.title else ""
    body = soup.get_text("\n", strip=True)
    links = [(a.get_text(strip=True), a["href"]) for a in soup.find_all("a", href=True)]
    return title, body, links
