package com.paperaigc.detect.service;

import com.paperaigc.detect.domain.dto.CandidateMergeDTO;
import com.paperaigc.detect.domain.dto.CandidateQueryDTO;
import com.paperaigc.detect.domain.dto.CrawlSeedSaveDTO;
import com.paperaigc.detect.domain.dto.SchoolSaveDTO;
import com.paperaigc.detect.domain.entity.EduSchool;
import com.paperaigc.detect.domain.entity.EduSchoolCrawlSeed;
import com.paperaigc.detect.domain.entity.EduSchoolRuleCandidate;
import com.paperaigc.detect.domain.vo.PageVO;

import java.util.List;

/** 后台：学校红线管理与爬取数据维护（§12/§13） */
public interface ISchoolAdminService {

    // 学校
    List<EduSchool> listSchools(String q);
    void saveSchool(SchoolSaveDTO dto);
    void setSchoolStatus(Long id, String status);
    /** 手录 50 所：批量导入 */
    int importSchools(List<SchoolSaveDTO> list);

    // 爬取种子
    List<EduSchoolCrawlSeed> listSeeds(Long schoolId);
    void saveSeed(CrawlSeedSaveDTO dto);
    /** 立即爬取：投任务到常驻服务，回写 lastStatus */
    String runSeed(Long id);

    // 候选审核（数据维护）
    PageVO<EduSchoolRuleCandidate> pageCandidates(CandidateQueryDTO q);
    /** 合并发布为 edu_school_rule（人工确认，sourceUrl 必填），标候选 merged，返回规则 id */
    long mergeCandidate(Long candidateId, CandidateMergeDTO dto, Long operatorId);
    void rejectCandidate(Long candidateId);
}
