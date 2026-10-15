package com.paperaigc.detect.repository;

import com.paperaigc.detect.domain.entity.EduSchool;
import com.paperaigc.detect.domain.entity.EduSchoolRule;

import java.util.List;
import java.util.Optional;

/** 高校与红线查询仓储（公开读 + 按校解析） */
public interface ISchoolRepository {

    /** 按关键词（name/shortName/aliases）+ 省份 + 层次搜索启用的学校 */
    List<EduSchool> search(String q, String province, String level, int limit);

    Optional<EduSchool> findSchool(Long id);

    /** 某校已发布规则，按学位 + 置信度排序 */
    List<EduSchoolRule> publishedRules(Long schoolId);

    /**
     * 解析某校某学位的全校级已发布红线（college 为空），取置信度最高、最新的一条。
     * @return 命中返回规则，否则 empty（走通用口径兜底）
     */
    Optional<EduSchoolRule> resolve(Long schoolId, String degreeType);
}
