package com.paperaigc.detect.domain.dto;

import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 管理员修改账号资料；字段为 null 表示不改
 */
@Data
public class AdminAccountUpdateDTO {

    @Size(max = 64, message = "姓名最长 64 位")
    private String realName;

    @Size(max = 128, message = "组织最长 128 位")
    private String orgName;
}
