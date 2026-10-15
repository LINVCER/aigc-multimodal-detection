package com.paperaigc.detect.service;

import com.paperaigc.detect.domain.vo.ResolvedRuleVO;
import com.paperaigc.detect.domain.vo.SchoolDetailVO;
import com.paperaigc.detect.domain.vo.SchoolVO;

import java.util.List;

/** 高校与红线 · 公开读 + 按用户解析 */
public interface ISchoolService {

    /** 学校搜索（公开查询页 / 选学校） */
    List<SchoolVO> search(String q, String province, String level);

    /** 学校详情 + 已发布红线（公开查询页 /schools/{id}） */
    SchoolDetailVO detail(Long id);

    /** 设置当前用户的学校与学位 */
    void setUserSchool(String bearerToken, Long schoolId, String degreeType);

    /** 当前用户生效的红线；未命中返回 resolved=false 的通用口径兜底 */
    ResolvedRuleVO resolveForUser(String bearerToken);

    /** 按 userId 解析生效红线（提交检测、助手回调用，没有 token 时走此） */
    ResolvedRuleVO resolveByUserId(Long userId);
}
