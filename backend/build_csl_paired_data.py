"""
CSL 配对论文数据构建

策略: 拿 CSL 中的人类论文标题, 让 DeepSeek 生成 AI 版本摘要,
     形成同主题/不同风格的配对训练数据。

数据流:
  人类论文 (CSL) ──标题──→ DeepSeek ──生成──→ AI 版摘要
       ↓                                        ↓
   label=0 (human)                        label=1 (AI)
       ↓                                        ↓
           配对训练数据 (同标题, 同领域, 不同写作风格)

输出:
  aigc_csl_paired_train.json
  aigc_csl_paired_val.json
"""

import os, sys, json, time, random, csv, argparse
from pathlib import Path
from collections import defaultdict

random.seed(42)

DATA_DIR = Path("../data")
CSL_DIR = DATA_DIR / "CSL/benchmark"
TRAINING_DIR = DATA_DIR / "training"

API_KEY = os.getenv("LLM_API_KEY", "")
API_BASE = os.getenv("LLM_API_BASE", "")
API_MODEL = os.getenv("LLM_MODEL", "")

if not API_KEY:
    claude_path = os.path.expanduser("~/.claude/settings.json")
    if os.path.exists(claude_path):
        try:
            with open(claude_path, "r", encoding="utf-8") as f:
                cs = json.load(f)
            env = cs.get("env", {})
            API_KEY = env.get("ANTHROPIC_AUTH_TOKEN", "")
            raw_base = env.get("ANTHROPIC_BASE_URL", "")
            if "deepseek.com/anthropic" in raw_base:
                API_BASE = raw_base.replace("/anthropic", "/v1")
        except Exception:
            pass

API_KEY = API_KEY or os.getenv("LLM_API_KEY", "")
API_BASE = API_BASE or "https://api.deepseek.com/v1"
API_MODEL = API_MODEL or "deepseek-chat"

# ============================================================
# 加载 CSL 数据
# ============================================================

def load_csl_tsv(task: str) -> list[dict]:
    """加载 CSL benchmark TSV 文件, 提取标题+摘要

    CSL text2text 格式:
      column 0: 任务提示 (e.g. "to title")
      column 1: 摘要 (abstract) — 人类撰写的学术文本
      column 2: 标题 (title)
    """
    samples = []
    for split in ["train", "dev", "test"]:
        path = CSL_DIR / task / f"{split}.tsv"
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f, delimiter="\t")
            header = next(reader)  # skip header row
            for row in reader:
                if len(row) < 3:
                    continue
                abstract = row[1].strip()
                title = row[2].strip()
                if len(abstract) >= 50 and len(title) >= 5:
                    samples.append({
                        "title": title,
                        "abstract": abstract,
                        "source_split": split,
                        "domain": "csl",
                    })
    return samples


def load_csl_with_discipline(task: str = "cls_dcp") -> list[dict]:
    """加载 CSL 学科分类数据, 获取领域标签"""
    samples = []
    for split in ["train", "dev", "test"]:
        path = CSL_DIR / task / f"{split}.tsv"
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f, delimiter="\t")
            header = next(reader)
            for row in reader:
                if len(row) < 3:
                    continue
                discipline = row[2].strip()  # 学科
                abstract = row[1].strip()
                if len(abstract) >= 50:
                    samples.append({
                        "discipline": discipline,
                        "abstract": abstract,
                        "domain": "csl",
                    })
    return samples


# ============================================================
# AI 生成配对样本
# ============================================================

def _get_client():
    import httpx, os
    from openai import OpenAI
    # 强制清除代理环境变量，避免被系统代理拦截
    for key in list(os.environ.keys()):
        if key.upper() in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
            os.environ.pop(key, None)
    return OpenAI(
        api_key=API_KEY,
        base_url=API_BASE,
        http_client=httpx.Client(proxy=None, timeout=60.0),
    )


# 学科 → 生成风格指导
DISCIPLINE_STYLES = {
    "工程": "使用规范的工程技术语言，包含具体的技术参数和实验数据",
    "科学": "使用严谨的科学论述风格，包含理论推导和实验验证",
    "医学": "使用医学专业术语，包含临床数据和病例分析",
    "管理": "使用管理学分析框架，包含案例研究和数据论证",
    "经济": "使用经济学理论术语，包含计量分析和政策建议",
    "法学": "使用法律条文引用和法理分析",
    "教育": "使用教育学理论框架，包含教学实践案例",
    "文学": "使用文学批评理论，包含文本分析和文化阐释",
    "哲学": "使用哲学概念辨析和逻辑论证",
    "农学": "使用农业科学技术语言，包含实验数据和田间试验",
}


def generate_ai_abstract(client, title: str, domain: str = "csl",
                         discipline: str = "") -> str | None:
    """用论文标题生成 AI 版本的摘要"""
    style = DISCIPLINE_STYLES.get(discipline, "使用规范的学术论文写作风格")
    prompt = (
        f"请撰写一段学术论文摘要（200-400字），论文标题为「{title}」。\n"
        f"要求：\n"
        f"1. {style}\n"
        f"2. 包含研究背景、方法、主要发现和结论\n"
        f"3. 只输出摘要内容，不要包含标题\n"
        f"4. 使用客观、学术化的语言"
    )
    try:
        response = client.chat.completions.create(
            model=API_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.7,
            timeout=30,
        )
        text = response.choices[0].message.content.strip()
        # 过滤明显失败
        if len(text) < 80 or "无法" in text[:50] or "抱歉" in text[:50]:
            return None
        return text[:2000]
    except Exception as e:
        print(f"    API error: {e}")
        return None


# ============================================================
# 主流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="CSL 配对论文数据构建")
    parser.add_argument("--max_pairs", type=int, default=5000,
                        help="最大生成配对数 (默认 5000)")
    parser.add_argument("--batch_size", type=int, default=10,
                        help="每批 API 调用数 (用于速率控制)")
    parser.add_argument("--skip_api", action="store_true",
                        help="跳过 API 生成，仅输出人类样本")
    parser.add_argument("--discipline_file", type=str, default=None,
                        help="学科分类文件以添加领域标签")
    args = parser.parse_args()

    print("=" * 60)
    print("CSL 配对论文数据构建")
    print("=" * 60)

    # Step 1: 加载人类论文
    print("\n[1/3] 加载 CSL 人类论文...")
    ts_samples = load_csl_tsv("ts")
    print(f"  TS (摘要): {len(ts_samples)} samples")

    # 尝试加载学科信息
    discipline_samples = {}
    for task in ["cls_dcp", "cls_ctg"]:
        if (CSL_DIR / task).exists():
            dcp = load_csl_with_discipline(task)
            print(f"  {task}: {len(dcp)} discipline samples")
            for s in dcp:
                key = s["abstract"][:30]
                discipline_samples[key] = s["discipline"]

    # 匹配标题-摘要对, 附带学科信息
    human_samples = []
    discipline_dist = defaultdict(int)
    for s in ts_samples:
        disc = discipline_samples.get(s["abstract"][:30], "")
        human_samples.append({
            "domain": "csl",
            "text": s["abstract"][:1500],
            "label": 0,  # 人类撰写
            "title": s["title"],
            "discipline": disc,
            "subtype": "csl_human",
        })
        discipline_dist[disc] += 1

    print(f"  有效人类样本: {len(human_samples)}")
    if discipline_dist:
        print(f"  学科分布: {dict(discipline_dist)}")

    # Step 2: API 生成 AI 配对
    num_pairs = min(args.max_pairs, len(human_samples))
    ai_samples = []

    if not args.skip_api:
        print(f"\n[2/3] API 生成 AI 配对摘要 ({num_pairs} pairs)...")
        client = _get_client()

        selected = random.sample(human_samples, num_pairs)
        generated = 0
        batch_errors = 0

        for i, hs in enumerate(selected):
            disc = hs.get("discipline", "")
            ai_text = generate_ai_abstract(
                client, hs["title"], domain="csl", discipline=disc
            )
            if ai_text:
                ai_samples.append({
                    "domain": "csl",
                    "text": ai_text,
                    "label": 1,  # AI 生成
                    "title": hs["title"],
                    "discipline": disc,
                    "subtype": "csl_ai_paired",
                })
                generated += 1
                if (generated) % 10 == 0:
                    print(f"    {generated}/{num_pairs} generated...")
            else:
                batch_errors += 1

            # 速率控制
            time.sleep(0.3)
            if batch_errors > 10:
                print(f"    连续错误过多，跳过剩余")
                break

        print(f"  成功生成: {generated} AI samples")

    # Step 3: 合并+分割+保存
    print("\n[3/3] 合并并保存...")
    all_samples = human_samples + ai_samples
    random.shuffle(all_samples)

    # 80/20 split
    split_idx = int(len(all_samples) * 0.8)
    train = all_samples[:split_idx]
    val = all_samples[split_idx:]

    # 统计
    train_ai = sum(1 for s in train if s["label"] == 1)
    train_human = sum(1 for s in train if s["label"] == 0)
    val_ai = sum(1 for s in val if s["label"] == 1)
    val_human = sum(1 for s in val if s["label"] == 0)

    print(f"  Train: {len(train)} ({train_human} human + {train_ai} AI)")
    print(f"  Val:   {len(val)} ({val_human} human + {val_ai} AI)")

    TRAINING_DIR.mkdir(parents=True, exist_ok=True)
    train_path = TRAINING_DIR / "aigc_csl_paired_train.json"
    val_path = TRAINING_DIR / "aigc_csl_paired_val.json"

    with open(train_path, "w", encoding="utf-8") as f:
        json.dump(train, f, ensure_ascii=False)
    with open(val_path, "w", encoding="utf-8") as f:
        json.dump(val, f, ensure_ascii=False)

    print(f"\n  训练集: {train_path}")
    print(f"  验证集: {val_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()
