package com.paperaigc.detect.repository.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.paperaigc.detect.domain.entity.EduSchool;
import com.paperaigc.detect.domain.entity.EduSchoolCrawlSeed;
import com.paperaigc.detect.domain.entity.EduSchoolRule;
import com.paperaigc.detect.domain.entity.EduSchoolRuleCandidate;
import com.paperaigc.detect.mapper.EduSchoolCrawlSeedMapper;
import com.paperaigc.detect.mapper.EduSchoolMapper;
import com.paperaigc.detect.mapper.EduSchoolRuleCandidateMapper;
import com.paperaigc.detect.mapper.EduSchoolRuleMapper;
import com.paperaigc.detect.repository.ISchoolAdminRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Primary;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

/** 后台学校红线维护 · MyBatis-Plus 实现 */
@Primary
@Repository
@RequiredArgsConstructor
public class MybatisSchoolAdminRepository implements ISchoolAdminRepository {

    private final EduSchoolMapper schoolMapper;
    private final EduSchoolRuleMapper ruleMapper;
    private final EduSchoolRuleCandidateMapper candidateMapper;
    private final EduSchoolCrawlSeedMapper seedMapper;

    @Override
    public List<EduSchool> listSchools(String q) {
        LambdaQueryWrapper<EduSchool> w = Wrappers.lambdaQuery(EduSchool.class);
        if (q != null && !q.isBlank()) {
            w.and(x -> x.like(EduSchool::getName, q).or().like(EduSchool::getShortName, q).or().like(EduSchool::getAliases, q));
        }
        w.orderByDesc(EduSchool::getUpdatedAt);
        return schoolMapper.selectList(w);
    }

    @Override
    public void saveSchool(EduSchool s) {
        if (s.getId() == null) schoolMapper.insert(s);
        else schoolMapper.updateById(s);
    }

    @Override
    public Optional<EduSchool> findSchool(Long id) {
        return Optional.ofNullable(id == null ? null : schoolMapper.selectById(id));
    }

    @Override
    public List<EduSchoolCrawlSeed> listSeeds(Long schoolId) {
        LambdaQueryWrapper<EduSchoolCrawlSeed> w = Wrappers.lambdaQuery(EduSchoolCrawlSeed.class);
        if (schoolId != null) w.eq(EduSchoolCrawlSeed::getSchoolId, schoolId);
        w.orderByDesc(EduSchoolCrawlSeed::getUpdatedAt);
        return seedMapper.selectList(w);
    }

    @Override
    public Optional<EduSchoolCrawlSeed> findSeed(Long id) {
        return Optional.ofNullable(id == null ? null : seedMapper.selectById(id));
    }

    @Override
    public void saveSeed(EduSchoolCrawlSeed seed) {
        if (seed.getId() == null) seedMapper.insert(seed);
        else seedMapper.updateById(seed);
    }

    @Override
    public void touchSeed(Long id, String lastStatus) {
        EduSchoolCrawlSeed s = seedMapper.selectById(id);
        if (s == null) return;
        s.setLastCrawlAt(LocalDateTime.now());
        s.setLastStatus(lastStatus);
        seedMapper.updateById(s);
    }

    @Override
    public List<EduSchoolRuleCandidate> listCandidates(String status, Long schoolId) {
        LambdaQueryWrapper<EduSchoolRuleCandidate> w = Wrappers.lambdaQuery(EduSchoolRuleCandidate.class);
        if (status != null && !status.isBlank()) w.eq(EduSchoolRuleCandidate::getStatus, status);
        if (schoolId != null) w.eq(EduSchoolRuleCandidate::getSchoolId, schoolId);
        w.orderByDesc(EduSchoolRuleCandidate::getConfidence).orderByDesc(EduSchoolRuleCandidate::getId);
        return candidateMapper.selectList(w);
    }

    @Override
    public Optional<EduSchoolRuleCandidate> findCandidate(Long id) {
        return Optional.ofNullable(id == null ? null : candidateMapper.selectById(id));
    }

    @Override
    public void updateCandidate(EduSchoolRuleCandidate c) {
        candidateMapper.updateById(c);
    }

    @Override
    public boolean candidateExists(String contentHash) {
        if (contentHash == null || contentHash.isBlank()) return false;
        return candidateMapper.selectCount(Wrappers.lambdaQuery(EduSchoolRuleCandidate.class)
                .eq(EduSchoolRuleCandidate::getContentHash, contentHash)) > 0;
    }

    @Override
    public void insertCandidate(EduSchoolRuleCandidate c) {
        candidateMapper.insert(c);
    }

    @Override
    public long insertRule(EduSchoolRule rule) {
        ruleMapper.insert(rule);
        return rule.getId();
    }

    @Override
    public void updateRule(EduSchoolRule rule) {
        ruleMapper.updateById(rule);
    }

    @Override
    public Optional<EduSchoolRule> findPublishedWholeSchoolRule(Long schoolId, String degreeType) {
        if (schoolId == null || degreeType == null) return Optional.empty();
        List<EduSchoolRule> rows = ruleMapper.selectList(Wrappers.lambdaQuery(EduSchoolRule.class)
                .eq(EduSchoolRule::getSchoolId, schoolId)
                .eq(EduSchoolRule::getDegreeType, degreeType)
                .eq(EduSchoolRule::getStatus, "published")
                .isNull(EduSchoolRule::getCollege)
                .last("LIMIT 1"));
        return rows.isEmpty() ? Optional.empty() : Optional.of(rows.get(0));
    }
}
