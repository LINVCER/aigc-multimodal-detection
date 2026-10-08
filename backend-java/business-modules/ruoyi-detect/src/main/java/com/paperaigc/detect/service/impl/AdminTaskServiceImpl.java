package com.paperaigc.detect.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.paperaigc.detect.common.constant.DetectConstants;
import com.paperaigc.detect.common.util.ParamUtils;
import com.paperaigc.detect.domain.dto.DetectTaskQueryDTO;
import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.domain.entity.UserAccount;
import com.paperaigc.detect.domain.vo.PageVO;
import com.paperaigc.detect.mapper.DetectTaskMapper;
import com.paperaigc.detect.mapper.UserAccountMapper;
import com.paperaigc.detect.service.IAdminTaskService;
import com.paperaigc.detect.service.IAdminUserService;
import com.paperaigc.detect.service.IDetectTaskService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * 运营后台任务列表：全部条件下推 SQL，count + LIMIT；用户标识优先取 auth_user.username
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AdminTaskServiceImpl implements IAdminTaskService {

    private final DetectTaskMapper taskMapper;
    private final UserAccountMapper accountMapper;
    private final IAdminUserService adminUserService;
    private final IDetectTaskService detectTaskService;

    @Override
    public PageVO<Map<String, Object>> page(DetectTaskQueryDTO q) {
        LambdaQueryWrapper<DetectTask> w = new LambdaQueryWrapper<>();
        if (!ParamUtils.isBlank(q.getStatus())) w.eq(DetectTask::getStatus, q.getStatus());
        if (!ParamUtils.isBlank(q.getScenario())) w.eq(DetectTask::getScenario, q.getScenario());
        if (q.getUserId() != null) w.eq(DetectTask::getUserId, q.getUserId());
        if (!ParamUtils.isBlank(q.getKeyword())) w.like(DetectTask::getPaperTitle, q.getKeyword().trim());
        if (q.getMinAiRate() != null) w.ge(DetectTask::getAiRate, q.getMinAiRate());
        if (q.getMaxAiRate() != null) w.le(DetectTask::getAiRate, q.getMaxAiRate());
        if (!ParamUtils.isBlank(q.getModelVersion())) w.eq(DetectTask::getModelVersion, q.getModelVersion());
        if (!ParamUtils.isBlank(q.getDateFrom())) w.ge(DetectTask::getCreatedAt, LocalDate.parse(q.getDateFrom()).atStartOfDay());
        if (!ParamUtils.isBlank(q.getDateTo())) w.lt(DetectTask::getCreatedAt, LocalDate.parse(q.getDateTo()).plusDays(1).atStartOfDay());
        if (q.getPass() != null) {
            w.isNotNull(DetectTask::getAiRate).isNotNull(DetectTask::getThreshold);
            w.apply(q.getPass() ? "ai_rate <= threshold" : "ai_rate > threshold");
        }
        if (!ParamUtils.isBlank(q.getRateBucket())) {
            double[] range = bucketRange(q.getRateBucket());
            if (range != null) {
                w.ge(DetectTask::getAiRate, range[0]);
                if (range[1] < 100) w.lt(DetectTask::getAiRate, range[1]);
            }
        }

        long total = taskMapper.selectCount(w);
        int pageNum = q.getPageNum() == null || q.getPageNum() < 1 ? 1 : q.getPageNum();
        int pageSize = q.getPageSize() == null || q.getPageSize() < 1 ? 20 : Math.min(q.getPageSize(), 200);
        if (total == 0) return PageVO.of(0, List.of());

        boolean asc = "asc".equalsIgnoreCase(q.getSortOrder());
        switch (q.getSortBy() == null ? "" : q.getSortBy()) {
            case "aiRate" -> w.orderBy(true, asc, DetectTask::getAiRate);
            case "wordCount" -> w.orderBy(true, asc, DetectTask::getWordCount);
            case "createdAt" -> w.orderBy(true, asc, DetectTask::getCreatedAt);
            default -> w.orderByDesc(DetectTask::getId);
        }
        w.last("LIMIT " + ((pageNum - 1) * pageSize) + "," + pageSize);
        List<DetectTask> rows = taskMapper.selectList(w);

        List<Long> uids = rows.stream().map(DetectTask::getUserId).filter(Objects::nonNull).distinct().toList();
        Map<Long, String> names = uids.isEmpty() ? Map.of() : accountMapper.selectList(
                        new LambdaQueryWrapper<UserAccount>().in(UserAccount::getId, uids)
                                .select(UserAccount::getId, UserAccount::getUsername, UserAccount::getRealName))
                .stream().collect(Collectors.toMap(UserAccount::getId, a -> a.getRealName() != null && !a.getRealName().isBlank()
                        ? a.getRealName() + "（" + a.getUsername() + "）" : a.getUsername(), (x, y) -> x));
        return PageVO.of(total, rows.stream().map(t -> maskForAdmin(t, names)).toList());
    }

    /** 运营视图：不返回原文段落，只带列表字段 + 用户标识 */
    private Map<String, Object> maskForAdmin(DetectTask t, Map<Long, String> names) {
        Map<String, Object> m = new HashMap<>();
        m.put("id", t.getId());
        m.put("paperTitle", t.getPaperTitle());
        m.put("scenario", t.getScenario());
        m.put("threshold", t.getThreshold());
        m.put("aiRate", t.getAiRate());
        m.put("status", t.getStatus());
        m.put("createdAt", t.getCreatedAt() == null ? null : t.getCreatedAt().toString());
        m.put("finishedAt", t.getFinishedAt() == null ? null : t.getFinishedAt().toString());
        m.put("wordCount", t.getWordCount());
        m.put("bodyParagraphCount", t.getBodyParagraphCount());
        m.put("excludedParagraphCount", t.getExcludedParagraphCount());
        m.put("modelVersion", t.getModelVersion() == null ? "stub-v0" : t.getModelVersion());
        m.put("parentTaskId", t.getParentTaskId());
        m.put("originalFilename", t.getOriginalFilename());
        m.put("fileSize", t.getFileSize());
        Long uid = t.getUserId();
        m.put("userId", uid);
        m.put("userLabel", uid == null ? "-" : names.getOrDefault(uid, adminUserService.userLabel(uid)));
        return m;
    }

    /** 与 DetectAnalyticsServiceImpl.bucketOf 的分桶一致：0-10 / 10-20 / 20-30 / 30-50 / 50+ */
    private static double[] bucketRange(String bucket) {
        return switch (bucket) {
            case "0-10" -> new double[]{0, 10};
            case "10-20" -> new double[]{10, 20};
            case "20-30" -> new double[]{20, 30};
            case "30-50" -> new double[]{30, 50};
            case "50+" -> new double[]{50, 100};
            default -> null;
        };
    }

    @Override
    public Map<String, Object> stats() {
        LocalDateTime today = LocalDate.now().atStartOfDay();
        Map<String, Object> out = new LinkedHashMap<>();
        Map<String, Long> byStatus = new LinkedHashMap<>();
        for (String s : List.of(DetectConstants.STATUS_PENDING, DetectConstants.STATUS_RUNNING, DetectConstants.STATUS_DONE, DetectConstants.STATUS_FAILED)) {
            byStatus.put(s, taskMapper.selectCount(new LambdaQueryWrapper<DetectTask>().eq(DetectTask::getStatus, s)));
        }
        long total = byStatus.values().stream().mapToLong(Long::longValue).sum();
        long done = byStatus.getOrDefault(DetectConstants.STATUS_DONE, 0L);
        long over = taskMapper.selectCount(new LambdaQueryWrapper<DetectTask>()
                .eq(DetectTask::getStatus, DetectConstants.STATUS_DONE).isNotNull(DetectTask::getAiRate).apply("ai_rate > threshold"));
        out.put("total", total);
        out.put("byStatus", byStatus);
        out.put("today", taskMapper.selectCount(new LambdaQueryWrapper<DetectTask>().ge(DetectTask::getCreatedAt, today)));
        out.put("todayFailed", taskMapper.selectCount(new LambdaQueryWrapper<DetectTask>().ge(DetectTask::getCreatedAt, today).eq(DetectTask::getStatus, DetectConstants.STATUS_FAILED)));
        out.put("over", over);
        out.put("overRate", done == 0 ? null : Math.round(over * 1000.0 / done) / 10.0);
        return out;
    }

    @Override
    public int batchDelete(List<Long> ids) {
        return apply(ids, id -> { detectTaskService.delete(id); return true; });
    }

    @Override
    public int batchRetry(List<Long> ids) {
        return apply(ids, id -> {
            DetectTask t = taskMapper.selectById(id);
            if (t == null || !DetectConstants.STATUS_FAILED.equals(t.getStatus())) return false;
            detectTaskService.retry(id);
            return true;
        });
    }

    private int apply(List<Long> ids, Function<Long, Boolean> op) {
        if (ids == null) return 0;
        int n = 0;
        for (Long id : ids.stream().filter(Objects::nonNull).distinct().toList()) {
            try { if (op.apply(id)) n++; }
            catch (Exception e) { log.warn("admin batch op task={} failed: {}", id, e.toString()); }
        }
        return n;
    }
}
