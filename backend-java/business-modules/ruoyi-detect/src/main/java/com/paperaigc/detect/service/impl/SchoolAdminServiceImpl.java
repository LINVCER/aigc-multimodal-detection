package com.paperaigc.detect.service.impl;

import com.paperaigc.detect.domain.dto.CandidateMergeDTO;
import com.paperaigc.detect.domain.dto.CandidateQueryDTO;
import com.paperaigc.detect.domain.dto.CrawlSeedSaveDTO;
import com.paperaigc.detect.domain.dto.SchoolSaveDTO;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.paperaigc.detect.domain.entity.EduSchool;
import com.paperaigc.detect.domain.entity.EduSchoolCrawlSeed;
import com.paperaigc.detect.domain.entity.EduSchoolRule;
import com.paperaigc.detect.domain.entity.EduSchoolRuleCandidate;
import com.paperaigc.detect.domain.entity.KnowledgeChunk;
import com.paperaigc.detect.domain.vo.PageVO;
import com.paperaigc.detect.mapper.KnowledgeChunkMapper;
import com.paperaigc.detect.repository.ISchoolAdminRepository;
import com.paperaigc.detect.service.ISchoolAdminService;

import java.math.BigDecimal;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 后台学校红线管理实现。
 *
 * <p>本轮决策：候选一律人工审核才发布；合并发布的规则 sourceUrl 必填、source_type=official、记 verifiedBy。</p>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class SchoolAdminServiceImpl implements ISchoolAdminService {

    private final ISchoolAdminRepository repo;
    private final CrawlerClient crawlerClient;
    private final KnowledgeChunkMapper knowledgeChunkMapper;

    @Override
    public List<EduSchool> listSchools(String q) {
        return repo.listSchools(q);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void saveSchool(SchoolSaveDTO dto) {
        EduSchool s = EduSchool.builder()
                .id(dto.getId()).name(dto.getName()).shortName(dto.getShortName())
                .aliases(dto.getAliases()).province(dto.getProvince())
                .level(dto.getLevel() == null || dto.getLevel().isBlank() ? "undergrad" : dto.getLevel())
                .logoUrl(dto.getLogoUrl())
                .build();
        if (dto.getId() == null) {
            s.setStatus("active");
        } else {  // 编辑不动 status，由 setSchoolStatus 管
            EduSchool exist = repo.findSchool(dto.getId()).orElseThrow(() -> new IllegalArgumentException("学校不存在"));
            s.setStatus(exist.getStatus());
        }
        repo.saveSchool(s);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void setSchoolStatus(Long id, String status) {
        EduSchool s = repo.findSchool(id).orElseThrow(() -> new IllegalArgumentException("学校不存在"));
        s.setStatus("hidden".equals(status) ? "hidden" : "active");
        repo.saveSchool(s);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public int importSchools(List<SchoolSaveDTO> list) {
        if (list == null || list.isEmpty()) return 0;
        int n = 0;
        for (SchoolSaveDTO d : list) {
            if (d.getName() == null || d.getName().isBlank()) continue;
            d.setId(null);
            saveSchool(d);
            n++;
        }
        log.info("import schools: {}", n);
        return n;
    }

    @Override
    public List<EduSchoolCrawlSeed> listSeeds(Long schoolId) {
        return repo.listSeeds(schoolId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void saveSeed(CrawlSeedSaveDTO dto) {
        EduSchoolCrawlSeed seed = EduSchoolCrawlSeed.builder()
                .id(dto.getId()).schoolId(dto.getSchoolId()).entryUrl(dto.getEntryUrl())
                .adapter(dto.getAdapter() == null || dto.getAdapter().isBlank() ? "generic" : dto.getAdapter())
                .enabled(dto.getEnabled() == null ? 1 : dto.getEnabled())
                .note(dto.getNote())
                .build();
        repo.saveSeed(seed);
    }

    @Override
    public String runSeed(Long id) {
        EduSchoolCrawlSeed seed = repo.findSeed(id).orElseThrow(() -> new IllegalArgumentException("种子不存在"));
        String job = crawlerClient.submit(seed.getSchoolId(), null, seed.getEntryUrl(), seed.getAdapter(), true);
        repo.touchSeed(id, job == null ? "投递失败（服务未起？）" : ("已投递 " + job));
        return job;
    }

    @Override
    public PageVO<EduSchoolRuleCandidate> pageCandidates(CandidateQueryDTO q) {
        String status = q.getStatus() == null || q.getStatus().isBlank() ? "pending" : q.getStatus();
        List<EduSchoolRuleCandidate> all = repo.listCandidates(status, q.getSchoolId());
        int total = all.size();
        int pageNum = q.getPageNum() == null || q.getPageNum() < 1 ? 1 : q.getPageNum();
        int pageSize = q.getPageSize() == null || q.getPageSize() < 1 ? 20 : q.getPageSize();
        int from = Math.max(0, (pageNum - 1) * pageSize);
        int to = Math.min(total, from + pageSize);
        return PageVO.of(total, from >= total ? List.of() : all.subList(from, to));
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public long mergeCandidate(Long candidateId, CandidateMergeDTO dto, Long operatorId) {
        EduSchoolRuleCandidate c = repo.findCandidate(candidateId).orElseThrow(() -> new IllegalArgumentException("候选不存在"));
        if (dto.getSchoolId() == null) throw new IllegalArgumentException("请先指定学校");
        if (dto.getDegreeType() == null || dto.getDegreeType().isBlank()) throw new IllegalArgumentException("请指定学位");
        String sourceUrl = dto.getSourceUrl() != null && !dto.getSourceUrl().isBlank() ? dto.getSourceUrl() : c.getSourceUrl();
        if (sourceUrl == null || sourceUrl.isBlank()) throw new IllegalArgumentException("必须带原文地址");

        // 全校级 upsert：已有同校同学位 published 规则则补字段，否则新建
        EduSchoolRule rule = (dto.getCollege() == null || dto.getCollege().isBlank())
                ? repo.findPublishedWholeSchoolRule(dto.getSchoolId(), dto.getDegreeType()).orElse(null) : null;
        long ruleId;
        LocalDateTime now = LocalDateTime.now();
        if (rule == null) {
            rule = EduSchoolRule.builder()
                    .schoolId(dto.getSchoolId()).college(emptyToNull(dto.getCollege())).degreeType(dto.getDegreeType())
                    .aiRateLimit(dto.getAiRateLimit()).plagiarismLimit(dto.getPlagiarismLimit())
                    .platform(dto.getPlatform()).sourceType("official").sourceUrl(sourceUrl)
                    .effectiveYear(dto.getEffectiveYear()).confidence(100).status("published")
                    .verifiedBy(operatorId).verifiedAt(now).createdAt(now).updatedAt(now).build();
            ruleId = repo.insertRule(rule);
        } else {
            if (dto.getAiRateLimit() != null) rule.setAiRateLimit(dto.getAiRateLimit());
            if (dto.getPlagiarismLimit() != null) rule.setPlagiarismLimit(dto.getPlagiarismLimit());
            if (dto.getPlatform() != null) rule.setPlatform(dto.getPlatform());
            if (dto.getEffectiveYear() != null) rule.setEffectiveYear(dto.getEffectiveYear());
            rule.setSourceUrl(sourceUrl);
            rule.setVerifiedBy(operatorId);
            rule.setVerifiedAt(now);
            rule.setUpdatedAt(now);
            repo.updateRule(rule);
            ruleId = rule.getId();
        }
        c.setStatus("merged");
        c.setMergedRuleId(ruleId);
        repo.updateCandidate(c);
        mirrorToKnowledge(rule);   // §14 规则 → 知识库，小白 search_knowledge 可召回
        log.info("merge candidate {} -> rule {} by {}", candidateId, ruleId, operatorId);
        return ruleId;
    }

    /** 已发布规则镜像一条知识库块（doc=school-redline，uk_doc_title 幂等 upsert） */
    private void mirrorToKnowledge(EduSchoolRule rule) {
        try {
            EduSchool s = repo.findSchool(rule.getSchoolId()).orElse(null);
            if (s == null) return;
            String shortName = s.getShortName() != null && !s.getShortName().isBlank() ? s.getShortName() : s.getName();
            String degCn = degreeCn(rule.getDegreeType());
            String title = shortName + "-" + degCn + "红线";
            StringBuilder body = new StringBuilder(s.getName()).append(" ").append(degCn).append("学位论文：");
            if (rule.getAiRateLimit() != null) body.append("AIGC 率不超过 ").append(trim(rule.getAiRateLimit())).append("%；");
            if (rule.getPlagiarismLimit() != null) body.append("查重率不超过 ").append(trim(rule.getPlagiarismLimit())).append("%；");
            if (rule.getPlatform() != null && !rule.getPlatform().isBlank()) body.append("检测平台 ").append(rule.getPlatform()).append("；");
            if (rule.getEffectiveYear() != null) body.append(rule.getEffectiveYear()).append(" 届；");
            if (rule.getSourceUrl() != null && !rule.getSourceUrl().isBlank()) body.append("来源：").append(rule.getSourceUrl());
            String tags = String.join(",", shortName, s.getName(), degCn, "学校红线", "AI率", "查重");

            KnowledgeChunk exist = knowledgeChunkMapper.selectOne(Wrappers.lambdaQuery(KnowledgeChunk.class)
                    .eq(KnowledgeChunk::getDoc, "school-redline").eq(KnowledgeChunk::getTitle, title).last("LIMIT 1"));
            boolean published = "published".equals(rule.getStatus());
            if (exist == null) {
                knowledgeChunkMapper.insert(KnowledgeChunk.builder()
                        .doc("school-redline").title(title).tags(tags).body(body.toString())
                        .sortOrder(0).enabled(published)
                        .createdAt(LocalDateTime.now()).updatedAt(LocalDateTime.now()).build());
            } else {
                exist.setTags(tags);
                exist.setBody(body.toString());
                exist.setEnabled(published);
                exist.setUpdatedAt(LocalDateTime.now());
                knowledgeChunkMapper.updateById(exist);
            }
        } catch (Exception e) {
            log.warn("mirror rule {} to knowledge failed: {}", rule.getId(), e.getMessage());
        }
    }

    private static String trim(BigDecimal v) {
        return v.stripTrailingZeros().toPlainString();
    }

    private static String degreeCn(String degree) {
        return switch (degree == null ? "" : degree) {
            case "bachelor" -> "本科";
            case "master" -> "硕士";
            case "phd" -> "博士";
            default -> degree;
        };
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void rejectCandidate(Long candidateId) {
        EduSchoolRuleCandidate c = repo.findCandidate(candidateId).orElseThrow(() -> new IllegalArgumentException("候选不存在"));
        c.setStatus("rejected");
        repo.updateCandidate(c);
    }

    private static String emptyToNull(String s) {
        return s == null || s.isBlank() ? null : s;
    }
}
