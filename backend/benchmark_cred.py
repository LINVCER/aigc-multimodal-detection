"""
C-ReD 风格基准测试 — 五领域中文 AIGC 检测评估

模拟 C-ReD 论文的 5 个领域: 新闻 / 问答 / 影评 / 作文 / 学术
使用 DeepSeek API 生成 AI 文本 + 人工撰写/改写作为人类文本
评估检测器在各领域的准确率、F1、召回率
"""

import os, sys, json, time, random, asyncio
from pathlib import Path
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 五个领域的人类文本模板 (模拟真实场景)
HUMAN_TEMPLATES = {
    "新闻": [
        "今日上午10时，市交通局召开新闻发布会，宣布地铁三号线北延段将于下月正式通车。该线路全长15.3公里，设车站12座，预计日均客流量将超过20万人次。",
        "据本报记者了解，受持续降雨影响，老城区多路段出现积水。市政部门已调集50台抽水泵参与排涝，暂无人员伤亡报告。周边居民表示，希望政府能加快排水系统改造。",
        "在昨晚举行的CBA联赛中，广东队以108比95战胜辽宁队，取得了本赛季的第十场连胜。赛后主教练表示，球队的防守执行得非常好。",
    ],
    "问答": [
        "说实话我也不太确定，这个问题你得去问问专业人士。我当时学的时候也是查了很多资料，最好的方法还是多练习。推荐你可以看看B站上那个系列教程，讲得很清楚。",
        "这个问题问得好，我当年也遇到过类似的困扰。后来发现其实关键在于理解底层原理，而不是死记硬背。建议你先从基础概念入手，慢慢来，别着急。",
        "我是做这行的，可以说几句。现在市面上确实很多培训机构都在吹，但真正靠谱的就那么几家。选的时候主要看老师水平和课程内容，别光看价格。",
    ],
    "影评": [
        "昨晚看了流浪地球3，特效确实比前两部上了一个台阶。但是剧情嘛说实话有点乱，感觉导演想讲的东西太多了。不过冲着这个视效还是值得去电影院看的。",
        "说实话这部片子的演员表现让我挺意外的。本来以为是那种流水线产品，结果看到一半居然有点感动。特别是结尾那场戏，拍得真不错。",
        "朋友推荐看的，说是年度最佳。看完之后我觉得还行吧，没有那么神。不过相比今年看的其他几部垃圾片，这个确实算良心了。节奏把控得挺好，不拖沓。",
    ],
    "作文": [
        "那年夏天，我第一次离开家乡去城里上学。临走那天，母亲往我的包里塞了十几个煮鸡蛋，父亲沉默地抽着烟。我坐在颠簸的大巴车上，看着窗外的田野一点点远去，心里既有期待也有不舍。",
        "有人说青春是一首歌，我觉得青春更像是一阵风。来的时候轰轰烈烈，走的时候悄无声息。现在回想起来，那些曾经以为过不去的坎，那些哭过笑过的日子，都成了最珍贵的回忆。",
        "站在十七岁的门槛上，回望过去的岁月，我感慨万千。成长是一条没有回程的路，每一步都是新的开始。感谢那些陪伴我成长的人，感谢那些让我跌倒的挫折。",
    ],
    "学术": [
        "本文提出了一种基于对比学习的文本表示方法。实验在三个公开数据集上进行验证，结果表明所提方法在语义相似度任务上取得了显著的性能提升。",
        "通过对500名大学生的问卷调查，我们发现社交媒体使用时长与学业成绩之间存在显著的负相关关系。进一步的回归分析表明，控制其他变量后这一关系仍然显著。",
        "我们设计了一个多模态融合框架，将视觉特征与文本特征在注意力机制下进行交互。在图文匹配任务上的实验结果显示，该方法优于现有的单模态基线方法。",
    ],
}

# AI 生成 Prompts (模拟 C-ReD 真实场景)
AI_PROMPTS = {
    "新闻": [
        "请写一篇300字左右的新闻报道，报道人工智能在医疗领域的最新突破。",
        "撰写一篇关于新能源产业发展的深度报道，包含数据和分析。",
        "写一篇关于智慧城市建设的新闻稿，突出市民生活的改善。",
    ],
    "问答": [
        "请详细回答：什么是机器学习中的过拟合？如何解决？",
        "解释一下区块链技术的基本原理，用通俗的语言。",
        "量子计算和经典计算有什么区别？请举例说明。",
    ],
    "影评": [
        "请写一篇关于电影《流浪地球》的影评，分析其科幻设定和人文关怀。",
        "撰写一篇针对最新上映科幻片的电影评论。",
        "写一篇关于国产动画电影近年发展的评论。",
    ],
    "作文": [
        "请写一篇以'秋天的怀念'为主题的散文。",
        "以'我的理想'为题写一篇800字的文章。",
        "写一篇关于'坚持的力量'的议论文。",
    ],
    "学术": [
        "请撰写一段学术论文的方法部分，主题是深度学习在自然语言处理中的应用。",
        "写一段学术论文的引言部分，综述AI在教育中的研究现状。",
        "撰写一段实验分析，对比不同模型在文本分类任务上的表现。",
    ],
}


async def main():
    api_key = os.getenv("LLM_API_KEY", "sk-5fde2f682c194c8992f30fe91542fab9")
    api_base = os.getenv("LLM_API_BASE", "https://api.deepseek.com/v1")
    model = os.getenv("LLM_MODEL", "deepseek-chat")
    os.environ["NO_PROXY"] = "*"

    client = OpenAI(api_key=api_key, base_url=api_base)

    # 1. 生成 AI 文本
    print("=" * 60)
    print("C-ReD 风格基准测试 — AIGC--多模态检测器评估")
    print("=" * 60)

    ai_samples = []
    human_samples = []

    print("\n[1/3] 生成测试数据...")
    for domain, prompts in AI_PROMPTS.items():
        for prompt in prompts:
            try:
                r = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=400, temperature=0.9, timeout=15,
                )
                text = r.choices[0].message.content.strip()
                if len(text) > 30:
                    ai_samples.append({"domain": domain, "text": text, "label": 1})
                time.sleep(0.2)
            except Exception as e:
                print(f"  Gen Error [{domain}]: {e}")

    # 人类样本来自模板
    for domain, texts in HUMAN_TEMPLATES.items():
        for text in texts:
            human_samples.append({"domain": domain, "text": text, "label": 0})

    print(f"  AI: {len(ai_samples)}  Human: {len(human_samples)}")

    # 2. 运行检测
    print("\n[2/3] 运行检测...")
    from app.detectors.text.statistical_features import ChineseStatisticalExtractor
    from app.services.text_service import _statistical_to_output

    extractor = ChineseStatisticalExtractor()

    test_samples = ai_samples + human_samples
    random.shuffle(test_samples)

    results = []
    domain_stats = {}
    correct = 0
    total = 0

    for s in test_samples:
        feats = extractor.extract(s["text"])
        stat_out = _statistical_to_output(feats)
        predicted = stat_out.confidence > 0.5
        correct_pred = predicted == bool(s["label"])

        domain = s["domain"]
        if domain not in domain_stats:
            domain_stats[domain] = {"correct": 0, "total": 0, "tp": 0, "fp": 0, "tn": 0, "fn": 0}

        domain_stats[domain]["total"] += 1
        if correct_pred:
            domain_stats[domain]["correct"] += 1
        if s["label"] == 1 and predicted:
            domain_stats[domain]["tp"] += 1
        elif s["label"] == 0 and predicted:
            domain_stats[domain]["fp"] += 1
        elif s["label"] == 0 and not predicted:
            domain_stats[domain]["tn"] += 1
        elif s["label"] == 1 and not predicted:
            domain_stats[domain]["fn"] += 1

        total += 1
        if correct_pred: correct += 1
        results.append({"domain": domain, "actual": s["label"], "predicted": predicted, "confidence": stat_out.confidence})

    # 3. 输出报告
    print("\n[3/3] 基准测试报告")
    print("=" * 60)
    print(f"  总样本: {total}")
    print(f"  整体准确率: {correct/total:.1%}")
    print()
    print(f"  {'领域':<8} {'准确率':<8} {'精准率':<8} {'召回率':<8} {'F1':<8} {'样本':<6}")
    print(f"  {'-'*42}")

    overall_tp = overall_fp = overall_tn = overall_fn = 0
    for domain in ["新闻", "问答", "影评", "作文", "学术"]:
        ds = domain_stats.get(domain, {})
        tp = ds.get("tp", 0); fp = ds.get("fp", 0)
        tn = ds.get("tn", 0); fn = ds.get("fn", 0)
        overall_tp += tp; overall_fp += fp; overall_tn += tn; overall_fn += fn

        acc = ds.get("correct", 0) / max(ds.get("total", 1), 1)
        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        f1 = 2 * precision * recall / max(precision + recall, 0.01)
        n = ds.get("total", 0)
        print(f"  {domain:<8} {acc:<8.1%} {precision:<8.1%} {recall:<8.1%} {f1:<8.2f} {n:<6}")

    # 整体
    total_p = overall_tp + overall_fp + overall_tn + overall_fn
    overall_acc = (overall_tp + overall_tn) / max(total_p, 1)
    overall_prec = overall_tp / max(overall_tp + overall_fp, 1)
    overall_rec = overall_tp / max(overall_tp + overall_fn, 1)
    overall_f1 = 2 * overall_prec * overall_rec / max(overall_prec + overall_rec, 0.01)

    print(f"  {'-'*42}")
    print(f"  {'整体':<8} {overall_acc:<8.1%} {overall_prec:<8.1%} {overall_rec:<8.1%} {overall_f1:<8.2f} {total_p:<6}")

    # 保存结果
    output = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_samples": total,
        "overall": {"accuracy": round(overall_acc,4), "precision": round(overall_prec,4),
                     "recall": round(overall_rec,4), "f1": round(overall_f1,4)},
        "domains": {d: {"accuracy": round(ds.get("correct",0)/max(ds.get("total",1),1),4),
                         "samples": ds.get("total",0)}
                    for d, ds in domain_stats.items()},
    }
    Path("../data/benchmarks").mkdir(parents=True, exist_ok=True)
    path = f"../data/benchmarks/cred_test_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存: {path}")


if __name__ == "__main__":
    asyncio.run(main())
