package com.paperaigc.detect.service.impl;

import com.paperaigc.detect.common.enums.ErrorCode;
import com.paperaigc.detect.common.exception.BizException;
import com.paperaigc.detect.common.util.ParamUtils;
import com.paperaigc.detect.domain.dto.AdminUserQueryDTO;
import com.paperaigc.detect.domain.entity.AdminUser;
import com.paperaigc.detect.domain.vo.AdminUserVO;
import com.paperaigc.detect.domain.vo.PageVO;
import com.paperaigc.detect.repository.IAdminUserRepository;
import com.paperaigc.detect.service.IAdminUserService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.Collection;
import java.util.Comparator;
import java.util.List;

/**
 * 运营后台 · 用户管理
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AdminUserServiceImpl implements IAdminUserService {

    private final IAdminUserRepository userRepository;

    @Override
    public PageVO<AdminUserVO> page(AdminUserQueryDTO q) {
        List<AdminUser> all = userRepository.findAll().stream()
                .filter(u -> ParamUtils.isBlank(q.getLoginType()) || q.getLoginType().equals(u.getLoginType()))
                .filter(u -> ParamUtils.isBlank(q.getStatus())    || q.getStatus().equals(u.getStatus()))
                .filter(u -> ParamUtils.isBlank(q.getKeyword())
                        || ParamUtils.containsIgnoreCase(u.getIdentity(), q.getKeyword())
                        || String.valueOf(u.getId()).contains(q.getKeyword()))
                .filter(u -> q.getMinDetect() == null || (u.getDetectCount() != null && u.getDetectCount() >= q.getMinDetect()))
                .filter(u -> q.getMaxDetect() == null || (u.getDetectCount() != null && u.getDetectCount() <= q.getMaxDetect()))
                .sorted(Comparator.comparing(AdminUser::getRegisteredAt,
                        Comparator.nullsLast(Comparator.reverseOrder())))
                .toList();

        int total = all.size();
        int pageNum = q.getPageNum() == null || q.getPageNum() < 1 ? 1 : q.getPageNum();
        int pageSize = q.getPageSize() == null || q.getPageSize() < 1 ? 20 : q.getPageSize();
        int from = Math.max(0, (pageNum - 1) * pageSize);
        int to = Math.min(total, from + pageSize);
        List<AdminUserVO> rows = from >= total ? List.of()
                : all.subList(from, to).stream().map(AdminUserVO::from).toList();
        return PageVO.of(total, rows);
    }

    @Override
    public AdminUserVO detail(Long id) {
        return AdminUserVO.from(userRepository.findById(id)
                .orElseThrow(() -> new BizException(ErrorCode.USER_NOT_FOUND)));
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void ban(Long id) {
        updateStatus(id, "BANNED");
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void unban(Long id) {
        updateStatus(id, "NORMAL");
    }

    private void updateStatus(Long id, String status) {
        AdminUser u = userRepository.findById(id)
                .orElseThrow(() -> new BizException(ErrorCode.USER_NOT_FOUND));
        u.setStatus(status);
        userRepository.update(u);
    }

    /* ==================== 供 Dashboard / TaskLabel 复用 ==================== */

    @Override
    public Collection<AdminUser> findAll() {
        return userRepository.findAll();
    }

    @Override
    public int countTodayNewUser() {
        LocalDate today = LocalDate.now();
        return (int) userRepository.findAll().stream()
                .filter(u -> u.getRegisteredAt() != null && u.getRegisteredAt().toLocalDate().equals(today))
                .count();
    }

    @Override
    public String userLabel(Long userId) {
        if (userId == null) return "-";
        return userRepository.findById(userId)
                .map(AdminUser::getIdentity)
                .orElse("user#" + userId);
    }
}
