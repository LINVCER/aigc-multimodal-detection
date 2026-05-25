"""
中文 AIGC 检测训练数据生成器

用 DeepSeek API 批量生成覆盖四领域的 AI 合成文本 + 配对人类文本
生成约 2000+ 条训练样本

用法:
  python generate_training_data.py --num_samples 2000
"""

import os, sys, json, time, random, argparse
from pathlib import Path
from datetime import datetime

from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ============================================================
# 中文问题/主题库 (覆盖四领域)
# ============================================================

PROMPTS = {
    "教育": [
        "请写一篇800字左右的议论文，题目是《论人工智能对高等教育的影响》。",
        "解释什么是深度学习中的反向传播算法，并举例说明。",
        "如何看待大学生使用ChatGPT写作业的现象？请写一篇评论。",
        "简述中国古代科举制度的演变及其对现代教育的影响。",
        "写一份关于《红楼梦》中林黛玉人物形象的分析。",
        "谈谈你对'双减'政策的理解和看法。",
        "写一篇关于量子计算原理的科普文章，面向高中生。",
        "比较东西方教育理念的差异，并分析各自的优缺点。",
    ],
    "新闻": [
        "撰写一篇关于新能源汽车产业发展的新闻报道。",
        "写一篇关于城市垃圾分类政策实施效果的调查报道。",
        "请以新闻评论的方式，分析当前互联网平台的垄断问题。",
        "写一篇关于中国航天事业最新进展的通讯稿。",
        "撰写一篇关于人工智能伦理监管的深度报道。",
        "写一篇关于乡村振兴战略实施情况的新闻稿。",
        "分析当前全球经济形势及其对中国出口贸易的影响。",
        "写一篇关于食品安全监管体系改革的专题报道。",
    ],
    "科技": [
        "详细解释Transformer架构的工作原理及其在NLP中的应用。",
        "比较PyTorch和TensorFlow两个深度学习框架的优缺点。",
        "写一篇关于Web 3.0和去中心化技术的科普文章。",
        "谈谈你对大语言模型未来发展方向的理解。",
        "解释区块链技术的基本原理及其在供应链管理中的应用。",
        "分析5G技术对物联网发展的推动作用。",
        "写一篇关于数据库技术从SQL到NoSQL演变的技术博客。",
        "介绍计算机视觉领域的目标检测算法发展历程。",
    ],
    "文学": [
        "写一篇以'秋天的怀念'为主题的散文。",
        "请以'城市的夜晚'为题，创作一篇800字的随笔。",
        "写一篇关于友情的短文，要有具体的细节和情感。",
        "分析小说《活着》中的叙事技巧和主题思想。",
        "写一篇以'故乡的小河'为题的抒情散文。",
        "谈谈现代诗歌的语言特点和发展趋势。",
        "写一篇影评，分析电影《流浪地球》的科幻元素和人文关怀。",
        "请创作一篇以'钟声'为意象的微型小说。",
    ],
    # 短问题 (用于生成更多变体)
    "短问答": [
        "什么是机器学习？",
        "为什么天空是蓝色的？",
        "如何提高学习效率？",
        "中国最大的城市是哪个？",
        "光合作用的过程是什么？",
        "如何看待远程办公的优缺点？",
        "什么是碳中和？",
        "水的沸点受什么因素影响？",
        "如何准备一场成功的面试？",
        "PM2.5对人体的危害有哪些？",
        "什么叫供给侧改革？",
        "5G和4G的主要区别是什么？",
        "如何培养良好的阅读习惯？",
        "太阳系有几大行星？",
        "什么是物联网？",
        "如何看待直播带货的兴起？",
        "垃圾分类的意义是什么？",
        "什么是快闪记忆法？",
        "中医和西医的主要区别？",
        "如何在家进行有效的体育锻炼？",
    ],
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--num_samples", type=int, default=1000)
    parser.add_argument("--output_dir", default="../data/training")
    args = parser.parse_args()

    # 读取 API 配置
    api_key = os.getenv("LLM_API_KEY", "")
    api_base = os.getenv("LLM_API_BASE", "https://api.deepseek.com/v1")
    model = os.getenv("LLM_MODEL", "deepseek-chat")

    client = OpenAI(api_key=api_key, base_url=api_base)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ai_samples = []
    human_samples = []

    # 收集所有 prompts
    all_prompts = []
    for domain, prompts in PROMPTS.items():
        for p in prompts:
            all_prompts.append((domain, p))

    # 随机抽取 num_samples 个
    random.shuffle(all_prompts)
    target = min(args.num_samples, len(all_prompts))

    print(f"Generating {target} AI samples via {model}...")
    print(f"API: {api_base}\n")

    for i, (domain, prompt) in enumerate(all_prompts[:target]):
        try:
            # 生成 AI 风格的详细回答
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是一个有用的AI助手。请用中文给出详细、正式的回复。"},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=800,
                temperature=0.9,
            )
            ai_text = response.choices[0].message.content.strip()

            # 同时生成一个人类风格的简短/随意回答(用 low temp 加提示)
            response2 = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "请模仿人类的口语化表达方式回答问题，要自然随意，可以用第一人称，可以加入个人感受和经历，避免过于正式和结构化。"},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=500,
                temperature=1.2,
            )
            human_style = response2.choices[0].message.content.strip()

            ai_samples.append({
                "domain": domain,
                "prompt": prompt,
                "text": ai_text,
                "label": 1,
            })
            human_samples.append({
                "domain": domain,
                "prompt": prompt,
                "text": human_style,
                "label": 0,
            })

            print(f"  [{i+1}/{target}] {domain}: {prompt[:50]}... (AI={len(ai_text)}ch, H={len(human_style)}ch)")

            # 速率限制
            time.sleep(0.5)

        except Exception as e:
            print(f"  [{i+1}/{target}] ERROR: {e}")
            time.sleep(2)

    # 保存
    train_data = ai_samples + human_samples
    random.shuffle(train_data)

    train_size = int(len(train_data) * 0.8)
    train = train_data[:train_size]
    val = train_data[train_size:]

    for split_name, split_data in [("train", train), ("val", val)]:
        out_file = output_dir / f"aigc_chinese_{split_name}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(split_data, f, ensure_ascii=False, indent=2)
        ai_count = sum(1 for s in split_data if s["label"] == 1)
        human_count = sum(1 for s in split_data if s["label"] == 0)
        print(f"\n{splits_name}: {len(splits_data)} samples ({ai_count} AI, {human_count} human) -> {out_file}")

    print(f"\nDone! Total: {len(train_data)} samples")


if __name__ == "__main__":
    main()
