package com.paperaigc.detect.service.impl;

import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.domain.entity.Feedback;
import com.paperaigc.detect.service.INotifyService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

/**
 * 通知实现（占位）：模板 id 已可配，但没有真实 openid 发不出去，只记日志
 *
 * <p>替换为真实实现需要：user_profile 存 openid（W3.c 微信登录真接入）、
 * 后端 access_token 缓存、调 subscribeMessage.send。小程序端的 requestSubscribeMessage
 * 已在 mobile-uniapp/api/wechat.js 封装，模板 id 申请后填到 platform.notify.wechat.*。</p>
 */
@Slf4j
@Service
public class LogNotifyServiceImpl implements INotifyService {

    @Value("${platform.notify.wechat.detect-done-template:}")
    private String detectDoneTemplate;

    @Value("${platform.notify.wechat.appeal-replied-template:}")
    private String appealRepliedTemplate;

    @Override
    public void taskDone(DetectTask task) {
        if (task == null) return;
        log.info("notify[detect-done] user={} task={} aiRate={} template={}",
                task.getUserId(), task.getId(), task.getAiRate(),
                detectDoneTemplate.isBlank() ? "(未配置)" : detectDoneTemplate);
    }

    @Override
    public void appealReplied(Feedback feedback) {
        if (feedback == null) return;
        log.info("notify[appeal-replied] user={} feedback={} task={} template={}",
                feedback.getUserId(), feedback.getId(), feedback.getTaskId(),
                appealRepliedTemplate.isBlank() ? "(未配置)" : appealRepliedTemplate);
    }
}
