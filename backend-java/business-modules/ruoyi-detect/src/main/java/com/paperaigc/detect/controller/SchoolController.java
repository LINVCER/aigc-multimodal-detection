package com.paperaigc.detect.controller;

import cn.dev33.satoken.annotation.SaIgnore;
import com.paperaigc.detect.common.constant.AuthConstants;
import com.paperaigc.detect.domain.dto.SetSchoolDTO;
import com.paperaigc.detect.domain.vo.ResolvedRuleVO;
import com.paperaigc.detect.domain.vo.SchoolDetailVO;
import com.paperaigc.detect.domain.vo.SchoolVO;
import com.paperaigc.detect.service.ISchoolService;
import lombok.RequiredArgsConstructor;
import org.dromara.common.core.domain.R;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 高校与红线 · C 端与公开查询（202610-school-redline-plan.md §4、§6）
 *
 * <p>/schools 公开查询页不需登录；/me/* 按 token 认当前用户。</p>
 */
@SaIgnore
@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
public class SchoolController {

    private final ISchoolService schoolService;

    /** 学校搜索（name/shortName/aliases） */
    @GetMapping("/schools")
    public R<List<SchoolVO>> search(@RequestParam(required = false) String q,
                                    @RequestParam(required = false) String province,
                                    @RequestParam(required = false) String level) {
        return R.ok(schoolService.search(q, province, level));
    }

    /** 学校详情 + 已发布红线 */
    @GetMapping("/schools/{id}")
    public R<SchoolDetailVO> detail(@PathVariable Long id) {
        return R.ok(schoolService.detail(id));
    }

    /** 设置当前用户的学校与学位 */
    @PutMapping("/me/school")
    public R<Void> setSchool(@RequestBody SetSchoolDTO dto,
                             @RequestHeader(value = AuthConstants.HEADER_AUTHORIZATION, required = false) String auth) {
        schoolService.setUserSchool(auth, dto.getSchoolId(), dto.getDegreeType());
        return R.ok();
    }

    /** 当前用户生效的红线（上传页卡片 / 报告页文案） */
    @GetMapping("/me/rule")
    public R<ResolvedRuleVO> myRule(@RequestHeader(value = AuthConstants.HEADER_AUTHORIZATION, required = false) String auth) {
        return R.ok(schoolService.resolveForUser(auth));
    }
}
