package com.paperaigc.detect.common.enums;

import lombok.Getter;

/**
 * 业务错误码统一定义
 *
 * <p>编码规则：4 位数字，首位分段：
 * <ul>
 *   <li>1xxx 通用（参数 / 权限 / 未找到）</li>
 *   <li>2xxx 认证登录</li>
 *   <li>3xxx 检测任务</li>
 *   <li>4xxx 用户反馈</li>
 *   <li>5xxx 用户 / 运营账号</li>
 *   <li>6xxx 报告导出</li>
 * </ul>
 * 前端按 code 区分文案与跳转，不依赖 msg 字符串。</p>
 */
@Getter
public enum ErrorCode {

    /* ========== 1xxx 通用 ========== */
    PARAM_INVALID          (1001, "参数无效"),
    PARAM_MISSING          (1002, "缺少必填参数"),
    UNAUTHORIZED           (1401, "未登录或登录已失效"),
    FORBIDDEN              (1403, "无操作权限"),
    NOT_FOUND              (1404, "资源不存在"),
    SERVER_ERROR           (1500, "服务器内部错误"),

    /* ========== 2xxx 认证 ========== */
    LOGIN_USERNAME_EMPTY   (2001, "用户名不能为空"),
    LOGIN_PASSWORD_EMPTY   (2002, "密码不能为空"),
    LOGIN_TOKEN_INVALID    (2401, "token 无效或已过期"),

    /* ========== 3xxx 检测任务 ========== */
    DETECT_FORMAT_UNSUPPORT(3000, "论文格式不支持，请上传 PDF / DOC / DOCX / TXT"),
    DETECT_FILE_TOO_LARGE  (3001, "文件超过 20MB 限制"),
    DETECT_EXTRACT_FAILED  (3002, "文档解析失败"),
    DETECT_TASK_NOT_FOUND  (3003, "任务不存在"),
    DETECT_INFERENCE_ERROR (3004, "推理服务暂时不可用"),

    /* ========== 4xxx 反馈 ========== */
    FEEDBACK_CATEGORY_INVALID (4001, "反馈分类必须是 bug / suggestion / appeal"),
    FEEDBACK_CONTENT_EMPTY    (4002, "反馈内容不能为空"),
    FEEDBACK_CONTENT_TOO_LONG (4003, "反馈内容超过 2000 字"),
    FEEDBACK_APPEAL_NEED_TASK (4004, "结果申诉需带上 taskId"),
    FEEDBACK_REPLY_EMPTY      (4005, "已回复状态必须填回复内容"),
    FEEDBACK_NOT_FOUND        (4404, "反馈不存在"),

    /* ========== 5xxx 用户 ========== */
    USER_NOT_FOUND         (5404, "用户不存在"),
    ;

    private final int code;
    private final String msg;

    ErrorCode(int code, String msg) {
        this.code = code;
        this.msg = msg;
    }
}
