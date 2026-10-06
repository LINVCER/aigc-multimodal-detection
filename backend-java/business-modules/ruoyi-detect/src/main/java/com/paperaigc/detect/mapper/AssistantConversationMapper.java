package com.paperaigc.detect.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.paperaigc.detect.domain.entity.AssistantConversation;
import org.apache.ibatis.annotations.Mapper;

/**
 * assistant_conversation 表 Mapper（只读）
 */
@Mapper
public interface AssistantConversationMapper extends BaseMapper<AssistantConversation> {
}
