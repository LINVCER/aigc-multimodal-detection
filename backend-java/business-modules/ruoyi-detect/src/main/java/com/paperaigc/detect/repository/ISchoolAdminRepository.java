package com.paperaigc.detect.repository;

import com.paperaigc.detect.domain.entity.EduSchool;
import com.paperaigc.detect.domain.entity.EduSchoolCrawlSeed;
import com.paperaigc.detect.domain.entity.EduSchoolRule;
import com.paperaigc.detect.domain.entity.EduSchoolRuleCandidate;

import java.util.List;
import java.util.Optional;

/** 后台：学校 / 种子 / 候选 / 规则维护 */
public interface ISchoolAdminRepository {

    // 学校
    List<EduSchool> listSchools(String q);
    void saveSchool(EduSchool s);          // id 空=insert，否则 update
    Optional<EduSchool> findSchool(Long id);

    // 种子
    List<EduSchoolCrawlSeed> listSeeds(Long schoolId);
    Optional<EduSchoolCrawlSeed> findSeed(Long id);
    void saveSeed(EduSchoolCrawlSeed seed);
    void touchSeed(Long id, String lastStatus);

    // 候选
    List<EduSchoolRuleCandidate> listCandidates(String status, Long schoolId);
    Optional<EduSchoolRuleCandidate> findCandidate(Long id);
    void updateCandidate(EduSchoolRuleCandidate c);

    // 规则
    long insertRule(EduSchoolRule rule);    // 返回生成 id
    void updateRule(EduSchoolRule rule);
    /** 某校某学位的全校级已发布规则（合并时 upsert 用） */
    Optional<EduSchoolRule> findPublishedWholeSchoolRule(Long schoolId, String degreeType);
}
