package com.paperaigc.detect.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.paperaigc.detect.common.constant.AuthConstants;
import com.paperaigc.detect.common.enums.ErrorCode;
import com.paperaigc.detect.common.exception.BizException;
import com.paperaigc.detect.common.util.ParamUtils;
import com.paperaigc.detect.common.util.PasswordHasher;
import com.paperaigc.detect.domain.dto.AdminAccountCreateDTO;
import com.paperaigc.detect.domain.dto.AdminAccountQueryDTO;
import com.paperaigc.detect.domain.dto.AdminAccountUpdateDTO;
import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.domain.entity.UserAccount;
import com.paperaigc.detect.domain.vo.AdminAccountStatsVO;
import com.paperaigc.detect.domain.vo.AdminAccountVO;
import com.paperaigc.detect.domain.vo.PageVO;
import com.paperaigc.detect.mapper.DetectTaskMapper;
import com.paperaigc.detect.mapper.UserAccountMapper;
import com.paperaigc.detect.repository.IAuthTokenRepository;
import com.paperaigc.detect.service.IAdminAccountService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * 平台账号管理实现（auth_user）
 *
 * <p>列表走 SQL 分页（count + LIMIT），检测数 / 最近检测只对当前页账号聚合一次 detect_task。</p>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AdminAccountServiceImpl implements IAdminAccountService {

    private static final Set<String> ROLES = Set.of(AuthConstants.ROLE_USER, AuthConstants.ROLE_ADMIN, AuthConstants.ROLE_OPS_ADMIN);
    private static final Pattern USERNAME_OK = Pattern.compile("^[A-Za-z0-9_.@-]{2,64}$");

    private final UserAccountMapper accountMapper;
    private final DetectTaskMapper taskMapper;
    private final IAuthTokenRepository tokenRepository;

    @Override
    public PageVO<AdminAccountVO> page(AdminAccountQueryDTO q) {
        LambdaQueryWrapper<UserAccount> w = new LambdaQueryWrapper<>();
        if (!ParamUtils.isBlank(q.getKeyword())) {
            String kw = q.getKeyword().trim();
            w.and(x -> x.like(UserAccount::getUsername, kw).or().like(UserAccount::getRealName, kw).or().like(UserAccount::getOrgName, kw));
        }
        if (!ParamUtils.isBlank(q.getRole())) w.eq(UserAccount::getRole, q.getRole().trim());
        if (q.getStatus() != null) w.eq(UserAccount::getStatus, q.getStatus());

        long total = accountMapper.selectCount(w);
        int pageNum = q.getPageNum() == null || q.getPageNum() < 1 ? 1 : q.getPageNum();
        int pageSize = q.getPageSize() == null || q.getPageSize() < 1 ? 20 : Math.min(q.getPageSize(), 200);
        if (total == 0) return PageVO.of(0, List.of());

        // 排序白名单，避免把前端字段直接拼进 SQL
        String sort = q.getSortBy() == null ? "" : q.getSortBy();
        boolean asc = "asc".equalsIgnoreCase(q.getSortOrder());
        switch (sort) {
            case "lastLoginAt" -> w.orderBy(true, asc, UserAccount::getLastLoginAt);
            case "createdAt" -> w.orderBy(true, asc, UserAccount::getCreatedAt);
            case "username" -> w.orderBy(true, asc, UserAccount::getUsername);
            default -> w.orderByDesc(UserAccount::getId);
        }
        w.last("LIMIT " + ((pageNum - 1) * pageSize) + "," + pageSize);
        List<UserAccount> rows = accountMapper.selectList(w);

        Map<Long, Object[]> detect = detectStats(rows.stream().map(UserAccount::getId).toList());
        List<AdminAccountVO> vos = rows.stream().map(a -> {
            AdminAccountVO vo = AdminAccountVO.from(a);
            Object[] d = detect.get(a.getId());
            vo.setDetectCount(d == null ? 0 : ((Number) d[0]).intValue());
            vo.setLastDetectAt(d == null ? null : (LocalDateTime) d[1]);
            return vo;
        }).toList();
        return PageVO.of(total, vos);
    }

    /** 当前页账号的 detect_task 聚合：userId → [count, lastCreatedAt] */
    private Map<Long, Object[]> detectStats(Collection<Long> userIds) {
        Map<Long, Object[]> out = new HashMap<>();
        if (userIds == null || userIds.isEmpty()) return out;
        QueryWrapper<DetectTask> qw = new QueryWrapper<DetectTask>()
                .select("user_id AS userId", "COUNT(*) AS cnt", "MAX(created_at) AS lastAt")
                .in("user_id", userIds)
                .groupBy("user_id");
        for (Map<String, Object> m : taskMapper.selectMaps(qw)) {
            Object uid = m.get("userId");
            if (uid == null) continue;
            Object lastAt = m.get("lastAt");
            LocalDateTime ts = lastAt instanceof LocalDateTime t ? t
                    : lastAt instanceof java.sql.Timestamp st ? st.toLocalDateTime() : null;
            out.put(((Number) uid).longValue(), new Object[]{m.get("cnt"), ts});
        }
        return out;
    }

    @Override
    public AdminAccountStatsVO stats() {
        LocalDateTime todayStart = LocalDate.now().atStartOfDay();
        LocalDateTime weekAgo = LocalDateTime.now().minusDays(7);
        long total = accountMapper.selectCount(null);
        long disabled = accountMapper.selectCount(new LambdaQueryWrapper<UserAccount>().eq(UserAccount::getStatus, 0));
        long todayNew = accountMapper.selectCount(new LambdaQueryWrapper<UserAccount>().ge(UserAccount::getCreatedAt, todayStart));
        long active7d = accountMapper.selectCount(new LambdaQueryWrapper<UserAccount>().ge(UserAccount::getLastLoginAt, weekAgo));
        Map<String, Long> byRole = new HashMap<>();
        for (String r : ROLES) {
            byRole.put(r, accountMapper.selectCount(new LambdaQueryWrapper<UserAccount>().eq(UserAccount::getRole, r)));
        }
        return AdminAccountStatsVO.builder()
                .total(total).active(total - disabled).disabled(disabled)
                .todayNew(todayNew).active7d(active7d).byRole(byRole)
                .build();
    }

    @Override
    public AdminAccountVO detail(Long id) {
        UserAccount a = mustGet(id);
        AdminAccountVO vo = AdminAccountVO.from(a);
        Object[] d = detectStats(List.of(id)).get(id);
        vo.setDetectCount(d == null ? 0 : ((Number) d[0]).intValue());
        vo.setLastDetectAt(d == null ? null : (LocalDateTime) d[1]);
        return vo;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateProfile(Long id, AdminAccountUpdateDTO dto) {
        mustGet(id);
        LambdaUpdateWrapper<UserAccount> u = new LambdaUpdateWrapper<UserAccount>().eq(UserAccount::getId, id);
        boolean any = false;
        if (dto.getRealName() != null) { u.set(UserAccount::getRealName, dto.getRealName().trim()); any = true; }
        if (dto.getOrgName() != null) { u.set(UserAccount::getOrgName, dto.getOrgName().trim().isEmpty() ? null : dto.getOrgName().trim()); any = true; }
        if (any) accountMapper.update(null, u);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void setStatus(Long id, int status, Long operatorId) {
        if (status != 0 && status != 1) throw new BizException(ErrorCode.PARAM_INVALID, "status 只能是 0 / 1");
        if (status == 0 && Objects.equals(id, operatorId)) throw new BizException(ErrorCode.FORBIDDEN, "不能停用自己");
        UserAccount a = mustGet(id);
        accountMapper.update(null, new LambdaUpdateWrapper<UserAccount>().eq(UserAccount::getId, id).set(UserAccount::getStatus, status));
        if (status == 0) tokenRepository.removeByUser(id);
        log.info("account status: username={} status={} by={}", a.getUsername(), status, operatorId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public int batchStatus(List<Long> ids, int status, Long operatorId) {
        if (ids == null || ids.isEmpty()) return 0;
        if (status != 0 && status != 1) throw new BizException(ErrorCode.PARAM_INVALID, "status 只能是 0 / 1");
        List<Long> targets = ids.stream().distinct().filter(i -> i != null && !(status == 0 && i.equals(operatorId))).toList();
        if (targets.isEmpty()) return 0;
        int n = accountMapper.update(null, new LambdaUpdateWrapper<UserAccount>().in(UserAccount::getId, targets).set(UserAccount::getStatus, status));
        if (status == 0) targets.forEach(tokenRepository::removeByUser);
        log.info("account batch status: n={} status={} by={}", n, status, operatorId);
        return n;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public String resetPassword(Long id) {
        UserAccount a = mustGet(id);
        String temp = PasswordHasher.tempPassword();
        accountMapper.update(null, new LambdaUpdateWrapper<UserAccount>().eq(UserAccount::getId, id).set(UserAccount::getPasswordHash, PasswordHasher.hash(temp)));
        tokenRepository.removeByUser(id);
        log.info("password reset by admin: username={}", a.getUsername());
        return temp;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void setRole(Long id, String role, Long operatorId) {
        if (role == null || !ROLES.contains(role)) throw new BizException(ErrorCode.PARAM_INVALID, "角色只能是 USER / ADMIN / OPS_ADMIN");
        if (Objects.equals(id, operatorId)) throw new BizException(ErrorCode.FORBIDDEN, "不能修改自己的角色");
        UserAccount a = mustGet(id);
        accountMapper.update(null, new LambdaUpdateWrapper<UserAccount>().eq(UserAccount::getId, id).set(UserAccount::getRole, role));
        // 角色写在 token 里的用户快照上，作废让其重新登录生效
        tokenRepository.removeByUser(id);
        log.info("account role: username={} role={} by={}", a.getUsername(), role, operatorId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public String create(AdminAccountCreateDTO dto) {
        String username = dto.getUsername() == null ? "" : dto.getUsername().trim();
        if (!USERNAME_OK.matcher(username).matches()) throw new BizException(ErrorCode.REGISTER_USERNAME_INVALID);
        String role = ParamUtils.isBlank(dto.getRole()) ? AuthConstants.ROLE_USER : dto.getRole().trim();
        if (!ROLES.contains(role)) throw new BizException(ErrorCode.PARAM_INVALID, "角色只能是 USER / ADMIN / OPS_ADMIN");
        if (accountMapper.selectCount(new LambdaQueryWrapper<UserAccount>().eq(UserAccount::getUsername, username)) > 0) {
            throw new BizException(ErrorCode.REGISTER_USERNAME_EXISTS);
        }
        String temp = PasswordHasher.tempPassword();
        UserAccount a = UserAccount.builder()
                .username(username)
                .passwordHash(PasswordHasher.hash(temp))
                .realName(ParamUtils.isBlank(dto.getRealName()) ? username : dto.getRealName().trim())
                .role(role)
                .orgName(ParamUtils.isBlank(dto.getOrgName()) ? null : dto.getOrgName().trim())
                .status(1)
                .build();
        accountMapper.insert(a);
        log.info("account created by admin: username={} role={}", username, role);
        return temp;
    }

    private UserAccount mustGet(Long id) {
        UserAccount a = id == null ? null : accountMapper.selectById(id);
        if (a == null) throw new BizException(ErrorCode.USER_NOT_FOUND);
        return a;
    }
}
