"""
完整文本检测管线测试 — 下载模型 + 运行真实检测
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio


async def main():
    print("=" * 60)
    print("ImageNious 文本检测管线测试")
    print("=" * 60)

    # ---------- Step 1: 测试数据集 ----------
    human_text = """
作为一个从小在农村长大的孩子，我对土地有着特别深的感情。
记得小时候，每到夏天，村里的孩子们就会一起去河边捉鱼摸虾。
那时候没有手机，但我们从来不觉得无聊。一个竹竿子，一根棉线，
就能钓上半天。奶奶总说我是个野孩子，晒得跟泥鳅似的。
说实话，现在的孩子们虽然物质条件好了，但少了我们那时候的自由自在。
"""

    ai_text_gpt = """
随着人工智能技术的飞速发展，深度学习在自然语言处理领域取得了
显著进展。值得注意的是，大型语言模型如GPT-4已经能够生成高质量的
文本内容。然而，这些技术的广泛应用也带来了一系列挑战，例如学术
诚信问题和虚假信息传播风险。因此，开发有效的AIGC检测工具变得
尤为重要。进一步来说，我们必须认识到，AIGC检测不仅是一个技术
问题，更是一个涉及教育伦理和社会信任的综合性议题。
"""

    ai_text_claude = """
坦率地说，这是一个很好的问题。让我来解释一下我的理解。
首先，从技术角度来看，深度学习的本质是通过多层神经网络对
海量数据进行特征提取和模式识别。其次，在应用层面，我们需要
考虑模型的泛化能力和鲁棒性。我想补充的是，在实际部署中，
数据隐私和模型安全同样值得深入思考。当然，这并不意味着传统
方法就完全没有价值——事实上，结合符号推理和统计学习的混合
方法正在成为一个值得关注的方向。
"""

    # ---------- Step 2: 统计特征提取 ----------
    print("\n[1] 统计特征提取器 (无需模型下载)...")
    from app.detectors.text.statistical_features import ChineseStatisticalExtractor

    extractor = ChineseStatisticalExtractor()

    for name, text in [("人类写作", human_text), ("GPT-4o生成", ai_text_gpt), ("Claude生成", ai_text_claude)]:
        features = extractor.extract(text)
        print(f"\n  {name}:")
        print(f"    n-gram熵: uni={features.unigram_entropy:.2f} bi={features.bigram_entropy:.2f} tri={features.trigram_entropy:.2f}")
        print(f"    成语密度: {features.idiom_density:.4f}")
        print(f"    句长CV:   {features.sentence_length_cv:.4f}")
        print(f"    Burstiness: {features.burstiness:.4f}")
        print(f"    Zipf偏差: {features.zipf_deviation:.4f}")
        print(f"    Slop词密度: {features.slop_word_density:.4f}")
        print(f"    过渡词密度: {features.transition_word_density:.4f}")
        print(f"    Hapax比率: {features.hapax_ratio:.4f}")
        print(f"    Yule's K: {features.yule_k:.2f}")
        print(f"    标点熵:   {features.punctuation_entropy:.2f}")

    # ---------- Step 3: 信号融合检测 ----------
    print("\n[2] Sigmoid 信号融合判定...")
    from app.services.text_service import _statistical_to_output

    for name, text in [("人类写作", human_text), ("GPT-4o", ai_text_gpt), ("Claude", ai_text_claude)]:
        features = extractor.extract(text)
        output = _statistical_to_output(features)
        verdict = "AI生成" if output.is_ai_generated else "人类写作"
        print(f"  {name}: {verdict} | 置信度={output.confidence:.4f} | logit={output.logit:.4f}")

    # ---------- Step 4: 完整检测流程 ----------
    print("\n[3] 完整检测服务 (text_service)...")
    from app.services.text_service import detect_text

    result = await detect_text(human_text, {"explain": True, "attribution": True})
    print(f"\n  人类文本检测结果:")
    print(f"    判定: {'AI生成' if result.is_ai_generated else '人类写作'}")
    print(f"    置信度: {result.confidence:.4f}")
    print(f"    校准置信度: {result.calibrated_confidence}")
    print(f"    置信区间: {result.confidence_interval}")
    print(f"    融合分支数: {result.metadata.get('available_branches', 'N/A')}")
    print(f"    可疑片段数: {len(result.explanation_data.get('text_snippets', []))}")

    result2 = await detect_text(ai_text_gpt, {"explain": True, "attribution": True})
    print(f"\n  GPT-4o文本检测结果:")
    print(f"    判定: {'AI生成' if result2.is_ai_generated else '人类写作'}")
    print(f"    置信度: {result2.confidence:.4f}")
    print(f"    可疑片段数: {len(result2.explanation_data.get('text_snippets', []))}")
    if result2.explanation_data.get("text_snippets"):
        for span in result2.explanation_data["text_snippets"][:5]:
            txt = ai_text_gpt[span["start"]:span["end"]]
            print(f"    -> [{span['reason']}] \"{txt}\" -- {span.get('detail', '')}")

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
