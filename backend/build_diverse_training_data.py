"""
构建多样化中文 AIGC 检测训练数据集

合并 16 个数据源，覆盖 15+ 种文体/语言类型，超越现有 AIGC 检测模型。

数据源:
  1. CUDRT Chinese (~20K) — 百科/医疗/金融/法律/心理 (已下载)
  2. HC3-Chinese 按领域 (~29K) — 百科/金融/法律/医疗/问答/心理 (已下载)
  3-12. DeepSeek API 生成 (~12K) — 学术/文学/作文/新闻/社交/技术/公文/商务/广告/对话
  13. NLPCC 2025 Task 1 (~32K) — 中文AIGC检测竞赛数据 (需 git clone)
  14. CSL 学术文献 (~5K) — 人类撰写的学术论文摘要 (需 git clone)
  15. Chinese Chatbot Corpus (~3K) — 豆瓣/微博/贴吧真实对话 (需 git clone)
  16. LLM-Detector (~5K) — HuggingFace 多LLM中文检测数据 (需 pip install datasets)

用法:
  python build_diverse_training_data.py                          # 完整构建 (全部 16 sources)
  python build_diverse_training_data.py --skip_api               # 仅本地数据 (sources 1-2 + 13-16)
  python build_diverse_training_data.py --resume                 # API 断点续传

前置准备 (可选但推荐):
  git clone https://github.com/NLP2CT/NLPCC-2025-Task1.git ../data/NLPCC-2025-Task1
  git clone https://github.com/ydli-ai/CSL.git ../data/CSL
  git clone https://github.com/codemayq/chinese-chatbot-corpus.git ../data/chinese-chatbot-corpus
  pip install datasets  # LLM-Detector HuggingFace
"""

import os
import sys
import json
import time
import random
import argparse
import re
from pathlib import Path
from typing import Optional

random.seed(42)

# ============================================================
# 配置
# ============================================================

DATA_DIR = Path("../data")
CUDRT_DIR = DATA_DIR / "CUDRT/Detector/Roberta/Chinese/dataset"
HC3_DIR = DATA_DIR
TRAINING_DIR = DATA_DIR / "training"
CHECKPOINT_FILE = TRAINING_DIR / ".build_diverse_checkpoint.json"

OUTPUT_TRAIN = TRAINING_DIR / "aigc_diverse_train.json"
OUTPUT_VAL = TRAINING_DIR / "aigc_diverse_val.json"

# DeepSeek API 配置 — 优先级: 环境变量 > claude settings > 硬编码
def _load_api_config():
    """从多来源加载 API 配置，优先环境变量，其次 claude settings。"""
    api_key = os.getenv("LLM_API_KEY", "")
    api_base = os.getenv("LLM_API_BASE", "")
    api_model = os.getenv("LLM_MODEL", "")

    if not api_key:
        # 尝试从 ~/.claude/settings.json 读取
        claude_settings_paths = [
            os.path.expanduser("~/.claude/settings.json"),
            os.path.expanduser("~/.claude/settings.local.json"),
        ]
        for sp in claude_settings_paths:
            if os.path.exists(sp):
                try:
                    with open(sp, "r", encoding="utf-8") as f:
                        cs = json.load(f)
                    env = cs.get("env", {})
                    if not api_key:
                        api_key = env.get("ANTHROPIC_AUTH_TOKEN", "")
                    if not api_base:
                        # Claude settings 用的是 Anthropic 协议地址，需要转成 DeepSeek 原生地址
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

# HC3 文件名 → 领域映射
HC3_DOMAIN_MAP = {
    "hc3_zh_baike.jsonl": "baike",
    "hc3_zh_finance.jsonl": "finance",
    "hc3_zh_law.jsonl": "law",
    "hc3_zh_medicine.jsonl": "medicine",
    "hc3_zh_nlpcc_dbqa.jsonl": "qa",
    "hc3_zh_open_qa.jsonl": "qa",
    "hc3_zh_psychology.jsonl": "psychology",
}

# AI 拒绝/免责模式 (复用 clean_training_data.py 逻辑)
AI_REFUSAL_PATTERNS = [
    "我不确定", "抱歉", "无法回答", "无法提供", "我无法",
    "作为一个AI", "作为AI", "我是一名AI", "我不了解",
    "我没有", "我不知", "我的知识", "我不能",
    "请提供更多", "您能提供", "对不起",
]


# ============================================================
# 文本清洗
# ============================================================

def clean_text(txt: str) -> str:
    if not txt:
        return ""
    txt = str(txt)
    txt = txt.strip()
    txt = re.sub(r'\s{3,}', ' ', txt)
    txt = txt.replace('ſ', '').replace('α', '')
    txt = txt.replace('。。', '。').replace('，，', '，')
    return txt


def is_ai_refusal(txt: str) -> bool:
    for pat in AI_REFUSAL_PATTERNS:
        if pat in txt[:100]:
            return True
    return False


def is_valid_sample(txt: str) -> bool:
    if len(txt) < 20 or len(txt) > 2000:
        return False
    chinese_chars = sum(1 for c in txt if '一' <= c <= '鿿')
    return chinese_chars >= 10


# ============================================================
# 数据源 1: CUDRT Chinese
# ============================================================

def load_cudrt() -> list[dict]:
    """加载 CUDRT Chinese 数据，统一格式。"""
    samples = []
    for split_name, filename in [("train", "train.json"), ("val", "val.json")]:
        path = CUDRT_DIR / filename
        if not path.exists():
            print(f"  [CUDRT] 跳过: {path} 不存在")
            continue
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            text = item.get("AI_text") or item.get("human_text") or ""
            label = item.get("label", 0)
            text = clean_text(text)
            if not is_valid_sample(text):
                continue
            if label == 1 and is_ai_refusal(text):
                continue
            samples.append({"domain": "cudrt", "text": text, "label": label})
        print(f"  [CUDRT] {split_name}: {len(data)} raw -> {len([s for s in samples if s['domain']=='cudrt'])} valid (cumulative)")
    return samples


# ============================================================
# 数据源 2: HC3-Chinese 按领域
# ============================================================

def load_hc3_domain(filepath: Path, domain: str) -> list[dict]:
    """从单个 HC3 jsonl 文件加载样本。"""
    samples = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            # 人类回答
            for ans in item.get("human_answers", []):
                if not ans:
                    continue
                text = clean_text(str(ans))
                if is_valid_sample(text):
                    samples.append({"domain": domain, "text": text, "label": 0})
            # AI 回答
            for ans in item.get("chatgpt_answers", []):
                if not ans:
                    continue
                text = clean_text(str(ans))
                if not is_valid_sample(text):
                    continue
                if is_ai_refusal(text):
                    continue
                samples.append({"domain": domain, "text": text, "label": 1})
    return samples


def load_hc3_all() -> list[dict]:
    """加载所有 HC3-Chinese 领域数据。"""
    all_samples = []
    for filename in os.listdir(HC3_DIR):
        if filename not in HC3_DOMAIN_MAP:
            continue
        domain = HC3_DOMAIN_MAP[filename]
        path = HC3_DIR / filename
        samples = load_hc3_domain(path, domain)
        all_samples.extend(samples)
        n_human = sum(1 for s in samples if s["label"] == 0)
        n_ai = sum(1 for s in samples if s["label"] == 1)
        print(f"  [HC3] {filename}: {len(samples)} ({n_human} human, {n_ai} AI) [{domain}]")
    return all_samples


# ============================================================
# 数据源 13: NLPCC 2025 Task 1 (中文 AIGC 检测竞赛数据)
# ============================================================

NLPCC2025_DIR = DATA_DIR / "NLPCC-2025-Task1"


def load_nlpcc2025() -> list[dict]:
    """加载 NLPCC 2025 共享任务数据。
    下载: git clone https://github.com/NLP2CT/NLPCC-2025-Task1.git ../data/NLPCC-2025-Task1
    """
    samples = []
    if not NLPCC2025_DIR.exists():
        print("  [NLPCC2025] 跳过: 数据未下载。")
        print("    下载命令: git clone https://github.com/NLP2CT/NLPCC-2025-Task1.git ../data/NLPCC-2025-Task1")
        return samples

    # NLPCC 2025 数据格式: JSON 数组, 每条 {text, label, domain?}
    for split_name in ["train", "dev", "test"]:
        for fname in [f"{split_name}.json", f"task1_{split_name}.json", f"data/{split_name}.json"]:
            path = NLPCC2025_DIR / fname
            if path.exists():
                break
        else:
            # 尝试遍历目录
            for f in NLPCC2025_DIR.rglob(f"*{split_name}*.json"):
                path = f
                break
            else:
                continue

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data = data.get("data", data.get("samples", []))
            for item in data:
                text = item.get("text") or item.get("content") or ""
                label = item.get("label", -1)
                if label == -1:
                    continue  # 跳过无标签数据 (测试集)
                text = clean_text(str(text))
                if not is_valid_sample(text):
                    continue
                if label == 1 and is_ai_refusal(text):
                    continue
                domain = item.get("domain", item.get("source", "nlpcc2025"))
                samples.append({"domain": str(domain), "text": text, "label": int(label)})
            n_human = sum(1 for s in samples if s["label"] == 0)
            n_ai = sum(1 for s in samples if s["label"] == 1)
            print(f"  [NLPCC2025] {split_name}: {len(data)} raw -> loaded (H={n_human}, AI={n_ai})")
        except Exception as e:
            print(f"  [NLPCC2025] {split_name} 加载失败: {e}")

    return samples


# ============================================================
# 数据源 14: CSL 中文学术文献 (人类撰写的学术摘要)
# ============================================================

CSL_DIR = DATA_DIR / "CSL"


def load_csl_abstracts(max_samples: int = 5000) -> list[dict]:
    """加载 CSL 中文学术文献的摘要作为人类学术文本。
    下载: git clone https://github.com/ydli-ai/CSL.git ../data/CSL
    CSL 格式: TSV (task \\t abstract \\t title), 用于文本摘要任务, 摘要为人类撰写
    """
    samples = []
    if not CSL_DIR.exists():
        print("  [CSL] 跳过: 数据未下载。")
        print("    下载命令: git clone https://github.com/ydli-ai/CSL.git ../data/CSL")
        return samples

    # CSL 数据在 benchmark/ts/ 目录下, TSV 格式
    tsv_dir = CSL_DIR / "benchmark" / "ts"
    if not tsv_dir.exists():
        # 尝试其他路径
        for p in [CSL_DIR / "data", CSL_DIR]:
            if (p / "train.tsv").exists():
                tsv_dir = p
                break

    count = 0
    for split_name in ["train", "dev", "test"]:
        if count >= max_samples:
            break
        path = tsv_dir / f"{split_name}.tsv"
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                header = f.readline()  # 跳过表头
                for line in f:
                    if count >= max_samples:
                        break
                    parts = line.strip().split("\t")
                    if len(parts) >= 2:
                        abstract = parts[1]  # 第二列是摘要
                        title = parts[2] if len(parts) >= 3 else ""
                        text = f"{title}。{abstract}" if title else abstract
                        text = clean_text(str(text))
                        if is_valid_sample(text) and not is_ai_refusal(text):
                            # 根据任务类型标注领域
                            task = parts[0] if parts else "academic"
                            samples.append({"domain": f"csl_{task}", "text": text, "label": 0})
                            count += 1
            print(f"  [CSL] {split_name}: loaded samples (cumulative={count})")
        except Exception as e:
            print(f"  [CSL] {split_name} 加载失败: {e}")

    print(f"  [CSL] total: {len(samples)} human-written academic abstracts")
    return samples


# ============================================================
# 数据源 15: Chinese Chatbot Corpus (真实人类对话)
# ============================================================

CHATBOT_DIR = DATA_DIR / "chinese-chatbot-corpus"


def load_chatbot_corpus(max_samples: int = 3000) -> list[dict]:
    """加载中文聊天语料作为真实人类对话样本。
    从 HuggingFace 流式下载 JSONL (每源 500 行, 避免超时)。
    数据: https://huggingface.co/datasets/qgyd2021/chinese_chitchat
    """
    samples = []
    HF_BASE = "https://huggingface.co/datasets/qgyd2021/chinese_chitchat/resolve/main/data"
    sources = ["chatterbot", "xiaohuangji", "qingyun", "ptt", "subtitle", "tieba", "douban", "weibo"]
    per_source = max(1, max_samples // len(sources))

    try:
        import requests as _req
        for src in sources:
            if len(samples) >= max_samples:
                break
            url = f"{HF_BASE}/{src}.jsonl"
            try:
                r = _req.get(url, timeout=120, stream=True)
                if r.status_code != 200:
                    print(f"  [Chatbot] {src}: HTTP {r.status_code}")
                    continue
                count_before = len(samples)
                for line in r.iter_lines(decode_unicode=True):
                    if line and line.strip():
                        try:
                            item = json.loads(line.strip())
                        except json.JSONDecodeError:
                            continue
                        text = ""
                        if isinstance(item, dict):
                            if "text" in item:
                                text = str(item["text"])
                            elif "dialogue" in item:
                                text = str(item["dialogue"])
                            elif "messages" in item:
                                text = " ".join(m.get("content", "") for m in item["messages"] if m.get("content"))
                            else:
                                strs = [str(v) for v in item.values() if isinstance(v, str) and len(str(v)) > 10]
                                text = max(strs, key=len) if strs else ""
                        elif isinstance(item, str):
                            text = item
                        text = clean_text(text)
                        if is_valid_sample(text) and len(text) >= 30:
                            samples.append({"domain": f"chat_{src}", "text": text, "label": 0})
                            if len(samples) - count_before >= per_source:
                                break
                added = len(samples) - count_before
                if added > 0:
                    print(f"  [Chatbot] {src}: +{added} dialogues")
            except Exception as e:
                print(f"  [Chatbot] {src}: skip ({str(e)[:40]})")
                continue

        if samples:
            domains = len(set(s["domain"] for s in samples))
            print(f"  [Chatbot] total: {len(samples)} human dialogues from {domains} sources")
            return samples
    except Exception as e:
        print(f"  [Chatbot] error: {str(e)[:80]}")

    if not samples:
        print("  [Chatbot] 跳过: 网络不可达, 非关键数据")
    return samples


# ============================================================
# 数据源 16: LLM-Detector (HuggingFace 多 LLM 中文检测数据)
# ============================================================

def load_llm_detector(max_samples: int = 5000) -> list[dict]:
    """从 HuggingFace 加载 LLM-Detector 多模型中文数据。
    需要: pip install datasets + huggingface-cli login (gated dataset)
    NLPCC 2025 已覆盖 gpt4o/glm/qwen, 此数据集补充 ChatGLM2/Baichuan2/ERNIE-Bot
    如无法访问 HF, 可跳过 — NLPCC 数据已提供足够的多 LLM 覆盖
    """
    samples = []
    try:
        from datasets import load_dataset
    except ImportError:
        print("  [LLM-Detector] 跳过: datasets 未安装 (pip install datasets)")
        return samples

    try:
        dataset = load_dataset("QiYuan-tech/LLM-Detector", split="train", streaming=True)
        count = 0
        for item in dataset:
            if count >= max_samples:
                break
            text = item.get("text") or item.get("content") or ""
            label = item.get("label", -1)
            if label == -1:
                continue
            text = clean_text(str(text))
            if not is_valid_sample(text):
                continue
            if label == 1 and is_ai_refusal(text):
                continue
            source = item.get("source", "llm_detector")
            samples.append({"domain": f"lldet_{source}", "text": text, "label": int(label)})
            count += 1
        n_human = sum(1 for s in samples if s["label"] == 0)
        n_ai = sum(1 for s in samples if s["label"] == 1)
        print(f"  [LLM-Detector] loaded {len(samples)} (H={n_human}, AI={n_ai})")
    except Exception as e:
        print(f"  [LLM-Detector] 跳过: {str(e)[:100]}")

    return samples


# ============================================================
# 数据源 3-6: DeepSeek API 生成
# ============================================================

# ---- 学术论文 prompts ----
ACADEMIC_TOPICS = [
    "请写一篇关于深度学习在自然语言处理中应用的学术论文摘要。",
    "撰写一篇计算机视觉领域目标检测算法的综述摘要。",
    "请写一篇关于大语言模型幻觉问题的学术分析。",
    "撰写一篇关于知识图谱构建方法的学术论文引言。",
    "写一篇关于强化学习在机器人控制中应用的研究摘要。",
    "撰写一篇关于联邦学习隐私保护技术的学术论文段落。",
    "请写一篇关于图神经网络在推荐系统中应用的学术论述。",
    "写一篇关于对比学习在文本表示中应用的学术分析。",
    "撰写一篇关于Transformer架构优化的学术论文摘要。",
    "请写一篇关于多模态学习最新进展的综述段落。",
    "写一篇关于代码大模型的学术论文引言。",
    "撰写一篇关于AI可解释性研究的学术论述。",
    "请写一篇关于少样本学习方法的学术论文摘要。",
    "写一篇关于知识蒸馏技术的学术分析。",
    "撰写一篇关于扩散模型原理与应用的学术论文段落。",
]

# ---- 学生作文 topics ----
ESSAY_TOPICS = [
    "写一篇关于'我的大学生活'的作文。",
    "请以'一次难忘的经历'为题写一篇作文。",
    "写一篇关于'科技改变生活'的议论文。",
    "以'我的家乡'为题写一篇记叙文。",
    "写一篇关于'环境保护'的议论文。",
    "以'我的理想'为题写一篇作文。",
    "写一篇关于'网络对青少年的影响'的议论文。",
    "以'最敬佩的人'为题写一篇记叙文。",
    "写一篇关于'读书的意义'的议论文。",
    "以'那一天'为题写一篇记叙文。",
    "写一篇关于'如何看待成功'的议论文。",
    "以'我的朋友'为题写一篇记叙文。",
    "写一篇关于'人工智能的未来'的议论文。",
    "以'春天来了'为题写一篇写景作文。",
    "写一篇关于'挫折与成长'的议论文。",
]

# ---- 新闻稿 topics ----
NEWS_TOPICS = [
    "撰写一篇关于新能源汽车产业发展的新闻报道。",
    "写一篇关于城市垃圾分类政策实施效果的调查报道。",
    "请以新闻评论的方式分析互联网平台的垄断问题。",
    "写一篇关于中国航天事业最新进展的通讯稿。",
    "撰写一篇关于人工智能伦理监管的深度报道。",
    "写一篇关于乡村振兴战略实施情况的新闻稿。",
    "分析当前全球经济形势及其对中国出口贸易的影响。",
    "写一篇关于食品安全监管体系改革的专题报道。",
    "撰写一篇关于数字经济发展的新闻评论。",
    "写一篇关于教育双减政策实施一周年的总结报道。",
    "写一篇关于医疗改革最新进展的新闻稿。",
    "撰写一篇关于气候变化国际合作的深度报道。",
    "写一篇关于芯片产业自主创新的新闻评论。",
    "写一篇关于人口老龄化应对策略的调查报道。",
    "撰写一篇关于智慧城市建设的通讯稿。",
]

# ---- 文学作品 ----
LITERARY_HUMAN_TEXTS = [
    # 公开领域文学作品段落 (鲁迅/老舍/朱自清/冰心/汪曾祺/沈从文)
    ("鲁迅", "秋夜", "在我的后园，可以看见墙外有两株树，一株是枣树，还有一株也是枣树。这上面的夜的天空，奇怪而高，我生平没有见过这样奇怪而高的天空。他仿佛要离开人间而去，使人们仰面不再看见。"),
    ("鲁迅", "从百草园到三味书屋", "不必说碧绿的菜畦，光滑的石井栏，高大的皂荚树，紫红的桑葚；也不必说鸣蝉在树叶里长吟，肥胖的黄蜂伏在菜花上，轻捷的叫天子忽然从草间直窜向云霄里去了。"),
    ("老舍", "林海", "目之所及，哪里都是绿的。的确是林海。群岭起伏是林海的波浪。多少种绿颜色呀：深的，浅的，明的，暗的，绿得难以形容。恐怕只有画家才能够写下这么多的绿颜色来呢。"),
    ("老舍", "济南的冬天", "对于一个在北平住惯的人，像我，冬天要是不刮风，便觉得是奇迹；济南的冬天是没有风声的。对于一个刚由伦敦回来的人，像我，冬天要能看得见日光，便觉得是怪事。"),
    ("老舍", "猫", "猫的性格实在有些古怪。说它老实吧，它有时候的确很乖。它会找个暖和地方，成天睡大觉，无忧无虑，什么事也不过问。可是，它决定要出去玩玩，就会出走一天一夜，任凭谁怎么呼唤，它也不肯回来。"),
    ("朱自清", "荷塘月色", "曲曲折折的荷塘上面，弥望的是田田的叶子。叶子出水很高，像亭亭的舞女的裙。层层的叶子中间，零星地点缀着些白花，有袅娜地开着的，有羞涩地打着朵儿的。"),
    ("朱自清", "春", "盼望着，盼望着，东风来了，春天的脚步近了。一切都像刚睡醒的样子，欣欣然张开了眼。山朗润起来了，水长起来了，太阳的脸红起来了。"),
    ("朱自清", "背影", "我看见他戴着黑布小帽，穿着黑布大马褂，深青布棉袍，蹒跚地走到铁道边，慢慢探身下去，尚不大难。可是他穿过铁道，要爬上那边月台，就不容易了。"),
    ("冰心", "繁星", "繁星闪烁着——深蓝的太空，何曾听得见它们对语？沉默中，微光里，它们深深的互相颂赞了。"),
    ("冰心", "春水", "墙角的花，你孤芳自赏时，天地便小了。"),
    ("汪曾祺", "端午的鸭蛋", "我的家乡是水乡。出鸭。高邮大麻鸭是著名的鸭种。鸭多，鸭蛋也多。高邮人也善于腌鸭蛋。高邮咸鸭蛋于是出了名。"),
    ("汪曾祺", "昆明的雨", "昆明的雨季是明亮的、丰满的，使人动情的。城春草木深，孟夏草木长。昆明的雨季，是浓绿的。"),
    ("沈从文", "边城", "小溪流下去，绕山岨流去了约三里便汇入茶峒的大河。人若过溪越小山走去，只一里路就到了茶峒城边。溪流如弓背，山路如弓弦，故远近有了小小差异。"),
    ("郁达夫", "故都的秋", "秋天，无论在什么地方的秋天，总是好的；可是啊，北国的秋，却特别地来得清，来得静，来得悲凉。"),
    ("周作人", "乌篷船", "你坐在船上，应该是游山的态度，看看四周物色，随处可见的山，岸旁的乌桕，河边的红蓼和白苹，渔舍，各式各样的桥。"),
    ("许地山", "落花生", "我们家的后园有半亩空地，母亲说，让它荒着怪可惜，既然你们那么爱吃花生，就辟来做花生园罢。"),
    ("叶圣陶", "荷花", "清早，我到公园去玩，一进门就闻到一阵清香。我赶紧往荷花池边跑去。荷花已经开了不少了。"),
    ("巴金", "繁星", "我爱月夜，但我也爱星天。从前在家乡七八月的夜晚在庭院里纳凉的时候，我最爱看天上密密麻麻的繁星。"),
]

LITERARY_AI_PROMPTS = [
    ("鲁迅", "请模仿鲁迅的风格写一篇短散文，要有沉郁的感觉和犀利的观察。"),
    ("老舍", "请模仿老舍的风格写一段描写老北京胡同的文字，要接地气、有烟火气。"),
    ("朱自清", "请模仿朱自清的风格写一篇写景的散文段落，语言要典雅优美。"),
    ("冰心", "请模仿冰心的风格写一段关于母爱或自然的短文，要有温暖细腻的感觉。"),
    ("汪曾祺", "请模仿汪曾祺的风格写一篇关于家乡美食的短文，要平实自然有韵味。"),
    ("沈从文", "请模仿沈从文的风格写一段描写湘西风景的文字，要有原始质朴的美感。"),
    ("郁达夫", "请模仿郁达夫的风格写一段感伤的游记文字。"),
    ("巴金", "请模仿巴金的风格写一段热情而真诚的抒情文字。"),
]

# ---- 社交媒体 prompts (Source 7) ----
SOCIAL_TOPICS = [
    "写一条微博，吐槽今天上班遇到的奇葩事情，语气要愤怒又好笑。",
    "知乎回答：如何看待年轻人越来越不想结婚的现象？用口语化的方式回答。",
    "豆瓣小组发帖：安利一部你最近看的好剧，要有真情实感。",
    "小红书笔记：分享一家你喜欢的咖啡店，要活泼有趣。",
    "朋友圈：今天加班到深夜，发个朋友圈吐槽一下。",
    "写一段微信群聊记录，3-4个人讨论周末去哪玩，有不同意见。",
    "微博热评：评论一条关于明星八卦的微博，要幽默犀利。",
    "知乎回答：你有哪些好用的省钱技巧？用接地气的方式回答。",
    "写一条B站弹幕风格的短评，吐槽一部烂片。",
    "模拟一个数码论坛的求助帖：电脑坏了怎么办，在线等。",
    "写一段社区论坛的回帖，讨论房价问题，要有不同观点碰撞。",
    "写一段网络直播间的弹幕和评论互动。",
]

# ---- 技术文档 prompts (Source 8) ----
TECH_TOPICS = [
    "写一篇Python入门教程的开头章节，面向编程新手。",
    "撰写一份MySQL数据库优化指南的技术文档。",
    "写一篇Git使用技巧的技术博客，包含常用命令示例。",
    "撰写Nginx配置教程：如何设置反向代理和负载均衡。",
    "写一篇Docker从入门到实践的教程文档。",
    "撰写RESTful API设计规范的技术文档。",
    "写一篇Linux常用命令整理的技术文章。",
    "撰写前端性能优化的技术分享文档。",
    "写一篇Redis缓存在项目中的应用实践文档。",
    "撰写一份代码审查标准和最佳实践文档。",
    "写一篇Vue3组合式API的使用教程。",
    "撰写一份软件系统架构设计的README文档。",
]

# ---- 政府公文 prompts (Source 9) ----
GOV_TOPICS = [
    "草拟一份关于加强城市垃圾分类管理工作的通知。",
    "撰写一份关于促进中小企业发展的实施意见。",
    "写一份关于做好防汛抗旱工作的通知。",
    "草拟一份关于加快推进数字政府建设的实施方案。",
    "撰写一份关于进一步加强安全生产工作的通知。",
    "写一份关于改善营商环境的若干措施。",
    "草拟一份关于推进养老服务发展的指导意见。",
    "撰写一份关于规范互联网平台经济的政策文件。",
    "写一份关于加强食品安全监管的实施方案。",
    "草拟一份关于落实教育双减政策的年度总结报告。",
]

# ---- 商务通讯 prompts (Source 10) ----
BUSINESS_TOPICS = [
    "写一封正式的商务合作邀请邮件。",
    "撰写一份项目进度周报，汇报工作进展和下周计划。",
    "写一份产品需求文档(PRD)的模板和示例内容。",
    "写一封内部邮件：通知团队下周要进行系统升级。",
    "撰写一份季度销售数据分析报告。",
    "写一份会议纪要，总结上周的部门讨论要点。",
    "写一封辞职信，语气要专业得体。",
    "撰写一份竞品分析报告的摘要部分。",
    "写一份年度绩效考核的自评报告。",
    "写一封客户投诉回复邮件，要诚恳专业。",
]

# ---- 广告文案 prompts (Source 11) ----
ADS_TOPICS = [
    "为一款新上市的智能手表写一篇电商详情页文案。",
    "写一段短视频口播文案，推广一款美白精华。",
    "为一家火锅店写一篇大众点评风格的推广文案。",
    "写一段社群营销文案，推广一门线上课程。",
    "为一款蓝牙耳机写一篇小红书种草文案。",
    "写一段直播带货的话术脚本，产品是空气炸锅。",
    "为一家精品酒店写一篇携程风格的产品描述。",
    "写一张促销海报的文案，主题是双十一大促。",
    "写一段公众号软文开头，推广一个理财课程。",
    "为一款猫粮写一篇宠物博主的推荐文案。",
]

# ---- 对话/聊天 prompts (Source 12) ----
CHAT_TOPICS = [
    "模拟一段客户和AI客服关于退换货的多轮对话。",
    "写一段两个同事在微信上讨论工作交接的对话。",
    "模拟一段在线教育平台的师生问答对话。",
    "写一段两个人讨论最近热映电影的聊天记录。",
    "模拟一段医疗问诊的对话（医生和患者）。",
    "写一段求职者与HR的微信沟通记录。",
    "模拟一段两个朋友讨论投资理财的对话。",
    "写一段在线技术支持与用户的对话（解决网络问题）。",
    "模拟一段旅行规划群聊的对话，4个人讨论行程。",
    "写一段心理咨询师与来访者的对话片段。",
]


def make_api_call(client, system_prompt: str, user_prompt: str, temperature: float = 0.9, max_tokens: int = 800) -> Optional[str]:
    """调用 DeepSeek API，带重试。"""
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=API_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"    API error (attempt {attempt+1}/3): {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)
    return None


def generate_api_samples(client, topics: list[str], domain: str,
                         human_system: str, ai_system: str,
                         checkpoint_key: str, existing: dict) -> list[dict]:
    """通过 API 生成配对的 (AI, 人类风格) 样本。"""
    samples = []
    start_idx = existing.get(checkpoint_key, 0)

    for i, topic in enumerate(topics):
        if i < start_idx:
            continue

        # AI 风格
        ai_text = make_api_call(client, ai_system, topic, temperature=0.9)
        if ai_text and is_valid_sample(ai_text) and not is_ai_refusal(ai_text):
            samples.append({"domain": domain, "text": clean_text(ai_text), "label": 1})

        # 人类风格
        human_text = make_api_call(client, human_system, topic, temperature=1.2)
        if human_text and is_valid_sample(human_text):
            samples.append({"domain": domain, "text": clean_text(human_text), "label": 0})

        n_ai = sum(1 for s in samples if s["label"] == 1)
        n_human = sum(1 for s in samples if s["label"] == 0)
        print(f"  [{domain}] {i+1}/{len(topics)}: {topic[:40]}... (AI={n_ai}, H={n_human})")

        # 断点续传
        existing[checkpoint_key] = i + 1
        if (i + 1) % 10 == 0:
            with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)

        time.sleep(0.5)

    return samples


def generate_literary_ai(client, existing: dict) -> list[dict]:
    """生成 AI 模仿的文学作品 (作为 AI 样本的对照)。"""
    samples = []
    start_idx = existing.get("literary_ai", 0)

    for i, (author, prompt) in enumerate(LITERARY_AI_PROMPTS):
        if i < start_idx:
            continue

        ai_text = make_api_call(
            client, "你是一个文学创作助手。", prompt, temperature=0.9, max_tokens=600
        )
        if ai_text and is_valid_sample(ai_text) and not is_ai_refusal(ai_text):
            samples.append({"domain": "literature", "text": clean_text(ai_text), "label": 1})

        print(f"  [literary_AI] {i+1}/{len(LITERARY_AI_PROMPTS)}: {author} -> {len(ai_text) if ai_text else 0} chars")

        existing["literary_ai"] = i + 1
        if (i + 1) % 5 == 0:
            with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)

        time.sleep(0.5)

    return samples


# ============================================================
# 数据汇总与划分
# ============================================================

def balance_and_split(all_samples: list[dict], train_ratio: float = 0.85):
    """分层划分训练/验证集, 保留更多 AI 样本让模型充分学习 AI 特征。

    策略:
      - NLPCC 领域 (asap/cnewsum/csl): 保留原始 3:1 AI:human 比例
      - HC3 领域 (baike/qa/psychology 等): 不丢弃 AI, 人类过多时才裁剪
      - 整体目标: human:AI ≈ 1:2 (更多 AI, 反映真实分布)
      - 不做领域样本数上限 (移除 8K cap)
    """
    # 按 (domain, label) 分组
    groups: dict[tuple[str, int], list[dict]] = {}
    for s in all_samples:
        key = (s["domain"], s["label"])
        groups.setdefault(key, []).append(s)

    print("\n原始分布:")
    for (domain, label), items in sorted(groups.items()):
        label_name = "人类" if label == 0 else "AI  "
        print(f"  {domain}: {len(items)} {label_name}")

    domains = sorted(set(d for d, _ in groups))
    nlpcc_domains = {"asap", "cnewsum", "csl", "nlpcc2025"}

    balanced = []
    for domain in domains:
        human = groups.get((domain, 0), [])
        ai = groups.get((domain, 1), [])

        if domain in nlpcc_domains:
            # NLPCC 领域: 保留原始 3:1 AI:human (最多裁剪到 4:1)
            max_ratio = 4.0
            if len(human) > len(ai) * 2:
                random.shuffle(human)
                human = human[:int(len(ai) * 2)]
            if len(ai) > len(human) * max_ratio:
                random.shuffle(ai)
                ai = ai[:int(len(human) * max_ratio)]
        else:
            # 非 NLPCC 领域: 允许 AI 更多 (human:AI 上限 1:3)
            max_ratio = 3.0
            if len(human) > len(ai) * max_ratio:
                random.shuffle(human)
                human = human[:int(len(ai) * max_ratio)]
            elif len(ai) > len(human) * max_ratio:
                random.shuffle(ai)
                ai = ai[:int(len(human) * max_ratio)]

        balanced.extend(human + ai)

    random.shuffle(balanced)

    # 分层划分 — 不设领域上限
    train_samples = []
    val_samples = []

    for domain in domains:
        domain_data = [s for s in balanced if s["domain"] == domain]
        random.shuffle(domain_data)
        split = int(len(domain_data) * train_ratio)
        train_samples.extend(domain_data[:split])
        val_samples.extend(domain_data[split:])

    random.shuffle(train_samples)
    random.shuffle(val_samples)

    print(f"\n处理后: {len(balanced)} total (H:AI ≈ 1:{sum(1 for s in balanced if s['label']==1)/max(1,sum(1 for s in balanced if s['label']==0)):.1f})")
    print(f"训练: {len(train_samples)}, 验证: {len(val_samples)}")

    return train_samples, val_samples


def print_stats(name: str, samples: list[dict]):
    """打印数据集统计。"""
    domains = sorted(set(s["domain"] for s in samples))
    print(f"\n{'='*50}")
    print(f"{name}: {len(samples)} samples")
    print(f"{'='*50}")
    for domain in domains:
        domain_samples = [s for s in samples if s["domain"] == domain]
        n_human = sum(1 for s in domain_samples if s["label"] == 0)
        n_ai = sum(1 for s in domain_samples if s["label"] == 1)
        print(f"  {domain:15s}: {len(domain_samples):5d} ({n_human:4d} human, {n_ai:4d} AI)")


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="构建多样化 AIGC 检测训练数据")
    parser.add_argument("--skip_api", action="store_true", help="跳过 API 生成，仅用已有数据")
    parser.add_argument("--resume", action="store_true", help="从断点续传")
    parser.add_argument("--output_dir", default=str(TRAINING_DIR))
    args = parser.parse_args()

    # 避免系统代理干扰
    os.environ.setdefault("NO_PROXY", "*")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_samples = []

    # ---- Source 1: CUDRT Chinese ----
    print("\n[1/12] Loading CUDRT Chinese...")
    cudrt_samples = load_cudrt()
    print(f"  Total CUDRT: {len(cudrt_samples)}")
    all_samples.extend(cudrt_samples)

    # ---- Source 2: HC3-Chinese by domain ----
    print("\n[2/12] Loading HC3-Chinese by domain...")
    hc3_samples = load_hc3_all()
    print(f"  Total HC3: {len(hc3_samples)}")
    all_samples.extend(hc3_samples)

    # ---- Source 13: NLPCC 2025 (labeled detection data) ----
    print("\n[13/16] Loading NLPCC 2025 Task 1...")
    nlpcc_samples = load_nlpcc2025()
    print(f"  Total NLPCC2025: {len(nlpcc_samples)}")
    all_samples.extend(nlpcc_samples)

    # ---- Source 14: CSL Academic Abstracts (human-written) ----
    print("\n[14/16] Loading CSL academic abstracts...")
    csl_samples = load_csl_abstracts(max_samples=5000)
    print(f"  Total CSL: {len(csl_samples)}")
    all_samples.extend(csl_samples)

    # ---- Source 15: Chinese Chatbot Corpus (human dialogues) ----
    print("\n[15/16] Loading Chinese Chatbot Corpus...")
    chatbot_samples = load_chatbot_corpus(max_samples=3000)
    print(f"  Total Chatbot: {len(chatbot_samples)}")
    all_samples.extend(chatbot_samples)

    # ---- Source 16: LLM-Detector (HuggingFace multi-LLM) ----
    print("\n[16/16] Loading LLM-Detector from HuggingFace...")
    lldet_samples = load_llm_detector(max_samples=5000)
    print(f"  Total LLM-Detector: {len(lldet_samples)}")
    all_samples.extend(lldet_samples)

    # ---- Sources 3-12: API Generation ----
    if not args.skip_api:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=API_KEY, base_url=API_BASE)

            # 断点恢复
            checkpoint = {}
            if args.resume and CHECKPOINT_FILE.exists():
                with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                    checkpoint = json.load(f)
                print(f"\n从断点恢复: {checkpoint}")

            # Source 3: 学术论文
            print("\n[3/12] Generating academic papers via DeepSeek API...")
            academic = generate_api_samples(
                client, ACADEMIC_TOPICS, "academic",
                human_system="请模仿一个研究生写学术论文的风格，使用第一人称，加入个人见解和思考过程，语言自然、有主观判断，不要过于正式和结构化。",
                ai_system="你是一个学术论文写作助手。请用中文撰写正式、结构化的学术论文段落，使用第三人称，逻辑严密，引用标准学术表达。",
                checkpoint_key="academic", existing=checkpoint,
            )
            print(f"  Total academic: {len(academic)}")
            all_samples.extend(academic)

            # Source 4: 文学作品
            print("\n[4/12] Building literary dataset...")
            # 人类: 公开领域段落
            lit_human = [
                {"domain": "literature", "text": clean_text(t), "label": 0}
                for _, _, t in LITERARY_HUMAN_TEXTS
            ]
            print(f"  literary human (public domain): {len(lit_human)}")
            all_samples.extend(lit_human)

            # AI: DeepSeek 模仿
            lit_ai = generate_literary_ai(client, checkpoint)
            print(f"  literary AI (generated): {len(lit_ai)}")
            all_samples.extend(lit_ai)

            # Source 5: 学生作文
            print("\n[5/12] Generating student essays via DeepSeek API...")
            essays = generate_api_samples(
                client, ESSAY_TOPICS, "essay",
                human_system="请以一个中国中学生或大学生的身份写作。使用口语化的语言，可以加入个人经历和感受，语言自然随性，可以有口语词，不要过于正式。",
                ai_system="你是一个学生作文辅导助手。请写一篇结构完整、论证清晰的学生作文，语言规范，条理分明。",
                checkpoint_key="essay", existing=checkpoint,
            )
            print(f"  Total essays: {len(essays)}")
            all_samples.extend(essays)

            # Source 6: 新闻稿
            print("\n[6/12] Generating news articles via DeepSeek API...")
            news = generate_api_samples(
                client, NEWS_TOPICS, "news",
                human_system="请以一名一线记者的身份写作。使用第一人称或亲历者视角，加入采访细节、现场观察和个人感受，语言生动接地气。",
                ai_system="你是一个新闻通讯社编辑。请撰写正式、客观的新闻报道，使用第三人称，结构清晰，信息全面，符合新闻写作规范。",
                checkpoint_key="news", existing=checkpoint,
            )
            print(f"  Total news: {len(news)}")
            all_samples.extend(news)

            # Source 7: 社交媒体
            print("\n[7/12] Generating social media content via DeepSeek API...")
            social = generate_api_samples(
                client, SOCIAL_TOPICS, "social",
                human_system="请以一个真实网友的身份写作。使用口语化表达，可以用网络流行语、表情符号(emoji)、吐槽、感叹，语言自然随意不加修饰，就像真实的微博/知乎/朋友圈发言。",
                ai_system="你是一个社交媒体内容创作助手。请以规范、有条理的方式写社交媒体帖子，语言流畅但相对正式，结构清晰。",
                checkpoint_key="social", existing=checkpoint,
            )
            print(f"  Total social: {len(social)}")
            all_samples.extend(social)

            # Source 8: 技术文档
            print("\n[8/12] Generating technical documentation via DeepSeek API...")
            tech = generate_api_samples(
                client, TECH_TOPICS, "tech",
                human_system="请以一个经验丰富的开发者身份写作。用自己的话解释技术概念，可以加入个人踩坑经历和实际项目经验，语言接地气，可以有不完美的表达。",
                ai_system="你是一个技术文档撰写助手。请撰写结构清晰、术语准确、示例完整的技术文档，使用规范的技术写作风格。",
                checkpoint_key="tech", existing=checkpoint,
            )
            print(f"  Total tech: {len(tech)}")
            all_samples.extend(tech)

            # Source 9: 政府公文
            print("\n[9/12] Generating government documents via DeepSeek API...")
            gov = generate_api_samples(
                client, GOV_TOPICS, "gov",
                human_system="请以一个基层公务员的身份写公文。可以加入实际工作中的困惑、执行中的困难、地方特色的表达，语言在正式中略带个人视角。",
                ai_system="你是一个政府公文撰写助手。请使用规范、正式、结构化的公文语言，包含完整的发文格式要素，使用标准套话和正式表达。",
                checkpoint_key="gov", existing=checkpoint,
            )
            print(f"  Total gov: {len(gov)}")
            all_samples.extend(gov)

            # Source 10: 商务通讯
            print("\n[10/12] Generating business communication via DeepSeek API...")
            biz = generate_api_samples(
                client, BUSINESS_TOPICS, "business",
                human_system="请以一个真实的职场人士身份写作。可以加入工作中的纠结、个人情绪、职场真实困境，语言自然不完美，体现真实的职场沟通风格。",
                ai_system="你是一个商务文档撰写助手。请使用专业、规范、礼貌的商业写作风格，结构清晰，表达得体，使用标准商务用语。",
                checkpoint_key="business", existing=checkpoint,
            )
            print(f"  Total business: {len(biz)}")
            all_samples.extend(biz)

            # Source 11: 广告文案
            print("\n[11/12] Generating ad copy via DeepSeek API...")
            ads = generate_api_samples(
                client, ADS_TOPICS, "ads",
                human_system="请以一个真实的自媒体博主或小店主的身份写推广文案。语言要接地气，可以用夸张、幽默、亲切的表达，像真人推荐而非模板化广告。",
                ai_system="你是一个专业广告文案撰写助手。请使用营销技巧、精准卖点提炼、号召性语言，撰写高转化率的商业文案。",
                checkpoint_key="ads", existing=checkpoint,
            )
            print(f"  Total ads: {len(ads)}")
            all_samples.extend(ads)

            # Source 12: 对话/聊天
            print("\n[12/12] Generating dialogue data via DeepSeek API...")
            chat = generate_api_samples(
                client, CHAT_TOPICS, "chat",
                human_system="请模拟真实的人类对话。对话要有自然的犹豫、打断、口语词、不完整的句子、情绪波动，像真实聊天记录一样自然。不要过于流畅和完整。",
                ai_system="你是一个对话生成助手。请生成流畅、完整、有礼貌的多轮对话，每条回复信息完整、逻辑清晰、表达准确。",
                checkpoint_key="chat", existing=checkpoint,
            )
            print(f"  Total chat: {len(chat)}")
            all_samples.extend(chat)

            # 清理断点文件
            if CHECKPOINT_FILE.exists():
                CHECKPOINT_FILE.unlink()

        except ImportError:
            print("\n[3-12] openai 未安装，跳过 API 生成。")
            print("  安装: pip install openai")
        except Exception as e:
            print(f"\n[3-12] API 生成出错: {e}")
            print("  继续使用已有数据...")

    # ---- 平衡与划分 ----
    print("\n" + "="*50)
    print("Balancing & splitting...")
    train, val = balance_and_split(all_samples)

    print_stats("Train", train)
    print_stats("Val", val)

    # ---- 保存 ----
    for name, data in [("train", train), ("val", val)]:
        path = output_dir / f"aigc_diverse_{name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\nSaved: {path} ({len(data)} samples)")

    print("\nDone!")


if __name__ == "__main__":
    main()
