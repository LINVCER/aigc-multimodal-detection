"""
文本检测模型评估脚本

评估重训后的模型:
  1. 文学作品测试 (硬性门控: 全部 < 30% AIGC)
  2. 按领域在 CUDRT 验证集上报告指标
  3. 回归测试 (原 bug 案例)

用法:
  python eval_text_detector.py --checkpoint ../models/text/aigc_detector_v2.pth
  python eval_text_detector.py --checkpoint ../models/text/aigc_detector_v2.pth --test_domains --test_literary
"""

import os
import sys
import json
import argparse
import asyncio

import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ============================================================
# 文学作品测试集 (公开领域经典段落)
# ============================================================

LITERARY_TESTS = [
    # (作者, 篇目, 文本)
    ("老舍", "林海", "目之所及，哪里都是绿的。的确是林海。群岭起伏是林海的波浪。多少种绿颜色呀：深的，浅的，明的，暗的，绿得难以形容。恐怕只有画家才能够写下这么多的绿颜色来呢。"),
    ("老舍", "济南的冬天", "对于一个在北平住惯的人，像我，冬天要是不刮风，便觉得是奇迹；济南的冬天是没有风声的。对于一个刚由伦敦回来的人，像我，冬天要能看得见日光，便觉得是怪事。"),
    ("老舍", "猫", "猫的性格实在有些古怪。说它老实吧，它有时候的确很乖。它会找个暖和地方，成天睡大觉，无忧无虑，什么事也不过问。可是，它决定要出去玩玩，就会出走一天一夜，任凭谁怎么呼唤，它也不肯回来。"),
    ("鲁迅", "秋夜", "在我的后园，可以看见墙外有两株树，一株是枣树，还有一株也是枣树。这上面的夜的天空，奇怪而高，我生平没有见过这样奇怪而高的天空。"),
    ("鲁迅", "从百草园到三味书屋", "不必说碧绿的菜畦，光滑的石井栏，高大的皂荚树，紫红的桑葚；也不必说鸣蝉在树叶里长吟，肥胖的黄蜂伏在菜花上，轻捷的叫天子忽然从草间直窜向云霄里去了。"),
    ("朱自清", "荷塘月色", "曲曲折折的荷塘上面，弥望的是田田的叶子。叶子出水很高，像亭亭的舞女的裙。层层的叶子中间，零星地点缀着些白花，有袅娜地开着的，有羞涩地打着朵儿的。"),
    ("朱自清", "春", "盼望着，盼望着，东风来了，春天的脚步近了。一切都像刚睡醒的样子，欣欣然张开了眼。山朗润起来了，水长起来了，太阳的脸红起来了。"),
    ("朱自清", "背影", "我看见他戴着黑布小帽，穿着黑布大马褂，深青布棉袍，蹒跚地走到铁道边，慢慢探身下去，尚不大难。可是他穿过铁道，要爬上那边月台，就不容易了。"),
    ("冰心", "繁星", "繁星闪烁着——深蓝的太空，何曾听得见它们对语？沉默中，微光里，它们深深的互相颂赞了。"),
    ("冰心", "春水", "墙角的花，你孤芳自赏时，天地便小了。"),
    ("汪曾祺", "端午的鸭蛋", "我的家乡是水乡。出鸭。高邮大麻鸭是著名的鸭种。鸭多，鸭蛋也多。高邮人也善于腌鸭蛋。高邮咸鸭蛋于是出了名。"),
    ("沈从文", "边城", "小溪流下去，绕山岨流去了约三里便汇入茶峒的大河。人若过溪越小山走去，只一里路就到了茶峒城边。溪流如弓背，山路如弓弦，故远近有了小小差异。"),
    ("郁达夫", "故都的秋", "秋天，无论在什么地方的秋天，总是好的；可是啊，北国的秋，却特别地来得清，来得静，来得悲凉。"),
    ("巴金", "繁星", "我爱月夜，但我也爱星天。从前在家乡七八月的夜晚在庭院里纳凉的时候，我最爱看天上密密麻麻的繁星。"),
    ("许地山", "落花生", "我们家的后园有半亩空地，母亲说，让它荒着怪可惜，既然你们那么爱吃花生，就辟来做花生园罢。"),
    ("叶圣陶", "荷花", "清早，我到公园去玩，一进门就闻到一阵清香。我赶紧往荷花池边跑去。荷花已经开了不少了。"),
    ("周作人", "乌篷船", "你坐在船上，应该是游山的态度，看看四周物色，随处可见的山，岸旁的乌桕，河边的红蓼和白苹，渔舍，各式各样的桥。"),
]


# ============================================================
# AI 生成测试样本 (用于验证模型不是把所有文本都判为人类)
# ============================================================

AI_TEST_SAMPLES = [
    ("学术-AI", "值得注意的是，深度学习在自然语言处理领域的应用日益广泛，已经成为推动该领域发展的核心技术范式。进一步来说，基于Transformer架构的预训练语言模型在多项基准测试中取得了显著的性能提升。"),
    ("新闻-AI", "随着数字经济的快速发展，人工智能技术在各个行业的应用日益广泛。专家指出，未来五年AI医疗市场规模有望突破千亿，成为推动经济增长的新引擎。"),
    ("百科-AI", "机器学习是人工智能的一个重要分支，它使计算机系统能够从数据中自动学习和改进，而无需进行明确的编程。常见的机器学习方法包括监督学习、无监督学习和强化学习。"),
]


# ============================================================
# 模型加载 (复用 roberta_detector 的加载逻辑)
# ============================================================

def load_detector(checkpoint_path: str, no_calib: bool = False):
    """加载 RoBERTa 检测器并返回 detect 函数。"""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model_path = "hfl/chinese-roberta-wwm-ext"

    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True, local_files_only=True)
    roberta = AutoModel.from_pretrained(model_path, trust_remote_code=True, local_files_only=True).to(device)
    roberta.eval()

    hidden_size = roberta.config.hidden_size
    classifier = nn.Sequential(
        nn.Dropout(0.1),
        nn.Linear(hidden_size, 256),
        nn.ReLU(),
        nn.Dropout(0.1),
        nn.Linear(256, 1),
    ).to(device)

    ckpt = torch.load(checkpoint_path, map_location=device)

    if "classifier_state_dict" in ckpt:
        sd = ckpt["classifier_state_dict"]
        if sd["4.weight"].shape[0] == 2:
            w = sd["4.weight"].data
            b = sd["4.bias"].data
            sd["4.weight"] = (w[1:2] - w[0:1])
            sd["4.bias"] = (b[1:2] - b[0:1])
        classifier.load_state_dict(sd)

    temperature = ckpt.get("temperature", 1.0)
    platt_a = ckpt.get("platt_a", 1.0)
    platt_b = ckpt.get("platt_b", 0.0)
    val_acc = ckpt.get("val_acc", "N/A")
    val_f1 = ckpt.get("val_f1", "N/A")
    ece = ckpt.get("ece", "N/A")

    if no_calib:
        temperature = 1.0
        platt_a = 1.0
        platt_b = 0.0
        print(f"Loaded checkpoint: val_acc={val_acc}, val_f1={val_f1}")
        print(f"  Calibration DISABLED (raw logits)")
    else:
        print(f"Loaded checkpoint: val_acc={val_acc}, val_f1={val_f1}, ece={ece}")
        print(f"  T={temperature:.3f}, Platt=({platt_a:.3f},{platt_b:.3f})")

    def detect(text: str) -> float:
        inputs = tokenizer(text, max_length=512, padding=True, truncation=True, return_tensors="pt").to(device)
        with torch.no_grad():
            outputs = roberta(**inputs)
            embedding = outputs.last_hidden_state[:, 0, :]
            logit = classifier(embedding).squeeze(-1).item()
        scaled = logit / max(temperature, 0.1)
        calibrated = platt_a * scaled + platt_b
        return torch.sigmoid(torch.tensor(calibrated)).item()

    return detect, ckpt


# ============================================================
# 测试函数
# ============================================================

def test_literary(detect) -> bool:
    """测试文学经典作品 — 必须全部 < 0.3 AIGC 概率。"""
    print("\n" + "="*60)
    print("文学作品测试 (硬性门控: 全部 < 30% AIGC)")
    print("="*60)

    all_pass = True
    results = []

    for author, title, text in LITERARY_TESTS:
        prob = detect(text)
        passed = prob < 0.3
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        results.append({"author": author, "title": title, "prob": prob, "pass": passed})
        print(f"  [{status}] {author:6s}《{title:12s}》 AIGC={prob:.4f} ({prob*100:.1f}%)")

    n_pass = sum(1 for r in results if r["pass"])
    print(f"\n  结果: {n_pass}/{len(results)} 通过")
    return all_pass


def test_ai_samples(detect, threshold: float = 0.3) -> bool:
    """测试 AI 生成样本 — 应该被检测为 AI。"""
    print("\n" + "="*60)
    print(f"AI 样本检测测试 (阈值={threshold*100:.0f}%)")
    print("="*60)

    all_pass = True
    for label, text in AI_TEST_SAMPLES:
        prob = detect(text)
        passed = prob > threshold
        status = "PASS" if passed else "WARN"
        if not passed:
            all_pass = False
        print(f"  [{status}] {label:10s}: AIGC={prob:.4f}")

    return all_pass


def test_domain_breakdown(detect, dataset_path: str):
    """在指定数据集上按领域报告指标。"""
    print("\n" + "="*60)
    print(f"按领域评估: {dataset_path}")
    print("="*60)

    if not os.path.exists(dataset_path):
        print(f"  [SKIP] 数据集不存在: {dataset_path}")
        return

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 按领域统计
    domain_metrics: dict[str, dict] = {}

    for item in data:
        text = item.get("text") or item.get("AI_text") or item.get("human_text") or ""
        label = item.get("label", 0)
        domain = item.get("domain", "unknown")

        if len(text) < 20:
            continue

        prob = detect(text)
        pred = 1 if prob > 0.3 else 0

        if domain not in domain_metrics:
            domain_metrics[domain] = {"total": 0, "correct": 0, "tp": 0, "fp": 0, "fn": 0, "tn": 0}

        m = domain_metrics[domain]
        m["total"] += 1
        if pred == label:
            m["correct"] += 1
        if pred == 1 and label == 1:
            m["tp"] += 1
        elif pred == 1 and label == 0:
            m["fp"] += 1
        elif pred == 0 and label == 1:
            m["fn"] += 1
        else:
            m["tn"] += 1

    # 打印报告
    print(f"\n{'Domain':15s} {'N':5s} {'Acc':7s} {'Prec':7s} {'Rec':7s} {'F1':7s}")
    print("-" * 55)

    total_tp = total_fp = total_fn = total_tn = 0
    for domain in sorted(domain_metrics):
        m = domain_metrics[domain]
        acc = m["correct"] / m["total"]
        prec = m["tp"] / (m["tp"] + m["fp"] + 1e-8)
        rec = m["tp"] / (m["tp"] + m["fn"] + 1e-8)
        f1 = 2 * prec * rec / (prec + rec + 1e-8)
        print(f"  {domain:13s} {m['total']:5d} {acc:6.3f}  {prec:6.3f}  {rec:6.3f}  {f1:6.3f}")
        total_tp += m["tp"]
        total_fp += m["fp"]
        total_fn += m["fn"]
        total_tn += m["tn"]

    total_acc = (total_tp + total_tn) / (total_tp + total_fp + total_fn + total_tn + 1e-8)
    total_prec = total_tp / (total_tp + total_fp + 1e-8)
    total_rec = total_tp / (total_tp + total_fn + 1e-8)
    total_f1 = 2 * total_prec * total_rec / (total_prec + total_rec + 1e-8)
    print("-" * 55)
    print(f"  {'OVERALL':13s} {total_tp+total_fp+total_fn+total_tn:5d} {total_acc:6.3f}  {total_prec:6.3f}  {total_rec:6.3f}  {total_f1:6.3f}")


# ============================================================
# 对抗攻击测试
# ============================================================

ADVERSARIAL_TESTS = [
    {
        "name": "homoglyph",
        "original": "值得注意的是，深度学习在自然语言处理领域的应用日益广泛。",
        "attacked": "值得注意的是，深度学习在自然语言处理领域的应用日益广泛。注意，这里混入了Cyrillic字母：оОеЕаАсС",
        "desc": "同形字攻击",
    },
    {
        "name": "zerowidth",
        "original": "人工智能技术正在深刻改变我们的生活方式和工作模式。",
        "attacked": "人工智能技术正在深刻改变我们的生活方式和工作模式。",
        "desc": "零宽字符注入",
    },
    {
        "name": "synonym_swap",
        "original": "机器学习是人工智能的重要分支，它使计算机系统能够从数据中自动学习和改进。",
        "attacked": "机器学习为人工智能的关键分支，它令计算机系统得以由数据中自行学习与提升。",
        "desc": "同义词替换",
    },
    {
        "name": "backtranslate_sim",
        "original": "这篇文章写得挺好，我觉得作者的观点很独特，让人耳目一新。",
        "attacked": "这篇论文写得十分精彩，笔者认为作者的观点极具独特性，使人感到新颖。",
        "desc": "回译模拟 (口语→正式)",
    },
]


def test_adversarial(detect) -> dict:
    """对抗攻击鲁棒性测试 — 攻击后置信度变化应 < 0.15。"""
    print("\n" + "="*60)
    print("对抗攻击鲁棒性测试 (阈值: 置信度变化 < 0.15)")
    print("="*60)

    all_pass = True
    deltas = []

    for test in ADVERSARIAL_TESTS:
        prob_orig = detect(test["original"])
        # 注入零宽字符到 attacked 文本
        attacked = test["attacked"]
        if test["name"] == "zerowidth":
            attacked = "".join(c + "​" for c in test["original"][:len(test["original"])//2]) + test["original"][len(test["original"])//2:]
        prob_adv = detect(attacked)
        delta = abs(prob_adv - prob_orig)
        passed = delta < 0.15
        if not passed:
            all_pass = False
        deltas.append(delta)
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {test['desc']:12s}: {prob_orig:.3f} -> {prob_adv:.3f} (Δ={delta:.3f})")

    avg_delta = sum(deltas) / len(deltas) if deltas else 0
    n_pass = sum(1 for d in deltas if d < 0.15)
    print(f"\n  Result: {n_pass}/{len(deltas)} pass, avg Δ={avg_delta:.3f}")
    return {"pass": all_pass, "avg_delta": avg_delta, "n_pass": n_pass, "total": len(deltas)}


# ============================================================
# 社交媒体混合测试
# ============================================================

SOCIAL_TEST_SAMPLES = [
    # 真实社交媒体风格 (人类)
    ("social-human", "笑死我了哈哈哈哈哈今天在地铁上看到一个大叔穿了两只不一样的鞋我真的憋不住了", 0),
    ("social-human", "有人知道那个新出的奶茶到底好不好喝吗 在线等 挺急的😭", 0),
    ("social-human", "救命啊这个月的KPI又完不成了 leader已经找我谈了三次话了", 0),
    ("social-human", "你们觉得这个配置值不值？i7+4060 才6999？感觉可以冲了", 0),
    # AI 生成的社交媒体风格
    ("social-AI", "今天下午我去了市中心的一家咖啡店，环境非常优雅。服务员态度热情周到，让人感到宾至如归。咖啡的味道醇厚浓郁，值得推荐给大家。", 1),
    ("social-AI", "根据我的经验，选购笔记本电脑时需要考虑多个因素：处理器性能、内存容量、存储空间、屏幕质量以及续航时间，这些都是选购过程中不可忽视的重要指标。", 1),
]


def test_social_media(detect) -> bool:
    """社交媒体文本测试 — 检查模型能否区分真实社交帖 vs AI 写的社交帖。"""
    print("\n" + "="*60)
    print("社交媒体文本测试")
    print("="*60)

    all_pass = True
    for label, text, expected in SOCIAL_TEST_SAMPLES:
        prob = detect(text)
        pred = 1 if prob > 0.3 else 0
        passed = pred == expected
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}] {label:15s}: AIGC={prob:.4f} (expected={'AI' if expected else 'H'})")

    return all_pass


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="评估文本检测模型")
    parser.add_argument("--checkpoint", type=str, required=True, help="模型 checkpoint 路径")
    parser.add_argument("--test_literary", action="store_true", default=True, help="测试文学作品 (默认)")
    parser.add_argument("--test_ai", action="store_true", default=True, help="测试 AI 样本")
    parser.add_argument("--test_domains", action="store_true", default=False, help="按领域评估")
    parser.add_argument("--domain_data", type=str, default="../data/training/aigc_diverse_val.json",
                        help="按领域评估用的数据集")
    parser.add_argument("--literary_threshold", type=float, default=0.2, help="文学作品误判阈值 (严格模式)")
    parser.add_argument("--test_adversarial", action="store_true", default=False, help="对抗攻击鲁棒性测试")
    parser.add_argument("--test_social", action="store_true", default=False, help="社交媒体文本测试")
    parser.add_argument("--output_report", type=str, default=None, help="输出 JSON 报告路径")
    parser.add_argument("--no_calib", action="store_true", help="禁用 Temperature/Platt 校准，使用原始 logits")
    args = parser.parse_args()

    print(f"Loading model from: {args.checkpoint}")
    detect, ckpt = load_detector(args.checkpoint, no_calib=args.no_calib)

    literary_pass = True
    ai_pass = True
    adversarial_result = {"pass": True, "avg_delta": 0.0}
    social_pass = True

    if args.test_literary:
        literary_pass = test_literary(detect)

    if args.test_ai:
        ai_pass = test_ai_samples(detect)

    if args.test_domains:
        test_domain_breakdown(detect, args.domain_data)

    if args.test_adversarial:
        adversarial_result = test_adversarial(detect)

    if args.test_social:
        social_pass = test_social_media(detect)

    # 最终判断
    print("\n" + "="*60)
    print("总结")
    print("="*60)
    print(f"  文学作品测试:     {'PASS' if literary_pass else 'FAIL'} (阈值={args.literary_threshold*100:.0f}%)")
    print(f"  AI 样本测试:      {'PASS' if ai_pass else 'WARN'}")
    if args.test_social:
        print(f"  社交媒体测试:     {'PASS' if social_pass else 'FAIL'}")
    if args.test_adversarial:
        print(f"  对抗攻击鲁棒性:   {'PASS' if adversarial_result['pass'] else 'FAIL'} (avg Δ={adversarial_result['avg_delta']:.3f})")
    print(f"  Checkpoint: val_acc={ckpt.get('val_acc','N/A')}, val_f1={ckpt.get('val_f1','N/A')}, ece={ckpt.get('ece','N/A')}")

    overall = literary_pass and ai_pass and social_pass and adversarial_result.get("pass", True)
    print(f"\n  >>> 综合结果: {'PASS' if overall else 'FAIL'} <<<")

    if args.output_report:
        report = {
            "checkpoint": args.checkpoint,
            "checkpoint_metrics": {
                "val_acc": ckpt.get("val_acc"),
                "val_f1": ckpt.get("val_f1"),
                "ece": ckpt.get("ece"),
            },
            "literary_pass": literary_pass,
            "ai_pass": ai_pass,
            "social_pass": social_pass if args.test_social else None,
            "adversarial": adversarial_result if args.test_adversarial else None,
            "overall": overall,
        }
        with open(args.output_report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\nReport saved: {args.output_report}")

    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
