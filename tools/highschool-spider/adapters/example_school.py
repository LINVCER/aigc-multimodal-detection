"""
单校适配器模板 —— 复制本文件改名即可（如 nwpu.py / pku.py）
========================================================

操作流程（每新增一所学校走一遍）：
  1. 人工去该校研究生院/教务处网站确认：学位论文检测通知在哪个栏目、是正文给数字还是附件红头文件、用什么检测平台；
  2. 复制本文件为 <school>.py，改 name / match / seed_urls / should_follow，必要时覆盖 extract；
  3. 在 adapters/__init__.py 的 _REGISTRY 里 import 并 append 本适配器；
  4. 用 seeds.csv（该校一行）跑 spider.py 验证，候选 OK 再提交到爬取器批量/按需跑。

不覆盖的部分自动走 GenericAdapter 的关键词逻辑，所以通常只需定几个点。
"""
from __future__ import annotations

from urllib.parse import urlparse

from adapters.base import SiteAdapter


class ExampleSchoolAdapter(SiteAdapter):
    name = "example_school"

    # 命中本校域名时启用本适配器（registrable domain 判断在注册表外层已按 host 匹配）
    def match(self, host: str, seed: dict) -> bool:
        return host.endswith("example.edu.cn")

    # 已确认的入口：直接给「通知公告」栏目列表页，比从首页瞎逛高效得多；可给多个
    def seed_urls(self, seed: dict) -> list[str]:
        return [
            "http://gs.example.edu.cn/cn/tzgg.htm",        # 研究生院通知公告列表
            "http://gs.example.edu.cn/cn/ssyjs/ssxwsqd.htm",  # 硕士学位申请/答辩/检测专栏
        ]

    # 只在确认过的栏目路径内跟进 + 附件；比通用关键词更准、更省
    def should_follow(self, anchor: str, href: str) -> bool:
        low = (anchor + " " + href).lower()
        path = urlparse(href).path.lower()
        if self.is_attachment(href):
            return False  # 附件走 is_attachment（spider deep 模式单独抓）
        if "/info/" in path or "tzgg" in path or "ssxwsqd" in path:
            return True
        return any(k in low for k in ["检测", "查重", "学术不端", "aigc", "学位论文"])

    # 若该校正文/附件结构特殊（例如数字在表格、或正文要先定位某容器），在此覆盖 extract；
    # 一般不用覆盖，交给 base + extract.extract_rules 的通用抽取即可。
    # def extract(self, title, body, url, seed):
    #     return super().extract(title, body, url, seed)
