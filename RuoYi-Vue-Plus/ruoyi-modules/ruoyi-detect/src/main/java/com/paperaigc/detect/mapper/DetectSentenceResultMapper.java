package com.paperaigc.detect.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.paperaigc.detect.domain.entity.SentenceResult;
import org.apache.ibatis.annotations.Mapper;

/**
 * detect_sentence_result 表 Mapper（句级子表）
 */
@Mapper
public interface DetectSentenceResultMapper extends BaseMapper<SentenceResult> {
}
