package com.paperaigc.detect.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.paperaigc.detect.domain.entity.AdminUser;
import org.apache.ibatis.annotations.Mapper;

/**
 * user_profile 表 Mapper
 *
 * <p>继承 BaseMapper 拿到全套 CRUD + LambdaQueryWrapper 组合查询；
 * Repository 层将 Wrappers 组合封成业务方法，Service 不直接调 Mapper。</p>
 */
@Mapper
public interface AdminUserMapper extends BaseMapper<AdminUser> {
}
