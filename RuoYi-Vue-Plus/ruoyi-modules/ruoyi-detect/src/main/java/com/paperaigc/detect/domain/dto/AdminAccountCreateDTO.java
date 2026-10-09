package com.paperaigc.detect.domain.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 管理员新建平台账号；密码由服务端生成临时密码返回
 */
@Data
public class AdminAccountCreateDTO {

    @NotBlank(message = "用户名不能为空")
    @Size(min = 2, max = 64, message = "用户名长度 2-64 位")
    private String username;

    @Size(max = 64, message = "姓名最长 64 位")
    private String realName;

    /** USER / ADMIN / OPS_ADMIN，缺省 USER */
    private String role;

    @Size(max = 128, message = "组织最长 128 位")
    private String orgName;
}
