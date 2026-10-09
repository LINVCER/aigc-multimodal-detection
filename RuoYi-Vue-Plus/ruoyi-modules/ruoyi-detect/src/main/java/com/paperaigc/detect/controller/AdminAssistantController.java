package com.paperaigc.detect.controller;

import cn.dev33.satoken.annotation.SaIgnore;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.paperaigc.detect.common.enums.ErrorCode;
import com.paperaigc.detect.common.exception.BizException;
import com.paperaigc.detect.domain.dto.KnowledgeChunkDTO;
import com.paperaigc.detect.domain.entity.AssistantConversation;
import com.paperaigc.detect.domain.entity.AssistantLog;
import com.paperaigc.detect.domain.entity.AssistantQualityNote;
import com.paperaigc.detect.domain.entity.KnowledgeChunk;
import com.paperaigc.detect.mapper.AssistantConversationMapper;
import com.paperaigc.detect.mapper.AssistantLogMapper;
import com.paperaigc.detect.mapper.AssistantQualityNoteMapper;
import com.paperaigc.detect.mapper.KnowledgeChunkMapper;
import com.paperaigc.detect.service.IAssistantService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.dromara.common.core.domain.R;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.stream.Collectors;

/**
 * 运营后台 · 助手运营（增长闭环 P0）
 *
 * <p>知识缺口按 docs/design/202610-assistant-growth-loop-plan.md §1.1 取：该走知识库的意图 + top-1 分数低于阈值（或未检索到）。
 * 知识库 CRUD 写 knowledge_chunk，写完通知 Python reload；Python 侧未配 ASSISTANT_KB_DB_* 时仍读 markdown，
 * reload 不会生效，/api/v1/assistant/health 的 knowledgeSource 可看当前来源。</p>
 */
@Slf4j
@SaIgnore
@RestController
@RequestMapping("/admin/assistant")
@RequiredArgsConstructor
public class AdminAssistantController {

    /** 该走知识库的意图；explain 走工具、chitchat / history 不需要知识 */
    private static final List<String> KB_INTENTS = List.of("policy", "guide", "other");

    /** 运营新增的知识块统一归这个 doc，便于和内置 01-08 区分 */
    private static final String OPS_DOC = "ops-faq";

    private final AssistantLogMapper logMapper;
    private final AssistantConversationMapper conversationMapper;
    private final AssistantQualityNoteMapper noteMapper;
    private final KnowledgeChunkMapper chunkMapper;
    private final IAssistantService assistantService;

    /**
     * 知识缺口候选列表
     * @param days 最近 N 天
     * @param threshold BM25 top-1 分数阈值（方案建议先 1.0，跑两周看分布再定）
     * @param limit 条数上限
     * @return 原问题 / 意图 / 命中分 / 命中块 / 时间
     */
    @GetMapping("/knowledge-gaps")
    public R<List<Map<String, Object>>> knowledgeGaps(
            @RequestParam(value = "days", defaultValue = "14") int days,
            @RequestParam(value = "threshold", defaultValue = "1.0") BigDecimal threshold,
            @RequestParam(value = "limit", defaultValue = "100") int limit) {
        LambdaQueryWrapper<AssistantLog> qw = new LambdaQueryWrapper<AssistantLog>()
                .ge(AssistantLog::getCreatedAt, LocalDateTime.now().minusDays(Math.max(days, 1)))
                .in(AssistantLog::getIntent, KB_INTENTS)
                .isNull(AssistantLog::getErrorCode)
                .and(w -> w.isNull(AssistantLog::getKbTopScore).or().lt(AssistantLog::getKbTopScore, threshold))
                .orderByDesc(AssistantLog::getCreatedAt)
                .last("LIMIT " + Math.min(Math.max(limit, 1), 500));
        List<Map<String, Object>> rows = logMapper.selectList(qw).stream().map(l -> {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("id", l.getId());
            m.put("question", l.getQuestion());
            m.put("intent", l.getIntent());
            m.put("kbTopScore", l.getKbTopScore());
            m.put("kbTopRef", l.getKbTopRef());
            m.put("conversationId", l.getConversationId());
            m.put("createdAt", l.getCreatedAt());
            return m;
        }).toList();
        return R.ok(rows);
    }

    /**
     * 助手运营指标（方案 §7 指标总表里能直接从 assistant_log 算的部分）
     * @param days 最近 N 天
     * @param threshold 知识命中阈值
     * @return 对话数 / 用户数 / 意图分布 / 越界率 / 知识命中率 / 工具失败率 / token 用量
     */
    @GetMapping("/stats")
    public R<Map<String, Object>> stats(
            @RequestParam(value = "days", defaultValue = "7") int days,
            @RequestParam(value = "threshold", defaultValue = "1.0") BigDecimal threshold) {
        List<AssistantLog> logs = logMapper.selectList(new LambdaQueryWrapper<AssistantLog>()
                .ge(AssistantLog::getCreatedAt, LocalDateTime.now().minusDays(Math.max(days, 1))));

        long total = logs.size();
        long users = logs.stream().map(AssistantLog::getUserId).filter(u -> u != null).distinct().count();
        long boundary = logs.stream().filter(l -> Boolean.TRUE.equals(l.getBoundaryFlag())).count();
        long toolFailed = logs.stream().filter(l -> "TOOL_FAILED".equals(l.getErrorCode())).count();
        long errors = logs.stream().filter(l -> l.getErrorCode() != null).count();
        long promptTokens = logs.stream().mapToLong(l -> l.getPromptTokens() == null ? 0 : l.getPromptTokens()).sum();
        long completionTokens = logs.stream().mapToLong(l -> l.getCompletionTokens() == null ? 0 : l.getCompletionTokens()).sum();

        Map<String, Long> intents = new TreeMap<>();
        Map<String, Long> boundaryTypes = new TreeMap<>();
        long kbDenominator = 0, kbHit = 0;
        for (AssistantLog l : logs) {
            intents.merge(l.getIntent() == null ? "unknown" : l.getIntent(), 1L, Long::sum);
            if (l.getBoundaryType() != null) boundaryTypes.merge(l.getBoundaryType(), 1L, Long::sum);
            if (l.getIntent() != null && KB_INTENTS.contains(l.getIntent()) && l.getErrorCode() == null) {
                kbDenominator++;
                if (l.getKbTopScore() != null && l.getKbTopScore().compareTo(threshold) >= 0) kbHit++;
            }
        }

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("days", days);
        out.put("conversations", total);
        out.put("users", users);
        out.put("intents", intents);
        out.put("boundaryRate", rate(boundary, total));
        out.put("boundaryTypes", boundaryTypes);
        out.put("kbHitRate", rate(kbHit, kbDenominator));
        out.put("kbSample", kbDenominator);
        out.put("toolFailedRate", rate(toolFailed, total));
        out.put("errorRate", rate(errors, total));
        out.put("promptTokens", promptTokens);
        out.put("completionTokens", completionTokens);
        return R.ok(out);
    }

    /* ==================== 对话质检（增长闭环 §3） ==================== */

    private static final Set<String> QUALITY_TAGS = Set.of("good", "wrong_fact", "off_point", "boundary", "tone");

    /**
     * 待质检会话列表：越界的全列，其余按时间倒序抽
     * @param days 最近 N 天
     * @param boundaryOnly 只看含越界标记的会话
     * @param limit 条数
     * @return 会话摘要 + 该会话的越界次数 / 轮数 / 已有质检数
     */
    @GetMapping("/conversations")
    public R<List<Map<String, Object>>> conversations(
            @RequestParam(value = "days", defaultValue = "14") int days,
            @RequestParam(value = "boundaryOnly", defaultValue = "false") boolean boundaryOnly,
            @RequestParam(value = "limit", defaultValue = "50") int limit) {
        LocalDateTime since = LocalDateTime.now().minusDays(Math.max(days, 1));
        List<AssistantLog> logs = logMapper.selectList(new LambdaQueryWrapper<AssistantLog>()
                .ge(AssistantLog::getCreatedAt, since).isNotNull(AssistantLog::getConversationId));
        Map<String, List<AssistantLog>> byConv = logs.stream().collect(Collectors.groupingBy(AssistantLog::getConversationId));

        LambdaQueryWrapper<AssistantConversation> qw = new LambdaQueryWrapper<AssistantConversation>()
                .ge(AssistantConversation::getUpdatedAt, since)
                .orderByDesc(AssistantConversation::getUpdatedAt)
                .last("LIMIT " + Math.min(Math.max(limit, 1), 300));
        if (boundaryOnly) {
            List<String> ids = byConv.entrySet().stream()
                    .filter(e -> e.getValue().stream().anyMatch(l -> Boolean.TRUE.equals(l.getBoundaryFlag())))
                    .map(Map.Entry::getKey).toList();
            if (ids.isEmpty()) return R.ok(List.of());
            qw.in(AssistantConversation::getConversationId, ids);
        }
        List<AssistantConversation> convs = conversationMapper.selectList(qw);
        List<String> convIds = convs.stream().map(AssistantConversation::getConversationId).toList();
        Map<String, Long> noteCount = convIds.isEmpty() ? Map.of() : noteMapper.selectList(
                new LambdaQueryWrapper<AssistantQualityNote>().in(AssistantQualityNote::getConversationId, convIds))
                .stream().collect(Collectors.groupingBy(AssistantQualityNote::getConversationId, Collectors.counting()));

        List<Map<String, Object>> rows = convs.stream().map(c -> {
            List<AssistantLog> ls = byConv.getOrDefault(c.getConversationId(), List.of());
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("conversationId", c.getConversationId());
            m.put("userId", c.getUserId());
            m.put("taskId", c.getTaskId());
            m.put("title", c.getTitle());
            m.put("turns", c.getMessages() == null ? 0 : c.getMessages().size() / 2);
            m.put("boundaryCount", ls.stream().filter(l -> Boolean.TRUE.equals(l.getBoundaryFlag())).count());
            m.put("intents", ls.stream().map(AssistantLog::getIntent).filter(i -> i != null).distinct().toList());
            m.put("noteCount", noteCount.getOrDefault(c.getConversationId(), 0L));
            m.put("updatedAt", c.getUpdatedAt());
            return m;
        }).toList();
        return R.ok(rows);
    }

    /**
     * 会话详情：完整消息 + 每轮审计 + 已有质检
     * @param cid 会话 id
     * @return {conversation, logs, notes}
     */
    @GetMapping("/conversations/{cid}")
    public R<Map<String, Object>> conversation(@PathVariable("cid") String cid) {
        AssistantConversation c = conversationMapper.selectOne(new LambdaQueryWrapper<AssistantConversation>()
                .eq(AssistantConversation::getConversationId, cid).last("LIMIT 1"));
        if (c == null) throw new BizException(ErrorCode.NOT_FOUND);
        List<AssistantLog> logs = logMapper.selectList(new LambdaQueryWrapper<AssistantLog>()
                .eq(AssistantLog::getConversationId, cid).orderByAsc(AssistantLog::getCreatedAt));
        List<AssistantQualityNote> notes = noteMapper.selectList(new LambdaQueryWrapper<AssistantQualityNote>()
                .eq(AssistantQualityNote::getConversationId, cid).orderByDesc(AssistantQualityNote::getCreatedAt));
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("conversation", c);
        out.put("logs", logs);
        out.put("notes", notes);
        return R.ok(out);
    }

    /**
     * 写质检标注
     * @param body {conversationId, logId?, score?, tag, note?, reviewer?}
     * @return 新标注 id
     */
    @PostMapping("/quality-notes")
    public R<Map<String, Object>> addQualityNote(@RequestBody Map<String, Object> body) {
        String cid = body.get("conversationId") == null ? null : String.valueOf(body.get("conversationId"));
        String tag = body.get("tag") == null ? null : String.valueOf(body.get("tag"));
        if (cid == null || cid.isBlank()) throw new BizException(ErrorCode.PARAM_MISSING, "conversationId");
        if (tag == null || !QUALITY_TAGS.contains(tag)) throw new BizException(ErrorCode.PARAM_INVALID, "tag 必须是 " + QUALITY_TAGS);
        Object score = body.get("score");
        Object logId = body.get("logId");
        Object reviewer = body.get("reviewer");
        AssistantQualityNote n = AssistantQualityNote.builder()
                .conversationId(cid)
                .logId(logId instanceof Number x ? x.longValue() : null)
                .score(score instanceof Number x ? Math.max(1, Math.min(5, x.intValue())) : null)
                .tag(tag)
                .note(body.get("note") == null ? null : String.valueOf(body.get("note")))
                .reviewer(reviewer instanceof Number x ? x.longValue() : null)
                .createdAt(LocalDateTime.now())
                .build();
        noteMapper.insert(n);
        return R.ok(Map.of("id", n.getId()));
    }

    /**
     * 质检统计：各标签占比（指向不同改进动作）
     * @param days 最近 N 天
     * @return {total, tags{...}, avgScore}
     */
    @GetMapping("/quality-notes/stats")
    public R<Map<String, Object>> qualityStats(@RequestParam(value = "days", defaultValue = "30") int days) {
        List<AssistantQualityNote> notes = noteMapper.selectList(new LambdaQueryWrapper<AssistantQualityNote>()
                .ge(AssistantQualityNote::getCreatedAt, LocalDateTime.now().minusDays(Math.max(days, 1))));
        Map<String, Long> tags = new TreeMap<>();
        for (AssistantQualityNote n : notes) tags.merge(n.getTag(), 1L, Long::sum);
        double avg = notes.stream().filter(n -> n.getScore() != null).mapToInt(AssistantQualityNote::getScore).average().orElse(0);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("days", days);
        out.put("total", notes.size());
        out.put("tags", tags);
        out.put("avgScore", notes.isEmpty() ? null : Math.round(avg * 100) / 100.0);
        return R.ok(out);
    }

    /* ==================== 知识缺口 → 转成知识 ==================== */

    /**
     * 「转成知识」草稿：用原问题预填标题，助手当时的回答作正文起点，运营改完再 POST /knowledge
     * @param logId assistant_log id
     * @return 预填的 KnowledgeChunkDTO 形状
     */
    @GetMapping("/knowledge-gaps/{logId}/draft")
    public R<Map<String, Object>> gapDraft(@PathVariable("logId") Long logId) {
        AssistantLog l = logMapper.selectById(logId);
        if (l == null) throw new BizException(ErrorCode.NOT_FOUND);
        String q = l.getQuestion() == null ? "" : l.getQuestion().trim();
        Map<String, Object> d = new LinkedHashMap<>();
        d.put("doc", OPS_DOC);
        d.put("title", q.length() > 60 ? q.substring(0, 60) : q);
        d.put("tags", l.getIntent() == null ? "" : l.getIntent());
        d.put("body", (l.getAnswer() == null || l.getAnswer().isBlank())
                ? "（请补充平台口径，用户原问：" + q + "）"
                : l.getAnswer());
        d.put("fromLogId", logId);
        d.put("kbTopRef", l.getKbTopRef());
        return R.ok(d);
    }

    /* ==================== 知识库管理 ==================== */

    /**
     * 知识块列表
     * @param doc 按来源文档过滤
     * @param keyword 标题 / 正文模糊
     * @param enabled 只看启用 / 下线
     * @return 列表（正文截断 200 字，详情单独取）
     */
    @GetMapping("/knowledge")
    public R<List<Map<String, Object>>> listKnowledge(
            @RequestParam(value = "doc", required = false) String doc,
            @RequestParam(value = "keyword", required = false) String keyword,
            @RequestParam(value = "enabled", required = false) Boolean enabled) {
        boolean hasKw = keyword != null && !keyword.isBlank();
        LambdaQueryWrapper<KnowledgeChunk> qw = new LambdaQueryWrapper<KnowledgeChunk>()
                .eq(doc != null && !doc.isBlank(), KnowledgeChunk::getDoc, doc)
                .eq(enabled != null, KnowledgeChunk::getEnabled, enabled)
                .and(hasKw, w -> w.like(KnowledgeChunk::getTitle, keyword).or().like(KnowledgeChunk::getBody, keyword))
                .orderByAsc(KnowledgeChunk::getDoc).orderByAsc(KnowledgeChunk::getSortOrder).orderByAsc(KnowledgeChunk::getId);
        List<Map<String, Object>> rows = chunkMapper.selectList(qw).stream().map(c -> {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("id", c.getId());
            m.put("doc", c.getDoc());
            m.put("title", c.getTitle());
            m.put("tags", c.getTags());
            String b = c.getBody() == null ? "" : c.getBody();
            m.put("bodyPreview", b.length() > 200 ? b.substring(0, 200) + "…" : b);
            m.put("sortOrder", c.getSortOrder());
            m.put("enabled", c.getEnabled());
            m.put("updatedAt", c.getUpdatedAt());
            return m;
        }).toList();
        return R.ok(rows);
    }

    @GetMapping("/knowledge/{id}")
    public R<KnowledgeChunk> getKnowledge(@PathVariable("id") Long id) {
        KnowledgeChunk c = chunkMapper.selectById(id);
        if (c == null) throw new BizException(ErrorCode.NOT_FOUND);
        return R.ok(c);
    }

    /**
     * 新增知识块并热加载
     * @param dto 标题 / 正文必填
     * @return 新块 id 与 reload 结果
     */
    @PostMapping("/knowledge")
    public R<Map<String, Object>> createKnowledge(@Valid @RequestBody KnowledgeChunkDTO dto) {
        String doc = dto.getDoc() == null || dto.getDoc().isBlank() ? OPS_DOC : dto.getDoc().trim();
        Long exists = chunkMapper.selectCount(new LambdaQueryWrapper<KnowledgeChunk>()
                .eq(KnowledgeChunk::getDoc, doc).eq(KnowledgeChunk::getTitle, dto.getTitle().trim()));
        if (exists != null && exists > 0) throw new BizException(ErrorCode.PARAM_INVALID, "同一文档下已有同名标题");
        Integer sort = dto.getSortOrder();
        if (sort == null) {
            Long n = chunkMapper.selectCount(new LambdaQueryWrapper<KnowledgeChunk>().eq(KnowledgeChunk::getDoc, doc));
            sort = n == null ? 0 : n.intValue();
        }
        KnowledgeChunk c = KnowledgeChunk.builder()
                .doc(doc).title(dto.getTitle().trim())
                .tags(dto.getTags() == null ? "" : dto.getTags().trim())
                .body(dto.getBody().trim())
                .sortOrder(sort)
                .enabled(dto.getEnabled() == null || dto.getEnabled())
                .build();
        chunkMapper.insert(c);
        log.info("知识块新增 id={} doc={} title={} fromLog={}", c.getId(), doc, c.getTitle(), dto.getFromLogId());
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("id", c.getId());
        out.put("reload", safeReload());
        return R.ok(out);
    }

    /**
     * 编辑知识块并热加载
     * @param id 块 id
     * @param dto 新内容
     * @return reload 结果
     */
    @PutMapping("/knowledge/{id}")
    public R<Map<String, Object>> updateKnowledge(@PathVariable("id") Long id, @Valid @RequestBody KnowledgeChunkDTO dto) {
        KnowledgeChunk c = chunkMapper.selectById(id);
        if (c == null) throw new BizException(ErrorCode.NOT_FOUND);
        if (dto.getDoc() != null && !dto.getDoc().isBlank()) c.setDoc(dto.getDoc().trim());
        c.setTitle(dto.getTitle().trim());
        c.setTags(dto.getTags() == null ? "" : dto.getTags().trim());
        c.setBody(dto.getBody().trim());
        if (dto.getSortOrder() != null) c.setSortOrder(dto.getSortOrder());
        if (dto.getEnabled() != null) c.setEnabled(dto.getEnabled());
        chunkMapper.updateById(c);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("id", id);
        out.put("reload", safeReload());
        return R.ok(out);
    }

    /**
     * 上线 / 下线知识块（不删，保留可回滚）
     * @param id 块 id
     * @param enabled true 上线
     * @return reload 结果
     */
    @PostMapping("/knowledge/{id}/enabled")
    public R<Map<String, Object>> setKnowledgeEnabled(@PathVariable("id") Long id, @RequestParam("enabled") boolean enabled) {
        KnowledgeChunk c = chunkMapper.selectById(id);
        if (c == null) throw new BizException(ErrorCode.NOT_FOUND);
        c.setEnabled(enabled);
        chunkMapper.updateById(c);
        return R.ok(safeReload());
    }

    /** 手动触发 Python 热加载 */
    @PostMapping("/knowledge/reload")
    public R<Map<String, Object>> reloadKnowledge() {
        return R.ok(assistantService.reloadKnowledge());
    }

    /** reload 失败不回滚写库：块已入库，下次启动或手动 reload 会生效 */
    private Map<String, Object> safeReload() {
        try {
            return assistantService.reloadKnowledge();
        } catch (Exception e) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("ok", false);
            m.put("error", "推理服务 reload 失败，块已入库，可稍后手动重载");
            return m;
        }
    }

    private static Double rate(long num, long den) {
        return den == 0 ? null : Math.round(num * 10000.0 / den) / 10000.0;
    }
}
