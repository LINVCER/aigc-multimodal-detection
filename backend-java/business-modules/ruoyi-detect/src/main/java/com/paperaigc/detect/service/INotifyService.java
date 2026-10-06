package com.paperaigc.detect.service;

import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.domain.entity.Feedback;

/**
 * 事务性通知（增长闭环 §5：订阅消息「检测完成」「申诉有回复」）
 *
 * <p>只做事务通知，不做营销推送。实现见 {@code LogNotifyServiceImpl}：
 * 微信登录仍是 mock、没有真实 openid，真实发送要等 W3.c 接入 code2session 后替换实现。</p>
 */
public interface INotifyService {

    /**
     * 检测完成
     * @param task 已 DONE 的任务
     */
    void taskDone(DetectTask task);

    /**
     * 申诉有回复
     * @param feedback 已 REPLIED 的申诉
     */
    void appealReplied(Feedback feedback);
}
