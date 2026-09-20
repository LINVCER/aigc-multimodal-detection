package com.paperaigc.detect.domain.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 图像区域级检测结果
 *
 * <p>对齐 AudioSegmentResult：aiProb + calibratedProb 三元组；图像独有 bbox（x/y/w/h）。
 * 整图单结果时列表仅一个元素、bbox 为 null；未来接篡改/区域定位时同一列可扩展多个带 bbox 的区域。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ImageSegmentResult {

    /** 区域序号（0 起；整图=0） */
    private Integer segmentIdx;

    /** 区域 bbox 左上角 x（整图为 null；像素坐标，相对原图） */
    private Integer x;
    /** 区域 bbox 左上角 y */
    private Integer y;
    /** 区域 bbox 宽 */
    private Integer w;
    /** 区域 bbox 高 */
    private Integer h;

    /** 原始 AI 概率 */
    private Double aiProb;

    /** 校准后 AI 概率（前端展示与阈值判定用） */
    private Double calibratedProb;

    /** 疑似 AI 生成源（sd / flux / dalle / midjourney / human 等；模型就绪前 null） */
    private String sourceLabel;
}
