package com.paperaigc.detect.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.paperaigc.detect.domain.entity.UserAccount;
import org.apache.ibatis.annotations.Mapper;

/**
 * auth_user 表 Mapper
 */
@Mapper
public interface UserAccountMapper extends BaseMapper<UserAccount> {
}
