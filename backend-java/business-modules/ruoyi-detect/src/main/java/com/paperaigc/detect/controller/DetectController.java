package com.paperaigc.detect.controller;

import com.paperaigc.detect.common.util.ParamUtils;
import com.paperaigc.detect.domain.dto.DetectTaskQueryDTO;
import com.paperaigc.detect.domain.dto.HumanizeDTO;
import com.paperaigc.detect.domain.dto.ParagraphDetectDTO;
import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.domain.vo.DetectTaskDetailVO;
import com.paperaigc.detect.domain.vo.DetectTaskVO;
import com.paperaigc.detect.domain.vo.PageVO;
import com.paperaigc.detect.domain.vo.StatisticsVO;
import com.paperaigc.detect.service.IDetectTaskService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.dromara.common.core.domain.R;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.HashMap;
import java.util.Map;

/**
 * 论文 AIGC 检测接口
 *
 * <p>路径遵循 docs/design/API_CONTRACT.md（§3 检测 · §4 降 AIGC · §8 内部推理）</p>
 * <p>Controller 瘦身版：只做参数装配 + 调 Service + 返回 R；业务规则、推理调用、
 * 文件抽取、段落切分、非正文过滤全部下沉到 {@link IDetectTaskService} 与其依赖组件。</p>
 */
@Slf4j
@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
public class DetectController {

    private final IDetectTaskService detectTaskService;

    /* ==================== §3.1 提交 ==================== */

    @PostMapping("/detect/submit")
    public R<Map<String, Object>> submit(
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "scenario", required = false) String scenario,
            @RequestParam(value = "degreeType", required = false) String degreeType,   // 兼容旧字段
            @RequestParam(value = "title", required = false) String title,
            @RequestParam(value = "userId", required = false) Long userId) {  // W3.c 前透传；接入后从 Sa-Token 取
        DetectTask task = detectTaskService.submit(file, scenario, degreeType, title, userId);
        Map<String, Object> resp = new HashMap<>();
        resp.put("taskId",     task.getId());
        resp.put("paperTitle", task.getPaperTitle());
        resp.put("status",     task.getStatus());
        resp.put("createdAt",  task.getCreatedAt() == null ? null : task.getCreatedAt().toString());
        return R.ok(resp);
    }

    /* ==================== §3.2 列表 ==================== */

    @GetMapping("/detect/tasks")
    public R<PageVO<DetectTaskVO>> list(DetectTaskQueryDTO query) {
        return R.ok(detectTaskService.page(query));
    }

    /* ==================== §3.3 详情 ==================== */

    @GetMapping("/detect/tasks/{id}")
    public R<DetectTaskDetailVO> detail(@PathVariable Long id) {
        return R.ok(detectTaskService.detail(id));
    }

    /* ==================== §3.4 重试 ==================== */

    @PostMapping("/detect/tasks/{id}/retry")
    public R<DetectTaskDetailVO> retry(@PathVariable Long id) {
        detectTaskService.retry(id);
        return R.ok(detectTaskService.detail(id));
    }

    /* ==================== §3.5 取消 ==================== */

    @PostMapping("/detect/tasks/{id}/cancel")
    public R<Void> cancel(@PathVariable Long id) {
        detectTaskService.cancel(id);
        return R.ok();
    }

    /* ==================== §3.6 删除 ==================== */

    @DeleteMapping("/detect/tasks/{id}")
    public R<Void> delete(@PathVariable Long id) {
        detectTaskService.delete(id);
        return R.ok();
    }

    /* ==================== §3.7 C 端 Dashboard 统计 ==================== */

    @GetMapping("/detect/statistics")
    public R<StatisticsVO> statistics() {
        return R.ok(detectTaskService.statistics());
    }

    /* ==================== §4 降 AIGC ==================== */

    @PostMapping("/humanize")
    public R<Map<String, Object>> humanize(@RequestBody HumanizeDTO dto) {
        return R.ok(detectTaskService.humanize(dto));
    }

    /* ==================== §8.2 单段直接检测（前端粘贴文本走此接口） ==================== */

    @PostMapping("/detect/paragraph")
    public R<Map<String, Object>> detectParagraph(@Valid @RequestBody ParagraphDetectDTO dto) {
        boolean withSentences = Boolean.TRUE.equals(dto.getReturnSentences());
        return R.ok(detectTaskService.detectParagraph(dto.getText(), withSentences));
    }

    /* ==================== 运维 · 推理健康 ==================== */

    @GetMapping("/detect/health")
    public R<Map<String, Object>> health() {
        return R.ok(detectTaskService.inferenceHealth());
    }

    /* 兼容旧 utility；避免其他 controller 直接依赖 */
    private static Long toLong(Object o) { return ParamUtils.toLong(o); }
}
