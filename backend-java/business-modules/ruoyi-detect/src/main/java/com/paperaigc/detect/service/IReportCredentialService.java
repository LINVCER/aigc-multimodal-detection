package com.paperaigc.detect.service;

import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.domain.vo.ReportVerifyVO;

/**
 * 报告溯源凭证：报告编号 + 验证码 + 服务端签名
 *
 * <p>签名 = HMAC-SHA256(secret, 编号 | 任务 | AI 率 | 红线 | 场景 | 模型 | 完成时间 | 字数 | 段落结果摘要)。
 * 任何一项被改动，重新计算的签名就对不上，验证页会提示「内容与签发时不一致」。</p>
 */
public interface IReportCredentialService {

    /**
     * 任务完成后签发凭证；已签发的直接返回，不重复生成（幂等）
     * @param task 已完成的任务（需带段落结果）
     * @return 签发后的任务（字段已回写到 task 对象并落库）
     */
    DetectTask ensure(DetectTask task);

    /**
     * 公开验证：编号 + 验证码
     * @param reportNo 报告编号
     * @param code 验证码（不区分大小写）
     * @return 验证结果；编号不存在或验证码不对时 valid=false，不泄露报告内容
     */
    ReportVerifyVO verify(String reportNo, String code);

    /**
     * 签名指纹（前 16 位十六进制），给页面与 PDF 展示用
     * @param task 任务
     * @return 指纹，未签发返回 null
     */
    String fingerprint(DetectTask task);

    /**
     * 公开验证页地址 {web.base-url}/verify/{reportNo}?code=xxx
     * @param task 任务
     * @return URL，未签发返回 null
     */
    String verifyUrl(DetectTask task);
}
