package com.paperaigc.detect.controller;

import cn.dev33.satoken.annotation.SaIgnore;
import com.paperaigc.detect.common.constant.AuthConstants;
import com.paperaigc.detect.domain.dto.CandidateMergeDTO;
import com.paperaigc.detect.domain.dto.CandidateQueryDTO;
import com.paperaigc.detect.domain.dto.CrawlSeedSaveDTO;
import com.paperaigc.detect.domain.dto.SchoolSaveDTO;
import com.paperaigc.detect.domain.entity.AuthUser;
import com.paperaigc.detect.domain.entity.EduSchool;
import com.paperaigc.detect.domain.entity.EduSchoolCrawlSeed;
import com.paperaigc.detect.domain.entity.EduSchoolRuleCandidate;
import com.paperaigc.detect.domain.vo.PageVO;
import com.paperaigc.detect.service.IAuthService;
import com.paperaigc.detect.service.ISchoolAdminService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.dromara.common.core.domain.R;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * 运营后台 · 学校红线管理（§12/§13）：学校 / 爬取种子 / 候选审核（数据维护）。
 */
@SaIgnore
@RestController
@RequestMapping("/admin/school")
@RequiredArgsConstructor
public class AdminSchoolController {

    private final ISchoolAdminService adminService;
    private final IAuthService authService;

    /* ---------- 学校 ---------- */

    @GetMapping("/list")
    public R<List<EduSchool>> schools(@RequestParam(required = false) String q) {
        return R.ok(adminService.listSchools(q));
    }

    @PostMapping("/save")
    public R<Void> saveSchool(@RequestBody SchoolSaveDTO dto) {
        adminService.saveSchool(dto);
        return R.ok();
    }

    /** 隐藏 / 恢复：status=hidden|active */
    @PostMapping("/{id}/status")
    public R<Void> setStatus(@PathVariable Long id, @RequestParam String status) {
        adminService.setSchoolStatus(id, status);
        return R.ok();
    }

    /** 手录 50 所：批量导入 */
    @PostMapping("/import")
    public R<Map<String, Integer>> importSchools(@RequestBody List<SchoolSaveDTO> list) {
        return R.ok(Map.of("imported", adminService.importSchools(list)));
    }

    /* ---------- 爬取种子 ---------- */

    @GetMapping("/seeds")
    public R<List<EduSchoolCrawlSeed>> seeds(@RequestParam(required = false) Long schoolId) {
        return R.ok(adminService.listSeeds(schoolId));
    }

    @PostMapping("/seeds/save")
    public R<Void> saveSeed(@RequestBody CrawlSeedSaveDTO dto) {
        adminService.saveSeed(dto);
        return R.ok();
    }

    /** 立即爬取：投任务到常驻爬取服务 */
    @PostMapping("/seeds/{id}/run")
    public R<Map<String, String>> runSeed(@PathVariable Long id) {
        String job = adminService.runSeed(id);
        return R.ok(Map.of("job", job == null ? "" : job));
    }

    /* ---------- 候选审核（数据维护） ---------- */

    /** 从爬取服务拉候选入审核队列（content_hash 去重） */
    @PostMapping("/candidates/sync")
    public R<Map<String, Integer>> syncCandidates() {
        return R.ok(Map.of("synced", adminService.syncCandidates()));
    }

    @GetMapping("/candidates")
    public R<PageVO<EduSchoolRuleCandidate>> candidates(CandidateQueryDTO query) {
        return R.ok(adminService.pageCandidates(query));
    }

    /** 合并发布为 edu_school_rule（人工确认，sourceUrl 必带） */
    @PostMapping("/candidates/{id}/merge")
    public R<Map<String, Long>> merge(@PathVariable Long id, @Valid @RequestBody CandidateMergeDTO dto,
                                      @RequestHeader(value = AuthConstants.HEADER_AUTHORIZATION, required = false) String auth) {
        long ruleId = adminService.mergeCandidate(id, dto, operatorId(auth));
        return R.ok(Map.of("ruleId", ruleId));
    }

    @PostMapping("/candidates/{id}/reject")
    public R<Void> reject(@PathVariable Long id) {
        adminService.rejectCandidate(id);
        return R.ok();
    }

    private Long operatorId(String auth) {
        try {
            AuthUser u = authService.me(auth);
            return u == null ? null : u.getId();
        } catch (Exception e) {
            return null;
        }
    }
}
