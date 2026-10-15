"""
highschool-spider · 高校公开页学位论文红线爬虫（礼貌版）
=======================================================

目的：帮用户查到「自己学校对学位论文 AIGC 率 / 查重率的要求」。
做法：只爬 seeds.csv 里指定的高校研究生院 / 教务处公开通知页，找阈值候选，
      产出 out/candidates.{jsonl,csv}，status=pending 交后台人工审核后才落 edu_school_rule。
      关联：docs/design/202610-school-redline-plan.md

它不做什么（硬约束）：
- 不碰需要登录 / 验证码 / 付费的页面，不绕过任何鉴权
- 不抓知网 / 维普 / 万方等检测平台，只抓高校自己的公开通知
- 遵守 robots.txt；每域限速、限页数、限深度；只在 seed 所属 edu.cn 域内爬；只读 HTML

用法::

    # 自测（离线，不联网）
    python tools/highschool-spider/spider.py --selftest
    # 预演：只打印将访问的入口，不发真实请求
    python tools/highschool-spider/spider.py --seeds tools/highschool-spider/seeds.example.csv --dry-run
    # 实跑
    python tools/highschool-spider/spider.py --seeds my_seeds.csv --out out --delay 5 --max-pages 40 --cache-dir out/cache

seeds.csv 列：school_id,school_name,entry_url[,note]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import logging
import os
import sys
from collections import deque
from urllib.parse import urljoin, urlparse

# 让 adapters / extract / fetcher 以顶层模块被导入（脚本所在目录已在 sys.path[0]）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests  # noqa: E402

import extract  # noqa: E402
from adapters import get_adapter  # noqa: E402
from fetcher import (  # noqa: E402
    Politeness, attachment_text, fetch_bytes, fetch_html, parse_page, registrable_domain,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s")
log = logging.getLogger("hsspider")


def load_seeds(path: str) -> list[dict]:
    rows = []
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            sid = (r.get("school_id") or "").strip()
            url = (r.get("entry_url") or "").strip()
            if sid.startswith("#") or url.startswith("#") or not url:
                continue  # # 开头的行当注释
            rows.append({k: (v or "").strip() for k, v in r.items()})
    return rows


def _cache(cache_dir: str, url: str, html: str) -> None:
    os.makedirs(cache_dir, exist_ok=True)
    name = hashlib.sha1(url.encode()).hexdigest()[:16] + ".html"
    io.open(os.path.join(cache_dir, name), "w", encoding="utf-8").write(html)


def crawl_seed(seed: dict, pol: Politeness, session: requests.Session, args, pages_out: list[dict]) -> list[dict]:
    adapter = get_adapter(seed)
    adapter.deep = args.deep
    seed_dom = registrable_domain(urlparse(seed["entry_url"]).netloc)
    seen: set[str] = set()
    q: deque[tuple[str, int]] = deque((u, 0) for u in adapter.seed_urls(seed))
    candidates: list[dict] = []
    fetched = 0
    attach_budget = args.max_attachments

    while q and fetched < args.max_pages:
        url, depth = q.popleft()
        url = url.split("#")[0]
        if url in seen:
            continue
        seen.add(url)
        if registrable_domain(urlparse(url).netloc) != seed_dom:
            continue

        if args.dry_run:
            log.info("[dry-run] %s 适配器 %s%s 将抓取 d%d %s", seed["school_name"], adapter.name,
                     "(deep)" if args.deep else "", depth, url)
            fetched += 1
            continue

        if not pol.can_fetch(url):
            log.info("robots 禁止，跳过 %s", url)
            continue
        pol.wait(url)
        html = fetch_html(url, session, args.timeout, args.max_bytes)
        fetched += 1
        if not html:
            continue
        if args.cache_dir:
            _cache(args.cache_dir, url, html)

        title, body, links = parse_page(html)
        if adapter.page_relevant(title, body):
            basics = extract.extract_basics(f"{title}\n{body}", title)
            rows = extract.extract_rules(f"{title}\n{body}", url, seed.get("school_id", ""),
                                         seed.get("school_name", ""), basics["notice_title"], basics["publish_date"])
            if rows:
                log.info("命中 %d 条候选 @ %s", len(rows), url)
                candidates.extend(rows)
                pages_out.append({"url": url, "school_id": seed.get("school_id", ""),
                                  "school_name": seed.get("school_name", ""), "basics": basics,
                                  "candidate_count": len(rows)})

        if depth >= args.depth:
            continue
        for anchor, href in links:
            nxt = urljoin(url, href).split("#")[0]
            if nxt in seen or registrable_domain(urlparse(nxt).netloc) != seed_dom:
                continue
            # 深度模式：红头文件多为 PDF/DOC 附件，公开页正文没有时从附件里抽
            if args.deep and attach_budget > 0 and adapter.is_attachment(href):
                if not pol.can_fetch(nxt):
                    continue
                pol.wait(nxt)
                raw = fetch_bytes(nxt, session, args.timeout, args.max_bytes * 4)
                attach_budget -= 1
                if not raw:
                    continue
                text = attachment_text(nxt, raw)
                if text and extract.page_is_relevant(text):
                    basics = extract.extract_basics(text, anchor or title)
                    rows = extract.extract_rules(text, nxt, seed.get("school_id", ""),
                                                 seed.get("school_name", ""), basics["notice_title"], basics["publish_date"])
                    if rows:
                        log.info("附件命中 %d 条候选 @ %s", len(rows), nxt)
                        candidates.extend(rows)
                        pages_out.append({"url": nxt, "school_id": seed.get("school_id", ""),
                                          "school_name": seed.get("school_name", ""), "basics": basics,
                                          "candidate_count": len(rows), "attachment": True})
                continue
            if adapter.should_follow(anchor, href):
                q.append((nxt, depth + 1))

    log.info("%s：抓 %d 页，候选 %d 条（适配器 %s%s）", seed["school_name"], fetched, len(candidates),
             adapter.name, "·deep" if args.deep else "")
    return candidates


def write_out(candidates: list[dict], out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with io.open(os.path.join(out_dir, "candidates.jsonl"), "w", encoding="utf-8") as f:
        for c in candidates:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    cols = ["school_id", "school_name", "degree_type", "metric", "limit_pct",
            "platform", "effective_year", "confidence", "source_url", "snippet"]
    with io.open(os.path.join(out_dir, "candidates.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for c in sorted(candidates, key=lambda x: (x["school_id"], -x["confidence"])):
            w.writerow({k: c.get(k, "") for k in cols})
    log.info("写出 %s/candidates.{jsonl,csv}（共 %d 条，均 status=pending 待人工审核）", out_dir, len(candidates))


def selftest() -> None:
    """离线端到端：把内置通知当一页喂给通用适配器，验证抽取链路。"""
    from adapters.base import GenericAdapter
    a = GenericAdapter()
    seed = {"school_id": "1", "school_name": "示例大学", "entry_url": "http://yjsy.example.edu.cn/"}
    title = "关于2026届研究生学位论文AIGC检测与学术不端检测的通知"
    assert a.should_follow("学位论文检测通知", "/yjsy/tzgg/2026.html")
    assert not a.should_follow("联系我们", "/about/contact.html")
    assert not a.should_follow("红头文件", "/upload/2026/aigc.pdf"), "附件不走 html 跟进"
    assert a.is_attachment("/upload/2026/aigc.pdf") and a.is_attachment("/f/x.docx")
    a.deep = True
    assert a.should_follow("2", "/tzgg/index_2.html"), "deep 跟进翻页"
    assert a.should_follow("", "https://gs.example.edu.cn/"), "deep 跟进研究生院子站"
    a.deep = False
    bz = extract.extract_basics("西北工业大学关于2026届研究生学位论文检测的通知 发布日期：2026-03-15 全日制硕士，知网检测，共2次检测机会，免费",
                                "关于2026届研究生学位论文检测的通知")
    assert bz["publish_date"] == "2026-03-15" and bz["platform"] == "cnki" and bz["detect_rounds"] == "2" and bz["free"], bz
    assert a.page_relevant(title, extract.SELFTEST_HTML)
    rows = a.extract(title, extract.SELFTEST_HTML, "http://yjsy.example.edu.cn/tzgg/2026.html", seed)
    assert len(rows) == 6, f"应抽到 6 条，实际 {len(rows)}"
    assert registrable_domain("yjsy.pku.edu.cn") == "pku.edu.cn"
    assert registrable_domain("www.tsinghua.edu.cn") == "tsinghua.edu.cn"
    print(f"spider selftest ok：适配器=generic，抽到 {len(rows)} 条候选")
    extract._selftest()


def main() -> None:
    ap = argparse.ArgumentParser(description="highschool-spider：高校公开页学位论文红线爬虫（礼貌版）")
    ap.add_argument("--seeds", help="seeds csv：school_id,school_name,entry_url[,note]")
    ap.add_argument("--out", default="out")
    ap.add_argument("--delay", type=float, default=4.0, help="每域最小请求间隔秒（robots Crawl-delay 更大时从其）")
    ap.add_argument("--depth", type=int, default=2, help="从入口页起最大跟进深度")
    ap.add_argument("--max-pages", type=int, default=50, help="每校最多抓取页数")
    ap.add_argument("--max-attachments", type=int, default=20, help="每校最多解析的 PDF/DOC 附件数（deep）")
    ap.add_argument("--timeout", type=int, default=15)
    ap.add_argument("--max-bytes", type=int, default=2_000_000)
    ap.add_argument("--cache-dir", default="", help="缓存抓到的 HTML，便于离线调抽取规则")
    ap.add_argument("--deep", action="store_true",
                    help="深挖：跟进翻页与研究生院/教务处子站，解析 PDF/DOC 附件正文；仍遵守 robots 与限速")
    ap.add_argument("--dry-run", action="store_true", help="只打印将访问的入口，不发真实请求")
    ap.add_argument("--selftest", action="store_true", help="离线自测，不联网")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return
    if not args.seeds:
        ap.error("需要 --seeds 或 --selftest")
    if args.deep:  # 深挖默认把深度与页数上调，用户显式给了就不覆盖
        if args.depth == 2:
            args.depth = 4
        if args.max_pages == 50:
            args.max_pages = 150

    seeds = load_seeds(args.seeds)
    log.info("载入 %d 所学校，每域限速 %.1fs，深度 %d，每校上限 %d 页%s",
             len(seeds), args.delay, args.depth, args.max_pages, "，deep 附件解析" if args.deep else "")
    session = requests.Session()
    pol = Politeness(args.delay, session)
    all_cand: list[dict] = []
    pages_out: list[dict] = []
    for seed in seeds:
        try:
            all_cand.extend(crawl_seed(seed, pol, session, args, pages_out))
        except Exception as e:
            log.exception("%s 爬取出错：%s", seed.get("school_name"), e)
    if not args.dry_run:
        write_out(all_cand, args.out)
        if pages_out:
            os.makedirs(args.out, exist_ok=True)
            with io.open(os.path.join(args.out, "pages.jsonl"), "w", encoding="utf-8") as f:
                for p in pages_out:
                    f.write(json.dumps(p, ensure_ascii=False) + "\n")
            log.info("写出 %s/pages.jsonl（%d 页基本信息）", args.out, len(pages_out))


if __name__ == "__main__":
    main()
