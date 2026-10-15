package com.paperaigc.detect.repository.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.paperaigc.detect.domain.entity.EduSchool;
import com.paperaigc.detect.domain.entity.EduSchoolRule;
import com.paperaigc.detect.mapper.EduSchoolMapper;
import com.paperaigc.detect.mapper.EduSchoolRuleMapper;
import com.paperaigc.detect.repository.ISchoolRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Primary;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/** edu_school / edu_school_rule · MyBatis-Plus 实现 */
@Primary
@Repository
@RequiredArgsConstructor
public class MybatisSchoolRepository implements ISchoolRepository {

    private final EduSchoolMapper schoolMapper;
    private final EduSchoolRuleMapper ruleMapper;

    @Override
    public List<EduSchool> search(String q, String province, String level, int limit) {
        LambdaQueryWrapper<EduSchool> w = Wrappers.lambdaQuery(EduSchool.class)
                .eq(EduSchool::getStatus, "active");
        if (q != null && !q.isBlank()) {
            w.and(x -> x.like(EduSchool::getName, q)
                    .or().like(EduSchool::getShortName, q)
                    .or().like(EduSchool::getAliases, q));
        }
        if (province != null && !province.isBlank()) w.eq(EduSchool::getProvince, province);
        if (level != null && !level.isBlank()) w.eq(EduSchool::getLevel, level);
        w.orderByAsc(EduSchool::getName).last("LIMIT " + Math.max(1, Math.min(limit, 50)));
        return schoolMapper.selectList(w);
    }

    @Override
    public Optional<EduSchool> findSchool(Long id) {
        return Optional.ofNullable(id == null ? null : schoolMapper.selectById(id));
    }

    @Override
    public List<EduSchoolRule> publishedRules(Long schoolId) {
        if (schoolId == null) return List.of();
        return ruleMapper.selectList(Wrappers.lambdaQuery(EduSchoolRule.class)
                .eq(EduSchoolRule::getSchoolId, schoolId)
                .eq(EduSchoolRule::getStatus, "published")
                .orderByAsc(EduSchoolRule::getDegreeType)
                .orderByDesc(EduSchoolRule::getConfidence));
    }

    @Override
    public Optional<EduSchoolRule> resolve(Long schoolId, String degreeType) {
        if (schoolId == null || degreeType == null || degreeType.isBlank()) return Optional.empty();
        List<EduSchoolRule> rows = ruleMapper.selectList(Wrappers.lambdaQuery(EduSchoolRule.class)
                .eq(EduSchoolRule::getSchoolId, schoolId)
                .eq(EduSchoolRule::getDegreeType, degreeType)
                .eq(EduSchoolRule::getStatus, "published")
                .isNull(EduSchoolRule::getCollege)
                .orderByDesc(EduSchoolRule::getConfidence)
                .orderByDesc(EduSchoolRule::getUpdatedAt)
                .last("LIMIT 1"));
        return rows.isEmpty() ? Optional.empty() : Optional.of(rows.get(0));
    }
}
