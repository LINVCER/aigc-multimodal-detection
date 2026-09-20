package com.paperaigc.detect.service;

import java.util.Map;

/**
 * 推理服务客户端
 *
 * <p>抽象层：当前 HttpInferenceClient；架构目标 GrpcInferenceClient（对应 #3 gRPC 落地），
 * 切换只换 @Primary bean。</p>
 * <p>方法都返回 Map 是因为 Python 侧 schema 短期还会变，跨语言以约定 key 交互；
 * schema 稳定后再补强类型 VO。</p>
 */
public interface IInferenceClient {

    /**
     * 段落 AI 检测（text 模态）
     * @param text 待检测文本
     * @param returnSentences 是否要句级明细
     * @return Python 原始响应（含 ai_prob / calibrated_prob / interval / sentences 等）
     */
    Map<String, Object> detectParagraph(String text, boolean returnSentences);

    /**
     * 音频 AI 检测（audio 模态）
     * @param audioBytes 音频文件字节流
     * @param filename 原始文件名（含后缀，供推理侧识别格式）
     * @param returnSegments 是否要片段级明细
     * @return Python 原始响应（含 ai_prob / calibrated_prob / interval / duration_sec / segments 等）
     */
    Map<String, Object> detectAudio(byte[] audioBytes, String filename, boolean returnSegments);

    /**
     * 图像 AI 检测（image 模态）
     * @param imageBytes 图片文件字节流
     * @param filename 原始文件名（含后缀，供推理侧识别格式）
     * @param returnRegions 是否要区域级明细
     * @return Python 原始响应（含 ai_prob / calibrated_prob / regions 等）
     */
    Map<String, Object> detectImage(byte[] imageBytes, String filename, boolean returnRegions);

    /**
     * 降 AIGC 改写
     * @param text 原文
     * @param style 风格 academic / casual / concise
     * @return Python 原始响应（rewritten_text / quality_score / model_version）
     */
    Map<String, Object> humanize(String text, String style);

    /**
     * 推理服务健康检查
     * @return Python /health 原始响应
     */
    Map<String, Object> health();
}
