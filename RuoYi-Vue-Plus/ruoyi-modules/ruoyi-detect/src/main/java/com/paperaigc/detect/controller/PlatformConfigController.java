package com.paperaigc.detect.controller;

import com.paperaigc.detect.service.impl.PlatformConfigClient;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.dromara.common.core.domain.R;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 平台参数配置（运营后台「参数配置」页）· 透传推理服务
 *
 * <p>检测模型版本切换与助手 LLM API 配置，改动由推理服务写回 .env（对齐 MODEL_SWITCH.md）。</p>
 */
@Slf4j
@RestController
@RequestMapping("/admin/platform")
@RequiredArgsConstructor
public class PlatformConfigController {

    private final PlatformConfigClient configClient;

    /** 当前生效配置：检测模型（版本/候选 checkpoint）+ 助手 LLM（provider/model/baseUrl，key 已脱敏） */
    @GetMapping("/config")
    public R<Object> config() {
        Object data = configClient.getConfig();
        if (data == null) {
            return R.fail("推理服务不可达，稍后再试或检查 8000 端口");
        }
        return R.ok(data);
    }

    /** 切换检测模型：body { checkpoint, baseModelPath?, modelVersion? }（推理服务同步重载） */
    @PostMapping("/model/switch")
    public R<Object> switchModel(@RequestBody Map<String, Object> body) {
        Object data = configClient.switchModel(body);
        if (data == null) {
            return R.fail("切换失败：checkpoint 不存在或推理服务不可达");
        }
        return R.ok(data);
    }

    /** 更新助手 LLM 配置：body { baseUrl?, model?, apiKey?, maxTokens? }（null=不改，apiKey 空串=清空） */
    @PostMapping("/assistant/config")
    public R<Object> updateAssistantConfig(@RequestBody Map<String, Object> body) {
        Object data = configClient.updateAssistantConfig(body);
        if (data == null) {
            return R.fail("保存失败：推理服务不可达");
        }
        return R.ok(data);
    }
}
