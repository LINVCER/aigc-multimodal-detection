package com.paperaigc.detect.domain.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * 复测对比视图（product-feature-plan §2.2）：当前任务 vs parent_task_id 指向的上一次
 *
 * <p>段落按文本相似度配对（字符二元组 Jaccard ≥ 0.35），配不上的分别记 new / removed。
 * 两次模型版本不同时 comparable=false，页面要明示不可直接比较。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TaskCompareVO {

    private Side current;
    private Side parent;
    /** 模型版本一致才可直接比较 */
    private boolean comparable;
    private Summary summary;
    private List<Row> rows;

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class Side {
        private Long id;
        private String paperTitle;
        private Double aiRate;
        private Integer threshold;
        private String modelVersion;
        private String createdAt;
        private int bodyParagraphs;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class Summary {
        /** aiRate 差值（当前 − 上次），百分点 */
        private Double deltaRate;
        private boolean pass;
        private int changed;
        private int down;
        private int up;
        private int added;
        private int removed;
        /** 一句话结论 */
        private String headline;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class Row {
        /** 当前段序号；removed 行为 null */
        private Integer currIdx;
        /** 上次段序号；added 行为 null */
        private Integer parentIdx;
        private String preview;
        private Double currProb;
        private Double parentProb;
        /** 概率差（当前 − 上次） */
        private Double delta;
        /** down / up / same / added / removed */
        private String status;
        /** 文本相似度 0-1 */
        private Double similarity;
    }
}
