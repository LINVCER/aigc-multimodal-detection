package com.paperaigc.detect.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.paperaigc.detect.domain.entity.ParagraphResult;
import org.apache.ibatis.annotations.Mapper;

/**
 * detect_paragraph_result 表 Mapper（段级子表）
 */
@Mapper
public interface DetectParagraphResultMapper extends BaseMapper<ParagraphResult> {
}
