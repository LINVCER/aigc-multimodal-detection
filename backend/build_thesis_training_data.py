"""
论文 AIGC 检测专项数据构建

在 aigc_diverse_train/val 基础上增强论文检测能力:
  1. 长章节文本 (3000+ 字) — 论文不是 512 token 片段
  2. AI→人工混合文本 — 模拟真实论文场景
  3. 引用密集段落 — 防止引用被误判
  4. 跨学科学术语料 — 医/法/金融/CS
  5. 论文 slop 词变体 — AI 论文常见套话

用法:
  python build_thesis_training_data.py                    # 完整构建
  python build_thesis_training_data.py --skip_api         # 仅本地数据
"""

import os, sys, json, time, random, re, argparse
from pathlib import Path
from collections import Counter

random.seed(42)

DATA_DIR = Path("../data")
TRAINING_DIR = DATA_DIR / "training"
BASE_TRAIN = TRAINING_DIR / "aigc_diverse_train.json"
BASE_VAL = TRAINING_DIR / "aigc_diverse_val.json"
OUTPUT_TRAIN = TRAINING_DIR / "aigc_thesis_train.json"
OUTPUT_VAL = TRAINING_DIR / "aigc_thesis_val.json"

# 论文相关领域
THESIS_DOMAINS = {"csl", "asap", "nlpcc2025", "psychology", "medicine", "law", "finance"}
NON_THESIS_DOMAINS = {"cudrt", "qa", "cnewsum", "baike"}

# API 配置
def _load_api_config():
    api_key = os.getenv("LLM_API_KEY", "")
    api_base = os.getenv("LLM_API_BASE", "")
    api_model = os.getenv("LLM_MODEL", "")
    if not api_key:
        claude_path = os.path.expanduser("~/.claude/settings.json")
        if os.path.exists(claude_path):
            try:
                with open(claude_path, "r", encoding="utf-8") as f:
                    cs = json.load(f)
                env = cs.get("env", {})
                api_key = env.get("ANTHROPIC_AUTH_TOKEN", api_key)
                raw_base = env.get("ANTHROPIC_BASE_URL", "")
                if "deepseek.com/anthropic" in raw_base:
                    api_base = raw_base.replace("/anthropic", "/v1")
            except Exception:
                pass
    api_key = api_key or os.getenv("LLM_API_KEY", "")
    api_base = api_base or "https://api.deepseek.com/v1"
    api_model = api_model or "deepseek-chat"
    return api_key, api_base, api_model

API_KEY, API_BASE, API_MODEL = _load_api_config()

# ============================================================
# 论文 AI 生成模板 — 按章节类型
# ============================================================

THESIS_TEMPLATES = {
    "introduction": {
        "prompt": "请撰写一段学术论文的引言部分（800-1500字），主题为「{}」。使用规范的学术语言，包含研究背景、问题陈述和研究意义。",
        "domain_keywords": {
            "medicine": ["深度学习在医学影像诊断中的应用", "基于机器学习的疾病预测模型研究", "人工智能辅助药物发现"],
            "finance": ["基于深度学习的股价预测模型研究", "金融风险智能预警系统", "量化交易策略优化"],
            "law": ["人工智能在司法判决预测中的应用", "数据隐私保护法律框架研究", "智能合约法律效力分析"],
            "psychology": ["基于大语言模型的心理健康评估", "社交媒体情感分析研究", "认知行为治疗的数字化应用"],
            "csl": ["基于Transformer的文本生成方法研究", "知识图谱增强的问答系统", "多模态信息抽取技术综述"],
        },
    },
    "literature_review": {
        "prompt": "请撰写一段学术论文的文献综述部分（800-1200字），主题为「{}」。梳理相关研究进展，指出研究空白。使用学术引用格式 [1] [2-3]。",
        "domain_keywords": {
            "medicine": ["医学图像分割技术", "电子病历自然语言处理", "基因组学数据分析"],
            "finance": ["金融市场预测模型", "信用风险评估方法", "高频交易策略"],
            "law": ["法律文本信息抽取", "司法大数据分析", "网络空间治理"],
            "psychology": ["心理测量与评估方法", "心理咨询技术发展", "认知神经科学研究"],
            "csl": ["预训练语言模型发展", "信息检索技术演进", "对话系统研究综述"],
        },
    },
    "methodology": {
        "prompt": "请撰写一段学术论文的研究方法部分（600-1000字），主题为「{}」。描述实验设计、数据集、评估指标和技术路线。",
        "domain_keywords": {
            "medicine": ["临床数据采集方法", "影像预处理流程", "模型评估指标体系"],
            "finance": ["时间序列分析方法", "特征工程流程", "回测框架设计"],
            "law": ["法律文本标注方案", "案件匹配算法设计", "评估指标体系"],
            "psychology": ["问卷调查设计方法", "实验组对照组设置", "统计分析方案"],
            "csl": ["数据集构建方法", "对比实验设计", "消融实验方案"],
        },
    },
    "conclusion": {
        "prompt": "请撰写一段学术论文的结论部分（500-800字），主题为「{}」。总结研究发现，指出局限性，展望未来方向。",
        "domain_keywords": {
            "medicine": ["诊断模型临床价值", "研究局限性分析", "精准医疗未来展望"],
            "finance": ["预测模型应用前景", "风控体系改进方向", "监管科技发展"],
            "law": ["司法智能化路径", "法律科技发展建议", "隐私保护机制"],
            "psychology": ["心理健康服务优化", "研究推广价值", "跨文化验证需求"],
            "csl": ["技术贡献总结", "方法局限性反思", "未来研究方向"],
        },
    },
}

# 学术 slop 词 — AI 论文高频套话
ACADEMIC_SLOP = [
    "值得注意的是", "进一步来说", "总而言之", "从某种意义上讲",
    "不可否认的是", "需要强调的是", "研究表明", "数据显示",
    "首先，其次，最后", "不仅...而且...", "一方面...另一方面...",
    "在一定程度上", "具有重要的理论意义和实践价值",
    "为...提供了新的思路", "推动了...的发展",
    "本文旨在", "本研究的创新点在于", "本文的研究贡献包括",
]

# 论文引用模板
CITATION_TEMPLATES = [
    "如文献[{}]所述，该方法的有效性已得到充分验证。",
    "已有研究[{}]指出，传统方法在处理此类问题时存在局限。",
    "参考[{}]的工作，我们采用了改进的评估策略。",
    "相关研究[{}]表明，该领域仍有较大的探索空间。",
    "与[{}]的方法相比，本文提出的方案在效率上有明显提升。",
]


# ============================================================
# Part 1: 本地数据增强 (不需要 API)
# ============================================================

def load_base_data() -> tuple[list[dict], list[dict]]:
    """加载基础数据集"""
    with open(BASE_TRAIN, "r", encoding="utf-8") as f:
        train = json.load(f)
    with open(BASE_VAL, "r", encoding="utf-8") as f:
        val = json.load(f)
    return train, val


def oversample_thesis_domains(samples: list[dict], ai_ratio: float = 4.0) -> list[dict]:
    """对论文领域 AI 样本过采样，修复 human:AI 失衡 (目标 1:1)"""
    thesis = [s for s in samples if s["domain"] in THESIS_DOMAINS]
    non_thesis = [s for s in samples if s["domain"] not in THESIS_DOMAINS]

    thesis_ai = [s for s in thesis if s["label"] == 1]
    thesis_human = [s for s in thesis if s["label"] == 0]

    # 计算需要多少倍过采样才能接近 1:1
    # target: AI / (AI + human) ≈ 0.5
    target_ai = len(thesis_human)  # 目标: AI 数量 = human 数量
    needed_ratio = target_ai / max(len(thesis_ai), 1)
    actual_ratio = min(needed_ratio, ai_ratio)  # 不超过上限

    print(f"  论文领域原始: {len(thesis)} ({len(thesis_human)} human, {len(thesis_ai)} AI, ratio={len(thesis_human)/max(len(thesis_ai),1):.1f}:1)")
    print(f"  非论文领域: {len(non_thesis)}")

    # 对 AI 样本过采样以接近 1:1
    oversampled = thesis_ai * int(actual_ratio)
    oversampled = oversampled[:target_ai - len(thesis_ai)]  # 精确补齐

    result = non_thesis + thesis + oversampled
    final_ai = len(thesis_ai) + len(oversampled)
    print(f"  过采样后: {len(result)} (论文 AI: {len(thesis_ai)} → {final_ai}, ratio={len(thesis_human)/max(final_ai,1):.1f}:1)")
    return result


def generate_mixed_samples(thesis_samples: list[dict], num: int = 2000) -> list[dict]:
    """生成混合文本：模拟 AI 生成 → 人工修改的场景"""
    import random as rnd
    mixed = []
    ai_samples = [s for s in thesis_samples if s["label"] == 1]

    for _ in range(min(num, len(ai_samples) * 2)):
        ai = rnd.choice(ai_samples)
        text = ai["text"]

        # 模拟人工修改: 随机删除 slop 词、调整句式、加入口语化表达
        modified = text
        # 删除随机 slop 词
        for slop in rnd.sample(ACADEMIC_SLOP, min(2, len(ACADEMIC_SLOP))):
            modified = modified.replace(slop, "")
        # 长句拆分
        modified = re.sub(r"([。；])(?=[^。；\n]{60,})", r"\1\n", modified)
        # 确保不低于 30 字符
        if len(modified) >= 30 and modified != text:
            mixed.append({
                "domain": ai["domain"],
                "text": modified.strip()[:2000],
                "label": 1,  # 仍然是 AI 文本（修改后）
                "subtype": "ai_edited",
            })

    rnd.shuffle(mixed)
    print(f"  混合文本生成: {len(mixed)} samples")
    return mixed


def generate_citation_samples(num: int = 1500) -> list[dict]:
    """生成引用密集段落 — 人类论文特征"""
    import random as rnd
    samples = []

    citation_patterns = [
        "根据文献[{n}]的研究，{content}。实验结果表明，该方法在{metric}上达到了{value}的性能。",
        "对比{methods}等[{refs}]方法，本文提出的方案在{aspect}方面具有明显优势。具体而言，{content}。",
        "近年来，{topic}领域的研究取得了显著进展[{n1}-{n2}]。然而，现有方法在{limitation}方面仍存在不足。",
        "如{topic}领域的研究[{n}]所示，改进后的模型在性能上有明显提升。具体而言，{content}。",
    ]

    topics = [
        "自然语言处理", "计算机视觉", "知识图谱", "推荐系统",
        "异常检测", "时间序列预测", "图神经网络", "迁移学习",
        "联邦学习", "对抗训练", "自监督学习", "多模态融合",
    ]

    for _ in range(num):
        pattern = rnd.choice(citation_patterns)
        n = rnd.randint(1, 50)
        n1, n2 = sorted([rnd.randint(1, 30), rnd.randint(31, 60)])
        refs = ",".join(str(rnd.randint(1, 60)) for _ in range(rnd.randint(2, 5)))

        text = pattern.format(
            n=n, n1=n1, n2=n2, refs=refs,
            content="通过系统性的实验对比分析，我们验证了所提出方法的有效性",
            metric="F1-score",
            value=f"{rnd.uniform(85, 98):.2f}%",
            methods="、".join(rnd.sample(["BERT", "RoBERTa", "GPT", "T5", "BART"], 2)),
            aspect="准确率和效率",
            topic=rnd.choice(topics),
            limitation="泛化能力和计算效率",
        )

        # 扩展文本使其更自然
        preamble = "本研究" if rnd.random() > 0.5 else "本文"
        text = f"{preamble}{text}"

        if len(text) >= 30:
            samples.append({
                "domain": "csl",
                "text": text[:1500],
                "label": 0,  # 引用密集 = 人类特征
                "subtype": "citation_heavy",
            })

    rnd.shuffle(samples)
    print(f"  引用段落生成: {len(samples)} samples")
    return samples


# ============================================================
# Part 2: API 生成论文数据
# ============================================================

def _get_client():
    import httpx, os
    from openai import OpenAI
    for key in list(os.environ.keys()):
        if key.upper() in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
            os.environ.pop(key, None)
    return OpenAI(
        api_key=API_KEY,
        base_url=API_BASE,
        http_client=httpx.Client(proxy=None, timeout=60.0),
    )


def generate_long_thesis_chapters(client, target_count: int = 300) -> list[dict]:
    """通过 API 生成长章节论文文本 (>800 字)"""
    samples = []
    generated = 0

    for chapter_type, config in THESIS_TEMPLATES.items():
        print(f"  生成 {chapter_type} 章节...")
        prompt_template = config["prompt"]
        for domain, keywords in config["domain_keywords"].items():
            for keyword in keywords:
                if generated >= target_count:
                    break
                try:
                    prompt = prompt_template.format(keyword)
                    response = client.chat.completions.create(
                        model=API_MODEL,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=1500,
                        temperature=0.8,
                        timeout=30,
                    )
                    text = response.choices[0].message.content.strip()
                    if len(text) >= 200:
                        samples.append({
                            "domain": domain,
                            "text": text[:3000],
                            "label": 1,
                            "subtype": f"ai_thesis_{chapter_type}",
                        })
                        generated += 1
                        print(f"    ✓ {domain}/{chapter_type}: {len(text)} chars")
                except Exception as e:
                    print(f"    ✗ {domain}/{chapter_type}: {e}")
                    time.sleep(2)

                if generated >= target_count:
                    break
            if generated >= target_count:
                break

    print(f"  长章节生成: {len(samples)} samples")
    return samples


def generate_slop_variants(num: int = 500) -> list[dict]:
    """生成 slop 词密集文本 — 训练模型识别 AI 套话"""
    import random as rnd
    samples = []

    for _ in range(num):
        slops = rnd.sample(ACADEMIC_SLOP, rnd.randint(2, 5))
        # 构建 slop 密集型段落
        parts = []
        for slop in slops:
            continuation = rnd.choice([
                "深度学习技术在多个领域的应用不断深化",
                "人工智能的发展为传统行业带来了新的机遇",
                "基于大数据的分析方法逐渐成为主流",
                "相关技术的发展推动了研究范式的转变",
                "新型算法的提出为解决复杂问题提供了可能",
            ])
            parts.append(f"{slop}，{continuation}。")
        text = "".join(parts)
        samples.append({
            "domain": "csl",
            "text": text[:1500],
            "label": 1,
            "subtype": "slop_dense",
        })

    rnd.shuffle(samples)
    print(f"  Slop 变体生成: {len(samples)} samples")
    return samples


# ============================================================
# Part 3: 主构建流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="论文 AIGC 检测专项数据构建")
    parser.add_argument("--skip_api", action="store_true", help="跳过 API 生成")
    parser.add_argument("--api_samples", type=int, default=300, help="API 生成样本数")
    args = parser.parse_args()

    print("=" * 60)
    print("论文 AIGC 检测数据构建")
    print("=" * 60)

    # Step 1: 加载基础数据
    print("\n[1/5] 加载基础数据...")
    train, val = load_base_data()
    print(f"  Train: {len(train)} | Val: {len(val)}")

    # 论文领域 vs 非论文
    train_thesis = [s for s in train if s["domain"] in THESIS_DOMAINS]
    train_ai = [s for s in train_thesis if s["label"] == 1]
    train_human = [s for s in train_thesis if s["label"] == 0]
    print(f"  论文领域: {len(train_thesis)} (AI={len(train_ai)}, Human={len(train_human)})")

    val_thesis = [s for s in val if s["domain"] in THESIS_DOMAINS]
    val_ai = [s for s in val_thesis if s["label"] == 1]
    val_human = [s for s in val_thesis if s["label"] == 0]
    print(f"  验证-论文: {len(val_thesis)} (AI={len(val_ai)}, Human={len(val_human)})")

    # Step 2: 本地增强
    print("\n[2/5] 本地数据增强...")
    # 混合文本
    mixed_train = generate_mixed_samples(train_thesis, 2000)
    mixed_val = generate_mixed_samples(val_thesis, 400)
    # 引用段落
    cite_train = generate_citation_samples(1500)
    cite_val = generate_citation_samples(300)
    # Slop 变体
    slop_variants = generate_slop_variants(500)

    # 保持自然比例 (~1.7:1 AI:Human)，不做过度过采样
    train_aug = train + mixed_train + cite_train + slop_variants
    # 统计最终分布
    final_thesis = [s for s in train_aug if s["domain"] in THESIS_DOMAINS]
    final_ai = sum(1 for s in final_thesis if s["label"] == 1)
    final_human = sum(1 for s in final_thesis if s["label"] == 0)
    print(f"  论文领域最终: AI={final_ai}, Human={final_human}, ratio={final_ai/max(final_human,1):.1f}:1")

    val_aug = val + mixed_val + cite_val

    # Step 3: API 生成 (可选)
    api_samples = []
    if not args.skip_api:
        print(f"\n[3/5] API 生成论文章节 ({args.api_samples} target)...")
        client = _get_client()
        api_samples = generate_long_thesis_chapters(client, args.api_samples)
        train_aug = train_aug + api_samples
        print(f"  总训练集: {len(train_aug)} samples")

    # Step 4: 分割与平衡
    print("\n[4/5] 数据平衡...")
    random.shuffle(train_aug)

    # 统计最终分布
    thesis_ai_final = sum(1 for s in train_aug if s["domain"] in THESIS_DOMAINS and s["label"] == 1)
    thesis_human_final = sum(1 for s in train_aug if s["domain"] in THESIS_DOMAINS and s["label"] == 0)
    non_thesis_final = sum(1 for s in train_aug if s["domain"] not in THESIS_DOMAINS)

    print(f"  最终分布:")
    print(f"    论文-AI:    {thesis_ai_final}")
    print(f"    论文-Human: {thesis_human_final}")
    print(f"    非论文:     {non_thesis_final}")
    print(f"    总计:       {len(train_aug)}")

    # 统计子类型
    subtypes = Counter(s.get("subtype", "original") for s in train_aug)
    for st, cnt in subtypes.most_common():
        print(f"    subtype={st}: {cnt}")

    # Step 5: 保存
    print("\n[5/5] 保存数据...")
    TRAINING_DIR.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_TRAIN, "w", encoding="utf-8") as f:
        json.dump(train_aug, f, ensure_ascii=False)
    with open(OUTPUT_VAL, "w", encoding="utf-8") as f:
        json.dump(val_aug, f, ensure_ascii=False)

    print(f"\n  训练集: {OUTPUT_TRAIN} ({len(train_aug)} samples)")
    print(f"  验证集: {OUTPUT_VAL} ({len(val_aug)} samples)")
    print("\nDone.")


if __name__ == "__main__":
    main()
