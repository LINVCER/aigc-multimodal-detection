"""
准备 AIGC 检测训练数据：HC3 英文解析 + DeepSeek API 生成中文 + 合并

用法:
  python prepare_training_data.py
"""

import json, random, time, os, sys
from pathlib import Path
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def parse_hc3(filepath: str) -> list[dict]:
    """解析 HC3 all.jsonl 为正负样本"""
    samples = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            question = item.get("question", "")
            human_answers = item.get("human_answers", [])
            chatgpt_answers = item.get("chatgpt_answers", [])
            for ans in human_answers:
                if len(ans) > 30:
                    samples.append({"domain": "hc3", "text": ans, "label": 0})
            for ans in chatgpt_answers:
                if len(ans) > 30:
                    samples.append({"domain": "hc3", "text": ans, "label": 1})
    return samples


def generate_chinese_data(client: OpenAI, model: str, num: int = 500) -> list[dict]:
    """用 DeepSeek API 生成中文训练数据"""
    from generate_training_data import PROMPTS

    all_prompts = []
    for domain, prompts in PROMPTS.items():
        for p in prompts:
            all_prompts.append((domain, p))

    random.shuffle(all_prompts)
    all_prompts = all_prompts[:min(num, len(all_prompts))]

    samples = []
    print(f"\nGenerating {len(all_prompts)} Chinese samples via {model}...")

    for i, (domain, prompt) in enumerate(all_prompts):
        try:
            # AI 风格
            r = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是一个AI助手，请用中文给出详细正式的回答。"},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=600, temperature=0.9,
            )
            ai_text = r.choices[0].message.content.strip()

            # 人类风格
            r2 = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "请模仿人类口语化表达回答，自然随意，用第一人称，避免正式结构。"},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=400, temperature=1.2,
            )
            human_text = r2.choices[0].message.content.strip()

            if len(ai_text) > 20:
                samples.append({"domain": domain, "text": ai_text, "label": 1})
            if len(human_text) > 20:
                samples.append({"domain": domain, "text": human_text, "label": 0})

            if (i + 1) % 10 == 0:
                print(f"  [{i+1}/{len(all_prompts)}] {domain}: {len(samples)} samples so far")
            time.sleep(0.3)

        except Exception as e:
            print(f"  [{i+1}] ERROR: {e}")
            time.sleep(2)

    return samples


def main():
    api_key = os.getenv("LLM_API_KEY", "")
    api_base = os.getenv("LLM_API_BASE", "https://api.deepseek.com/v1")
    model = os.getenv("LLM_MODEL", "deepseek-chat")
    client = OpenAI(api_key=api_key, base_url=api_base)

    output_dir = Path("../data/training")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: HC3 英文
    print("Parsing HC3 English data...")
    hc3_path = "../data/HC3_all.jsonl"
    en_samples = parse_hc3(hc3_path) if os.path.exists(hc3_path) else []
    print(f"  HC3 English: {len(en_samples)} samples ({sum(1 for s in en_samples if s['label']==0)} human, {sum(1 for s in en_samples if s['label']==1)} AI)")

    # Step 2: DeepSeek 生成中文
    zh_samples = generate_chinese_data(client, model, num=500)
    print(f"  Generated Chinese: {len(zh_samples)} samples ({sum(1 for s in zh_samples if s['label']==0)} human, {sum(1 for s in zh_samples if s['label']==1)} AI)")

    # Step 3: 合并 + 去重
    all_samples = en_samples + zh_samples
    random.shuffle(all_samples)

    # 按8:2划分
    split = int(len(all_samples) * 0.8)
    train = all_samples[:split]
    val = all_samples[split:]

    for name, data in [("train", train), ("val", val)]:
        path = output_dir / f"aigc_bilingual_{name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        ai = sum(1 for s in data if s["label"] == 1)
        human = sum(1 for s in data if s["label"] == 0)
        print(f"\n  {name}: {len(data)} samples ({human} human, {ai} AI) -> {path}")

    print(f"\nDone! Total: {len(all_samples)} samples")


if __name__ == "__main__":
    main()
