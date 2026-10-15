package com.paperaigc.detect.domain.dto;

import lombok.Data;

/** 候选审核队列查询 */
@Data
public class CandidateQueryDTO {
    private String status;      // pending / merged / rejected，默认 pending
    private Long schoolId;
    private Integer pageNum;
    private Integer pageSize;
}
