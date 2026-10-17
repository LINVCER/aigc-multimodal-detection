"""
公开数据集预拉 / 缓存
=====================

CSL / HC3-Chinese / M4-zh 的摄入已内置 `build_dataset.py`（直接从 HF 读）。本脚本只做：
  1. 预先把这些 HF 数据集拉到本地 cache，避免首次 build 时阻塞；
  2. 打印 CHEAT 等需手动下载的数据集的获取说明（CHEAT 只进 test，见 DATASETS.md）。

用法::

    python -m ml.datasets.text.download_datasets --only csl,hc3,m4
    python -m ml.datasets.text.download_datasets --selftest     # 不联网，只校验目标清单
"""
from __future__ import annotations

import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s")
log = logging.getLogger("download_datasets")

# name → (HF repo, load_dataset kwargs)；与 build_dataset.py 的 _hf_load 口径一致
HF_TARGETS: dict[str, tuple[str, dict]] = {
    "csl": ("neuclir/csl", {"split": "csl"}),
    "hc3": ("Hello-SimpleAI/HC3-Chinese", {"name": "all"}),
    "m4": ("mbzuai-nlp/M4", {"split": "train", "streaming": False}),
}
# 需手动获取的
MANUAL = {
    "cheat": "CHEAT（论文摘要 AI/human）需按原仓库说明申请下载，放 ml/datasets/text/raw/cheat/，"
             "再 `build_dataset --sources cheat --cheat-dir ...`；只进 test。",
}


def run(only: list[str] | None) -> None:
    targets = {k: v for k, v in HF_TARGETS.items() if not only or k in only}
    try:
        from datasets import load_dataset
    except Exception as e:
        log.error("datasets 库不可用（pip install datasets）：%s", e)
        return
    for name, (repo, kw) in targets.items():
        try:
            log.info("预拉 %s（%s）…", name, repo)
            load_dataset(repo, **kw)
            log.info("  %s 已缓存", name)
        except Exception as e:
            log.warning("  %s 拉取失败：%s", name, e)
    for name, note in MANUAL.items():
        if not only or name in only:
            log.info("手动获取 · %s：%s", name, note)


def _selftest() -> None:
    assert set(HF_TARGETS) == {"csl", "hc3", "m4"}
    assert "cheat" in MANUAL
    # --only 过滤逻辑
    only = ["csl"]
    picked = {k for k in HF_TARGETS if not only or k in only}
    assert picked == {"csl"}
    print("download_datasets selftest ok：目标清单与过滤正确（未联网）")


def main() -> None:
    ap = argparse.ArgumentParser(description="公开数据集预拉 / 缓存")
    ap.add_argument("--only", help="逗号分隔：csl,hc3,m4,cheat")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        _selftest()
    else:
        run([x.strip() for x in a.only.split(",")] if a.only else None)


if __name__ == "__main__":
    main()
