package com.paperaigc.detect.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.paperaigc.detect.common.constant.AuthConstants;
import com.paperaigc.detect.common.enums.ErrorCode;
import com.paperaigc.detect.common.exception.BizException;
import com.paperaigc.detect.common.util.ParamUtils;
import com.paperaigc.detect.common.util.PasswordHasher;
import com.paperaigc.detect.domain.dto.AdminAccountCreateDTO;
import com.paperaigc.detect.domain.dto.AdminAccountQueryDTO;
import com.paperaigc.detect.domain.entity.UserAccount;
import com.paperaigc.detect.domain.vo.AdminAccountVO;
import com.paperaigc.detect.domain.vo.PageVO;
import com.paperaigc.detect.mapper.UserAccountMapper;
import com.paperaigc.detect.repository.IAuthTokenRepository;
import com.paperaigc.detect.service.IAdminAccountService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Objects;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * 平台账号管理实现（auth_user）
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AdminAccountServiceImpl implements IAdminAccountService {

    private static final Set<String> ROLES = Set.of(AuthConstants.ROLE_USER, AuthConstants.ROLE_ADMIN, AuthConstants.ROLE_OPS_ADMIN);
    private static final Pattern USERNAME_OK = Pattern.compile("^[A-Za-z0-9_.@-]{2,64}$");

    private final UserAccountMapper accountMapper;
    private final IAuthTokenRepository tokenRepository;

    @Override
    public PageVO<AdminAccountVO> page(AdminAccountQueryDTO q) {
        LambdaQueryWrapper<UserAccount> w = new LambdaQueryWrapper<UserAccount>().orderByDesc(UserAccount::getId);
        if (!ParamUtils.isBlank(q.getKeyword())) {
            String kw = q.getKeyword().trim();
            w.and(x -> x.like(UserAccount::getUsername, kw).or().like(UserAccount::getRealName, kw).or().like(UserAccount::getOrgName, kw));
        }
        if (!ParamUtils.isBlank(q.getRole())) w.eq(UserAccount::getRole, q.getRole().trim());
        if (q.getStatus() != null) w.eq(UserAccount::getStatus, q.getStatus());
        List<UserAccount> all = accountMapper.selectList(w);

        int total = all.size();
        int pageNum = q.getPageNum() == null || q.getPageNum() < 1 ? 1 : q.getPageNum();
        int pageSize = q.getPageSize() == null || q.getPageSize() < 1 ? 20 : q.getPageSize();
        int from = Math.max(0, (pageNum - 1) * pageSize);
        int to = Math.min(total, from + pageSize);
        List<AdminAccountVO> rows = from >= total ? List.of() : all.subList(from, to).stream().map(AdminAccountVO::from).toList();
        return PageVO.of(total, rows);
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
