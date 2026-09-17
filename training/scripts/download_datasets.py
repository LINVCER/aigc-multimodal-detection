"""
下载中文 AIGC 检测公开数据集到 training/data/，并登记 DVC。

数据集：
  HC3-Chinese : Hello-SimpleAI/HC3-Chinese (HuggingFace)  24.3K 问答对
  CHEAT       : ChatGPT 学术摘要 35K（GitHub release，需手动确认最新地址）
  M4          : 多生成器多语言（GitHub，溯源训练用）

用法：
  python download_datasets.py                # 下载全部
  python download_datasets.py --only hc3     # 只下 HC3-Chinese
"""

import argparse
import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def download_hc3_chinese() -> None:
    """下载 HC3-Chinese 并转换为统一 jsonl 格式（text/label/source/domain）"""
    from datasets import load_dataset

    out_dir = DATA_DIR / "hc3-chinese"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("下载 HC3-Chinese ...")
    ds = load_dataset("Hello-SimpleAI/HC3-Chinese", "all")

    n_human, n_ai = 0, 0
    with open(out_dir / "train.jsonl", "w", encoding="utf-8") as f:
        for row in ds["train"]:
            domain = row.get("source", "unknown")
            for answer in row.get("human_answers") or []:
                if len(answer) > 20:
                    f.write(json.dumps({
                        "text": answer, "label": 0,
                        "source": "human", "domain": domain,
                    }, ensure_ascii=False) + "\n")
                    n_human += 1
            for answer in row.get("chatgpt_answers") or []:
                if len(answer) > 20:
                    f.write(json.dumps({
                        "text": answer, "label": 1,
                        "source": "gpt", "domain": domain,
                    }, ensure_ascii=False) + "\n")
                    n_ai += 1

    print(f"HC3-Chinese 完成: {n_human} human + {n_ai} ai -> {out_dir/'train.jsonl'}")


def download_m4() -> None:
    """M4 多生成器数据（溯源训练用），走 HuggingFace 镜像"""
    from datasets import load_dataset

    out_dir = DATA_DIR / "m4"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("下载 M4 (中文子集) ...")
    try:
        ds = load_dataset("mbzuai-nlp/M4", split="train", streaming=True)
        count = 0
        with open(out_dir / "train.jsonl", "w", encoding="utf-8") as f:
            for row in ds:
                if row.get("language") not in ("zh", "chinese", "Chinese"):
                    continue
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += 1
                if count >= 100_000:
                    break
        print(f"M4 中文子集完成: {count} 条 -> {out_dir/'train.jsonl'}")
    except Exception as e:
        print(f"M4 下载失败（数据集 ID 可能已变更，请到 HF 搜索 'M4 machine-generated'）: {e}")


def print_cheat_notice() -> None:
    # CHEAT 数据集托管在 GitHub，license 要求逐项确认，不做自动下载
    out_dir = DATA_DIR / "cheat"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(
        "CHEAT 数据集需手动获取:\n"
        "  1. 访问 https://github.com/botianzhe/CHEAT 确认 license\n"
        f"  2. 下载后放到 {out_dir}/\n"
        "  3. 运行 dvc add training/data/cheat 登记版本"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=["hc3", "m4", "cheat"], default=None)
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.only in (None, "hc3"):
        download_hc3_chinese()
    if args.only in (None, "m4"):
        download_m4()
    if args.only in (None, "cheat"):
        print_cheat_notice()

    print("\n登记 DVC:")
    print("  dvc add training/data && dvc push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
