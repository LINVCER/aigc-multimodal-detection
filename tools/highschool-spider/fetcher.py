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

# HTTP 头只能是 latin-1，UA 保持纯 ASCII（说明用途与联系方式，遵守 robots）
UA = ("HighschoolSpider/0.1 (+https://zhiyuan.app/about/crawler; "
      "collects public thesis-policy pages; respects robots; contact ops@zhiyuan.app)")

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

    def __init__(self, delay: float, session: requests.Session | None = None):
        self.delay = delay
        self._session = session or requests.Session()
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._last_hit: dict[str, float] = {}

    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser:
        """自己用统一 UA 取 robots.txt 再喂给解析器：
        2xx 按内容解析；404/410（无 robots）按允许；401/403 按 RFC 禁止；网络错误按允许但照常限速。
        不这么做时 robotparser 用默认 urllib UA，常被高校反爬回 403，被误判成「整站禁止」。"""
        p = urlparse(url)
        base = f"{p.scheme}://{p.netloc}"
        if base not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self._session.get(urljoin(base, "/robots.txt"), timeout=12, headers={"User-Agent": UA})
                if r.status_code in (401, 403):
                    rp.disallow_all = True
                elif 200 <= r.status_code < 300 and r.text.strip():
                    rp.parse(r.text.splitlines())
                else:  # 404/410/空 = 没有 robots，允许
                    rp.allow_all = True
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
        ctype = resp.headers.get("Content-Type", "")
        raw = b""
        for chunk in resp.iter_content(8192):
            raw += chunk
            if len(raw) > max_bytes:
                break
    finally:
        resp.close()
    return _decode(raw, ctype)


def _decode(raw: bytes, ctype: str) -> str:
    """从已拿到的字节判编码（高校站常 GBK）：HTTP 头 charset → HTML meta → utf-8/gb18030 兜底。
    不用 requests 的 apparent_encoding，因为流式消费后 resp.content 已不可再取。"""
    import re
    m = re.search(r"charset=([\w-]+)", ctype, re.I)
    if m:
        try:
            return raw.decode(m.group(1), errors="replace")
        except LookupError:
            pass
    head = raw[:2048].decode("ascii", errors="ignore").lower()
    m = re.search(r'charset=["\']?([\w-]+)', head)
    if m:
        try:
            return raw.decode(m.group(1), errors="replace")
        except LookupError:
            pass
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
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


# ---- 深度模式：附件（红头文件多为 PDF/DOC/DOCX）正文抽取 ----
ATTACH_EXT = (".pdf", ".doc", ".docx")


def fetch_bytes(url: str, session: requests.Session, timeout: int, max_bytes: int) -> bytes | None:
    try:
        resp = session.get(url, timeout=timeout, stream=True, headers={"User-Agent": UA})
    except requests.RequestException as e:
        log.warning("附件请求失败 %s：%s", url, e)
        return None
    try:
        if resp.status_code != 200:
            return None
        raw = b""
        for chunk in resp.iter_content(8192):
            raw += chunk
            if len(raw) > max_bytes:
                break
        return raw
    finally:
        resp.close()


def attachment_text(url: str, raw: bytes) -> str:
    """按扩展名抽附件正文；解析库缺失时告警并返回空串（不阻断爬取）。"""
    low = url.lower().split("?")[0]
    try:
        if low.endswith(".pdf"):
            return _pdf_text(raw)
        if low.endswith(".docx"):
            return _docx_text(raw)
        if low.endswith(".doc"):
            return _doc_text(raw)
    except Exception as e:
        log.warning("附件解析失败 %s：%s", url, e)
    return ""


def _pdf_text(raw: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        log.warning("未装 pypdf，跳过 PDF 附件；pip install pypdf")
        return ""
    import io as _io
    reader = PdfReader(_io.BytesIO(raw))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def _docx_text(raw: bytes) -> str:
    try:
        import docx
    except ImportError:
        log.warning("未装 python-docx，跳过 DOCX 附件；pip install python-docx")
        return ""
    import io as _io
    d = docx.Document(_io.BytesIO(raw))
    return "\n".join(p.text for p in d.paragraphs)


def _doc_text(raw: bytes) -> str:
    # 老 .doc 二进制格式无纯 Python 稳定解析，尽力从字节里抠出可见中文/数字，失败就放弃交人工
    try:
        txt = raw.decode("gb18030", errors="ignore")
    except Exception:
        return ""
    import re as _re
    keep = _re.findall(r"[一-鿿0-9%．.、：:；;，,（）()≤<不得超过低于高于以内]+", txt)
    return "\n".join(s for s in keep if len(s) >= 4)
