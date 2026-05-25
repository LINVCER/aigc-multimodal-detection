"""
清理 AIGC 中文训练数据:
  1. 移除中文字符间的多余空格
  2. 过滤 AI 拒绝/免责模式样本
  3. 过滤过短/异常样本
  4. 添加口语化人类样本做增强
  5. 数据平衡并重新划分
"""

import json, re, random, os

random.seed(42)

# AI 拒绝模式
AI_REFUSAL_PATTERNS = [
    "我不确定", "抱歉", "无法回答", "无法提供", "我无法",
    "作为一个AI", "作为AI", "我是一名AI", "我不了解",
    "我没有", "我不知", "我的知识", "我不能",
    "请提供更多", "您能提供", "对不起",
    "ſ",  # 乱码
]

def clean_text(txt: str) -> str:
    """清理文本"""
    # 1. 移除中文间多余空格
    txt = re.sub(r'([一-鿿])\s+([一-鿿])', r'\1\2', txt)
    # 2. 移除行首尾空格
    txt = txt.strip()
    # 3. 移除连续3个以上空格
    txt = re.sub(r'\s{3,}', ' ', txt)
    # 4. 移除乱码字符
    txt = txt.replace('ſ', '').replace('α', '')
    # 5. 标准化标点
    txt = txt.replace('。。', '。').replace('，，', '，')
    return txt

def is_ai_refusal(txt: str) -> bool:
    """检测是否为 AI 拒绝/免责模式"""
    for pat in AI_REFUSAL_PATTERNS:
        if pat in txt[:100]:  # 只在开头100字检查
            return True
    return False

def is_valid_sample(txt: str, label: int) -> bool:
    """检查样本有效性"""
    if len(txt) < 20:  # 过短
        return False
    if len(txt) > 2000:  # 过长
        return False
    # 纯数字/符号
    chinese_chars = sum(1 for c in txt if '一' <= c <= '鿿')
    if chinese_chars < 5:
        return False
    return True

# 口语化人类样本 (风格增强)
CASUAL_HUMAN_SAMPLES = [
    ("教育", "昨天上课老师讲的我一点没听懂，问了好几个同学才搞明白。这课确实有点难，不过挺有意思的。"),
    ("教育", "刚写完论文初稿，发给导师看了。导师批了一大堆意见，今晚估计要熬夜改了。不过改完应该能好不少。"),
    ("教育", "数学作业最后那道证明题我想了半天没想出来，去问了室友他也不会。看来明天得去找老师了。"),
    ("教育", "今天上课睡觉被老师点名了，尴尬死了。昨晚打游戏打太晚了，以后不能再这样了。"),
    ("科技", "刚升级了手机系统，结果好几个APP不能用。早知道不着急升了，等别人先用几天再说。"),
    ("科技", "最近想买个机械键盘，看了好多评测还是没决定。樱桃轴和国产轴到底哪个好啊，纠结。"),
    ("科技", "帮朋友装了一台电脑，折腾了一下午。主板跳线差点插错，还好最后点亮了。"),
    ("生活", "周末和室友去吃了那家新开的火锅，味道还可以就是太贵了。下次换个便宜的地方。"),
    ("生活", "今天下雨忘带伞，淋了一身。到了公司发现同事也没带，我俩在门口互相嘲笑。"),
    ("生活", "快递又送错了楼，跑了好几趟才找到。现在的快递员都不看门牌号的吗。"),
    ("生活", "今晚煮了泡面当晚饭，加了两个蛋。说实话比食堂的好吃多了，而且还便宜。"),
    ("新闻", "今天路过市中心看到在修路，堵了好长一段。问了交警说可能要到下个月才能修好。"),
    ("文学", "刚才在阳台站了一会，吹着风挺舒服的。楼下小孩在踢球，吵吵闹闹的但也挺有生气。"),
]

def main():
    data_dir = "../data/training"

    # 加载原始数据
    with open(f"{data_dir}/aigc_chinese_train.json", "r", encoding="utf-8") as f:
        train = json.load(f)
    with open(f"{data_dir}/aigc_chinese_val.json", "r", encoding="utf-8") as f:
        val = json.load(f)

    all_data = train + val
    print(f"原始: {len(all_data)} ({len(train)} train + {len(val)} val)")

    # 统计清理前
    ai_before = sum(1 for s in all_data if s["label"] == 1)
    human_before = sum(1 for s in all_data if s["label"] == 0)

    cleaned = []
    removed_refusal = 0
    removed_short = 0
    spaces_fixed = 0

    for s in all_data:
        old = s["text"]
        new = clean_text(old)
        if len(new) != len(old):
            spaces_fixed += 1

        if s["label"] == 1 and is_ai_refusal(new):
            removed_refusal += 1
            continue

        if not is_valid_sample(new, s["label"]):
            removed_short += 1
            continue

        cleaned.append({"domain": s["domain"], "text": new, "label": s["label"]})

    # 添加口语化人类样本
    for domain, text in CASUAL_HUMAN_SAMPLES:
        cleaned.append({"domain": domain, "text": text, "label": 0})

    print(f"清理空格: {spaces_fixed} 样本")
    print(f"移除AI拒绝: {removed_refusal}")
    print(f"移除过短/无效: {removed_short}")
    print(f"添加口语化: {len(CASUAL_HUMAN_SAMPLES)}")
    print(f"清理后: {len(cleaned)}")

    # 重新平衡 (保持人类:AI ≈ 1.2:1)
    human_samples = [s for s in cleaned if s["label"] == 0]
    ai_samples = [s for s in cleaned if s["label"] == 1]

    target_ratio = 1.2
    target_ai = min(len(ai_samples), int(len(human_samples) / target_ratio))
    target_human = min(len(human_samples), int(target_ai * target_ratio))

    # 随机采样
    random.shuffle(human_samples)
    random.shuffle(ai_samples)

    balanced = human_samples[:target_human] + ai_samples[:target_ai]
    random.shuffle(balanced)

    print(f"平衡后: {len(balanced)} (人类={target_human}, AI={target_ai})")

    # 重新划分
    split = int(len(balanced) * 0.85)
    train_new = balanced[:split]
    val_new = balanced[split:]

    for name, data in [("train", train_new), ("val", val_new)]:
        path = f"{data_dir}/aigc_chinese_clean_{name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        ai = sum(1 for s in data if s["label"] == 1)
        human = sum(1 for s in data if s["label"] == 0)
        print(f"{name}: {len(data)} ({human} human, {ai} AI) -> {path}")

    print("\nDone!")


if __name__ == "__main__":
    main()
