package com.paperaigc.detect.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.paperaigc.detect.domain.entity.DetectTask;
import org.apache.ibatis.annotations.Mapper;

/**
 * detect_task 表 Mapper（主表）
 *
 * <p>段落/句子子表由 DetectParagraphResultMapper / DetectSentenceResultMapper 独立管理。
 * Repository 层组合三 Mapper 完成主子表事务。</p>
 */
@Mapper
public interface DetectTaskMapper extends BaseMapper<DetectTask> {
}
