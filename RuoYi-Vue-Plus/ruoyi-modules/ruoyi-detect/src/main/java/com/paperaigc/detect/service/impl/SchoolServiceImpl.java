package com.paperaigc.detect.service.impl;

import com.paperaigc.detect.domain.entity.AuthUser;
import com.paperaigc.detect.domain.entity.EduSchool;
import com.paperaigc.detect.domain.entity.EduSchoolRule;
import com.paperaigc.detect.domain.entity.UserAccount;
import com.paperaigc.detect.domain.vo.ResolvedRuleVO;
import com.paperaigc.detect.domain.vo.SchoolDetailVO;
import com.paperaigc.detect.domain.vo.SchoolRuleVO;
import com.paperaigc.detect.domain.vo.SchoolVO;
import com.paperaigc.detect.mapper.UserAccountMapper;
import com.paperaigc.detect.repository.ISchoolRepository;
import com.paperaigc.detect.service.IAuthService;
import com.paperaigc.detect.service.ISchoolService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Set;

/**
 * 高校与红线服务实现。
 *
 * <p>按校解析顺序见 202610-school-redline-plan.md §3：这里负责「学校规则 → 通用口径兜底」，
 * 场景级默认阈值仍由 {@link IScenarioThresholdService} 提供，调用方（提交检测）按需拼接。</p>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class SchoolServiceImpl implements ISchoolService {

    private static final Set<String> DEGREES = Set.of("bachelor", "master", "phd");
    private static final String[] DEGREE_CN = {"本科", "硕士", "博士"};

    private final ISchoolRepository repository;
    private final IAuthService authService;
    private final UserAccountMapper accountMapper;

    @Override
    public List<SchoolVO> search(String q, String province, String level) {
        return repository.search(q, province, level, 30).stream()
                .map(s -> SchoolVO.builder()
                        .id(s.getId()).name(s.getName()).shortName(s.getShortName())
                        .province(s.getProvince()).level(s.getLevel()).build())
                .toList();
    }

    @Override
    public SchoolDetailVO detail(Long id) {
        EduSchool s = repository.findSchool(id).orElse(null);
        if (s == null) return null;
        List<SchoolRuleVO> rules = repository.publishedRules(id).stream()
                .map(r -> SchoolRuleVO.builder()
                        .degreeType(r.getDegreeType()).college(r.getCollege())
                        .aiRateLimit(r.getAiRateLimit()).plagiarismLimit(r.getPlagiarismLimit())
                        .platform(r.getPlatform()).effectiveYear(r.getEffectiveYear())
                        .sourceUrl(r.getSourceUrl()).build())
                .toList();
        return SchoolDetailVO.builder()
                .id(s.getId()).name(s.getName()).shortName(s.getShortName())
                .province(s.getProvince()).level(s.getLevel()).rules(rules).build();
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void setUserSchool(String bearerToken, Long schoolId, String degreeType) {
        AuthUser me = authService.me(bearerToken);
        if (degreeType != null && !degreeType.isBlank() && !DEGREES.contains(degreeType)) {
            throw new IllegalArgumentException("degreeType 非法：" + degreeType);
        }
        UserAccount account = accountMapper.selectById(me.getId());
        if (account == null) throw new IllegalStateException("用户不存在");
        account.setSchoolId(schoolId);
        account.setDegreeType(degreeType);
        accountMapper.updateById(account);
        log.info("user {} set school={} degree={}", me.getId(), schoolId, degreeType);
    }

    @Override
    public ResolvedRuleVO resolveForUser(String bearerToken) {
        AuthUser me = authService.me(bearerToken);
        return resolveByUserId(me == null ? null : me.getId());
    }

    @Override
    public ResolvedRuleVO resolveByUserId(Long userId) {
        UserAccount account = userId == null ? null : accountMapper.selectById(userId);
        Long schoolId = account == null ? null : account.getSchoolId();
        String degree = account == null ? null : account.getDegreeType();
        if (schoolId == null || degree == null || degree.isBlank()) {
            return ResolvedRuleVO.builder().resolved(false).label("通用标准").build();
        }
        EduSchool school = repository.findSchool(schoolId).orElse(null);
        String shortName = school == null ? "" : (school.getShortName() != null ? school.getShortName() : school.getName());
        return repository.resolve(schoolId, degree)
                .map(r -> ResolvedRuleVO.builder()
                        .resolved(true).ruleId(r.getId()).schoolId(schoolId).schoolName(shortName).degreeType(degree)
                        .aiRateLimit(r.getAiRateLimit()).plagiarismLimit(r.getPlagiarismLimit())
                        .platform(r.getPlatform()).effectiveYear(r.getEffectiveYear())
                        .sourceUrl(r.getSourceUrl()).sourceType(r.getSourceType())
                        .label(shortName + " · " + degreeCn(degree)).build())
                .orElseGet(() -> ResolvedRuleVO.builder()
                        .resolved(false).schoolId(schoolId).schoolName(shortName).degreeType(degree)
                        .label("通用标准").build());
    }

    private String degreeCn(String degree) {
        return switch (degree) {
            case "bachelor" -> DEGREE_CN[0];
            case "master" -> DEGREE_CN[1];
            case "phd" -> DEGREE_CN[2];
            default -> degree;
        };
    }
}
