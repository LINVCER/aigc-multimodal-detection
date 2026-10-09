package com.paperaigc.detect.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.paperaigc.detect.common.constant.DetectConstants;
import com.paperaigc.detect.domain.entity.DetectStatisticsDaily;
import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.mapper.DetectStatisticsDailyMapper;
import com.paperaigc.detect.mapper.DetectTaskMapper;
import com.paperaigc.detect.service.IDetectAnalyticsService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

import static com.paperaigc.detect.domain.entity.DetectStatisticsDaily.ALL;

/**
 * 物化统计实现：每个终态任务写 4 个分片 (all,all) (sc,all) (all,st) (sc,st)
 *
 * <p>当前数据量小，先做「提交时增量更新」（方案 §4 方案 B）；rebuild 提供全量重算兜底，
 * 量大后再换定时任务（方案 A）。</p>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class DetectAnalyticsServiceImpl implements IDetectAnalyticsService {

    private static final List<String> SCENARIOS = List.of(
            "academic_bachelor", "academic_master", "academic_phd", "job_report", "self_media", "other");
    private static final String[] BUCKETS = {"0-10", "10-20", "20-30", "30-50", "50-100"};

    private final DetectStatisticsDailyMapper statMapper;
    private final DetectTaskMapper taskMapper;

    /* ==================== 写 ==================== */

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void record(DetectTask task) {
        apply(task, +1);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void revert(DetectTask task) {
        if (task == null || !isTerminal(task.getStatus())) return;
        apply(task, -1);
    }

    private static boolean isTerminal(String status) {
        return DetectConstants.STATUS_DONE.equals(status) || DetectConstants.STATUS_FAILED.equals(status);
    }

    private void apply(DetectTask task, int sign) {
        if (task == null || task.getStatus() == null) return;
        LocalDate date = (task.getCreatedAt() == null ? LocalDateTime.now() : task.getCreatedAt()).toLocalDate();
        String sc = task.getScenario() == null ? "other" : task.getScenario();
        String st = task.getStatus();
        for (String s : new String[]{ALL, sc}) {
            for (String t : new String[]{ALL, st}) {
                DetectStatisticsDaily row = find(date, s, t);
                boolean insert = row == null;
                if (insert) {
                    row = DetectStatisticsDaily.builder().statDate(date).scenario(s).status(t)
                            .totalCount(0).doneCount(0).aiRateSum(BigDecimal.ZERO).passCount(0).overCount(0)
                            .sourceLabels(new HashMap<>()).build();
                }
                accumulate(row, task, sign);
                row.setUpdatedAt(LocalDateTime.now());
                if (insert) statMapper.insert(row); else statMapper.updateById(row);
            }
        }
    }

    private static void accumulate(DetectStatisticsDaily row, DetectTask task, int sign) {
        row.setTotalCount(Math.max(0, nz(row.getTotalCount()) + sign));
        if (DetectConstants.STATUS_DONE.equals(task.getStatus())) {
            row.setDoneCount(Math.max(0, nz(row.getDoneCount()) + sign));
            if (task.getAiRate() != null) {
                BigDecimal sum = (row.getAiRateSum() == null ? BigDecimal.ZERO : row.getAiRateSum())
                        .add(BigDecimal.valueOf(task.getAiRate() * sign));
                row.setAiRateSum(sum.max(BigDecimal.ZERO));
                if (task.getThreshold() != null) {
                    if (task.getAiRate() <= task.getThreshold()) row.setPassCount(Math.max(0, nz(row.getPassCount()) + sign));
                    else row.setOverCount(Math.max(0, nz(row.getOverCount()) + sign));
                }
            }
            String label = dominantSource(task.getSourceLabels());
            if (label != null) {
                Map<String, Long> m = row.getSourceLabels() == null ? new HashMap<>() : new HashMap<>(row.getSourceLabels());
                long v = Math.max(0, m.getOrDefault(label, 0L) + sign);
                if (v == 0) m.remove(label); else m.put(label, v);
                row.setSourceLabels(m);
            }
        }
        int done = nz(row.getDoneCount());
        row.setAvgAiRate(done == 0 || row.getAiRateSum() == null ? null
                : row.getAiRateSum().divide(BigDecimal.valueOf(done), 2, RoundingMode.HALF_UP));
    }

    /** 溯源分布里占比最高的标签；human 也算，但只在没有 AI 标签时才会是主标签 */
    private static String dominantSource(Map<String, Double> labels) {
        if (labels == null || labels.isEmpty()) return null;
        return labels.entrySet().stream()
                .filter(e -> e.getValue() != null)
                .max(Map.Entry.comparingByValue())
                .map(Map.Entry::getKey).orElse(null);
    }

    private DetectStatisticsDaily find(LocalDate date, String sc, String st) {
        return statMapper.selectOne(new LambdaQueryWrapper<DetectStatisticsDaily>()
                .eq(DetectStatisticsDaily::getStatDate, date)
                .eq(DetectStatisticsDaily::getScenario, sc)
                .eq(DetectStatisticsDaily::getStatus, st)
                .last("LIMIT 1"));
    }

    private static int nz(Integer v) {
        return v == null ? 0 : v;
    }

    /* ==================== 重算 ==================== */

    @Override
    @Transactional(rollbackFor = Exception.class)
    public int rebuild(int days) {
        LambdaQueryWrapper<DetectTask> tq = new LambdaQueryWrapper<DetectTask>()
                .in(DetectTask::getStatus, List.of(DetectConstants.STATUS_DONE, DetectConstants.STATUS_FAILED));
        LambdaQueryWrapper<DetectStatisticsDaily> dq = new LambdaQueryWrapper<>();
        if (days > 0) {
            LocalDate from = LocalDate.now().minusDays(days - 1L);
            tq.ge(DetectTask::getCreatedAt, from.atStartOfDay());
            dq.ge(DetectStatisticsDaily::getStatDate, from);
        }
        List<DetectTask> tasks = taskMapper.selectList(tq);
        statMapper.delete(dq);

        Map<String, DetectStatisticsDaily> rows = new LinkedHashMap<>();
        for (DetectTask task : tasks) {
            LocalDate date = (task.getCreatedAt() == null ? LocalDateTime.now() : task.getCreatedAt()).toLocalDate();
            String sc = task.getScenario() == null ? "other" : task.getScenario();
            for (String s : new String[]{ALL, sc}) {
                for (String t : new String[]{ALL, task.getStatus()}) {
                    String key = date + "|" + s + "|" + t;
                    DetectStatisticsDaily row = rows.computeIfAbsent(key, k -> DetectStatisticsDaily.builder()
                            .statDate(date).scenario(s).status(t)
                            .totalCount(0).doneCount(0).aiRateSum(BigDecimal.ZERO).passCount(0).overCount(0)
                            .sourceLabels(new HashMap<>()).updatedAt(LocalDateTime.now()).build());
                    accumulate(row, task, +1);
                }
            }
        }
        for (DetectStatisticsDaily row : rows.values()) statMapper.insert(row);
        log.info("detect_statistics_daily rebuilt: days={} tasks={} rows={}", days, tasks.size(), rows.size());
        return rows.size();
    }

    /* ==================== 读 ==================== */

    @Override
    public Map<String, Object> analytics(LocalDate from, LocalDate to, String scenario, String status) {
        String sc = scenario == null || scenario.isBlank() ? ALL : scenario;
        String st = status == null || status.isBlank() ? ALL : status;
        List<DetectStatisticsDaily> all = statMapper.selectList(new LambdaQueryWrapper<DetectStatisticsDaily>()
                .ge(DetectStatisticsDaily::getStatDate, from).le(DetectStatisticsDaily::getStatDate, to)
                .orderByAsc(DetectStatisticsDaily::getStatDate));

        // 趋势：所选 (scenario, status) 分片按天
        Map<LocalDate, DetectStatisticsDaily> byDate = new TreeMap<>();
        for (DetectStatisticsDaily r : all) {
            if (sc.equals(r.getScenario()) && st.equals(r.getStatus())) byDate.put(r.getStatDate(), r);
        }
        List<Map<String, Object>> trend = new ArrayList<>();
        long total = 0, done = 0, pass = 0, over = 0;
        BigDecimal rateSum = BigDecimal.ZERO;
        Map<String, Long> sourceDist = new TreeMap<>();
        for (LocalDate d = from; !d.isAfter(to); d = d.plusDays(1)) {
            DetectStatisticsDaily r = byDate.get(d);
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("date", d.toString());
            row.put("total", r == null ? 0 : nz(r.getTotalCount()));
            row.put("done", r == null ? 0 : nz(r.getDoneCount()));
            row.put("avgAiRate", r == null || r.getAvgAiRate() == null ? null : r.getAvgAiRate());
            row.put("pass", r == null ? 0 : nz(r.getPassCount()));
            row.put("over", r == null ? 0 : nz(r.getOverCount()));
            trend.add(row);
            if (r != null) {
                total += nz(r.getTotalCount());
                done += nz(r.getDoneCount());
                pass += nz(r.getPassCount());
                over += nz(r.getOverCount());
                if (r.getAiRateSum() != null) rateSum = rateSum.add(r.getAiRateSum());
                if (r.getSourceLabels() != null) r.getSourceLabels().forEach((k, v) -> sourceDist.merge(k, v, Long::sum));
            }
        }
        Map<String, Object> kpi = new LinkedHashMap<>();
        kpi.put("total", total);
        kpi.put("done", done);
        kpi.put("avgAiRate", done == 0 ? null : rateSum.divide(BigDecimal.valueOf(done), 2, RoundingMode.HALF_UP));
        kpi.put("passRate", done == 0 ? null : round4((double) pass / done));
        kpi.put("overRate", done == 0 ? null : round4((double) over / done));

        // 场景分布：所选状态下各场景总数
        Map<String, Long> scenarioDist = new LinkedHashMap<>();
        for (String s : SCENARIOS) scenarioDist.put(s, 0L);
        Map<String, Long> statusDist = new TreeMap<>();
        for (DetectStatisticsDaily r : all) {
            if (st.equals(r.getStatus()) && !ALL.equals(r.getScenario())) scenarioDist.merge(r.getScenario(), (long) nz(r.getTotalCount()), Long::sum);
            if (sc.equals(r.getScenario()) && !ALL.equals(r.getStatus())) statusDist.merge(r.getStatus(), (long) nz(r.getTotalCount()), Long::sum);
        }

        // AI 率分桶：直接查明细（只看 DONE），数据量起来后再物化
        Map<String, Long> buckets = new LinkedHashMap<>();
        for (String b : BUCKETS) buckets.put(b, 0L);
        LambdaQueryWrapper<DetectTask> tq = new LambdaQueryWrapper<DetectTask>()
                .eq(DetectTask::getStatus, DetectConstants.STATUS_DONE)
                .ge(DetectTask::getCreatedAt, from.atStartOfDay())
                .lt(DetectTask::getCreatedAt, to.plusDays(1).atStartOfDay())
                .isNotNull(DetectTask::getAiRate);
        if (!ALL.equals(sc)) tq.eq(DetectTask::getScenario, sc);
        for (DetectTask t : taskMapper.selectList(tq)) buckets.merge(bucketOf(t.getAiRate()), 1L, Long::sum);

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("from", from.toString());
        out.put("to", to.toString());
        out.put("scenario", sc);
        out.put("status", st);
        out.put("kpi", kpi);
        out.put("trend", trend);
        out.put("scenarioDist", scenarioDist);
        out.put("statusDist", statusDist);
        out.put("rateBuckets", buckets);
        out.put("sourceDist", sourceDist);
        return out;
    }

    /** 与 DetectTaskQueryDTO.rateBucket 同一套桶口径 */
    public static String bucketOf(Double rate) {
        if (rate == null) return "0-10";
        if (rate < 10) return "0-10";
        if (rate < 20) return "10-20";
        if (rate < 30) return "20-30";
        if (rate < 50) return "30-50";
        return "50-100";
    }

    private static Double round4(double v) {
        return Math.round(v * 10000) / 10000.0;
    }
}
