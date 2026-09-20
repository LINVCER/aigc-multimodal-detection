# 图像检测 Java 后端接入 · 实施计划

> 状态：待拍板 + 待实施
> 范围：仅 Java 后端（`ruoyi-detect` 业务模块）。Python 推理侧的 `/api/v1/detect/image` 端点与 `image.py` 检测器不在本次范围内（见 §9 前置依赖）。
> 实施方式：**完全对照音频链路**（`audio` 模态）的既有实现，逐文件平移。

---

## 1. 目标

打通图像检测在 Java 后端这一路，使前端 `image.vue` 提交的图片能走完：

```
POST /api/v1/detect/submit (modality=image)
  → DetectTaskServiceImpl.submitImage()
  → runImageInference()
  → IInferenceClient.detectImage()
  → Python /api/v1/detect/image（本节暂以 stub 兜底）
  → 汇总 aiRate + imageSegments 落库
  → GET /api/v1/detect/tasks/{id} 详情返回 imageSegments
```

## 2. 现状盘点（2026-09-20 实测）

| 层 | 图像现状 | 音频现状（对照） |
|---|---|---|
| 前端页面 | ✅ `mobile-uniapp/pages/upload/image.vue` | ✅ `audio.vue` |
| Java 数据模型 | ❌ 无 `ImageSegmentResult` | ✅ `AudioSegmentResult` |
| Java 客户端接口 | ❌ 无 `detectImage()` | ✅ `detectAudio()` |
| Java 服务流程 | ❌ `submit()` 里 `MODALITY_IMAGE` 直接抛「格式不支持」 | ✅ `submitAudio()` 完整 |
| Java 实体列 | ❌ 无 image 结果列 | ✅ `audio_segments_json` + `audio_duration_sec` |
| Python 端点 | ❌ 无 `/api/v1/detect/image` | ✅ `/api/v1/detect/audio`（stub） |

关键证据：
- `DetectConstants.MODALITY_IMAGE` 注释 = `// Wave 5 接`
- `guessModality()` 无 image 扩展名识别，图片会 fallback 到 `text` 被 `ALLOWED_EXT(pdf/doc/docx/txt)` 拒绝
- `DetectTaskServiceImpl.submit()` switch 分支：`case MODALITY_IMAGE -> throw new BizException(DETECT_FORMAT_UNSUPPORT, "图像检测建设中（Wave 5）")`

## 3. 参照模板：音频链路完整文件清单

以下文件是图像接入的**逐行对照模板**，实施时每步照抄音频写法：

| # | 文件（相对 `backend-java/business-modules/ruoyi-detect/`） | 音频实现 |
|---|---|---|
| 1 | `src/main/java/com/paperaigc/detect/domain/entity/AudioSegmentResult.java` | 数据模型（Lombok `@Data @Builder @NoArgsConstructor @AllArgsConstructor`） |
| 2 | `src/main/java/com/paperaigc/detect/common/constant/DetectConstants.java` | `ALLOWED_AUDIO_MIME` / `ALLOWED_AUDIO_EXT` / `guessModality()` |
| 3 | `src/main/java/com/paperaigc/detect/service/IInferenceClient.java` | `detectAudio(byte[], String, boolean)` |
| 4 | `src/main/java/com/paperaigc/detect/service/impl/HttpInferenceClient.java` | `detectAudio()` + `buildAudioMultipart()` |
| 5 | `src/main/java/com/paperaigc/detect/domain/entity/DetectTask.java` | `audioSegments`（`audio_segments_json` JSON 列）+ `audioDurationSec` |
| 6 | `src/main/java/com/paperaigc/detect/service/impl/DetectTaskServiceImpl.java` | `submitAudio()` / `runAudioInference()` / `runAudioInferenceBytes()` + `submit()` switch 分支 + `retry()` 分支 |
| 7 | `src/main/java/com/paperaigc/detect/domain/vo/DetectTaskVO.java` + `DetectTaskDetailVO.java` | `audioSegments` / `audioDurationSec` 暴露 |
| 8 | `backend-java/scripts/patch-schema.sql` | `audio_duration_sec` + `audio_segments_json` 列 |

---

## 4. 改动清单（逐文件）

> 路径前缀统一为 `backend-java/business-modules/ruoyi-detect/src/main/java/com/paperaigc/detect/`（下称 `$PKG`）。

### 4.1 新增 `$PKG/domain/entity/ImageSegmentResult.java`

对齐 `AudioSegmentResult`。字段设计（**含待拍板项**，见 §5）：

```java
package com.paperaigc.detect.domain.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 图像区域级检测结果
 * <p>对齐 AudioSegmentResult：aiProb + calibratedProb 三元组；图像独有 bbox（x/y/w/h）。
 * 整图单结果时列表仅一个元素、bbox 为 null。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ImageSegmentResult {

    /** 区域序号（0 起；整图=0） */
    private Integer segmentIdx;

    /** 区域 bbox（整图为 null；像素坐标，相对原图） */
    private Integer x;
    private Integer y;
    private Integer w;
    private Integer h;

    /** 原始 AI 概率 */
    private Double aiProb;

    /** 校准后 AI 概率（前端展示与阈值判定用） */
    private Double calibratedProb;

    /** 疑似 AI 生成源（sd / flux / dalle / midjourney / human 等；模型就绪前 null） */
    private String sourceLabel;
}
```

### 4.2 修改 `$PKG/common/constant/DetectConstants.java`

1. `MODALITY_IMAGE` 注释去掉「Wave 5 接」。
2. 新增文件大小上限与白名单：

```java
    public static final long FILE_SIZE_MAX_IMAGE = 20L * 1024 * 1024;   // 20MB · 图像

    /** 图像 MIME 白名单 */
    public static final Set<String> ALLOWED_IMAGE_MIME = Set.of(
            "image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp",
            "application/octet-stream"
    );

    /** 图像后缀白名单 */
    public static final Set<String> ALLOWED_IMAGE_EXT = Set.of("jpg", "jpeg", "png", "webp", "gif", "bmp");
```

3. `guessModality()` 加 image 分支（放在 audio 判断之后、text 之前）：

```java
        if (ALLOWED_IMAGE_EXT.contains(ext)) return MODALITY_IMAGE;
```

### 4.3 修改 `$PKG/service/IInferenceClient.java` + `$PKG/service/impl/HttpInferenceClient.java`

接口新增：

```java
    /**
     * 图像 AI 检测（image 模态）
     * @param imageBytes 图片文件字节流
     * @param filename 原始文件名（含后缀，供推理侧识别格式）
     * @param returnRegions 是否要区域级明细
     * @return Python 原始响应（含 ai_prob / calibrated_prob / regions 等）
     */
    Map<String, Object> detectImage(byte[] imageBytes, String filename, boolean returnRegions);
```

`HttpInferenceClient` 实现（照抄 `detectAudio()`，仅换 URL 与字段名）：

```java
    @Override
    public Map<String, Object> detectImage(byte[] imageBytes, String filename, boolean returnRegions) {
        try {
            String boundary = "----detectImage" + System.currentTimeMillis();
            byte[] body = buildFileMultipart(imageBytes, filename == null ? "image.bin" : filename,
                    "return_regions", returnRegions, boundary);
            HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create(base() + "/api/v1/detect/image"))
                    .header("Content-Type", "multipart/form-data; boundary=" + boundary)
                    .timeout(Duration.ofSeconds(60))
                    .POST(HttpRequest.BodyPublishers.ofByteArray(body))
                    .build();
            HttpResponse<String> resp = httpClient.send(req, HttpResponse.BodyHandlers.ofString());
            return objectMapper.readValue(resp.body(), Map.class);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("inference detectImage failed", e);
            throw new BizException(ErrorCode.DETECT_INFERENCE_ERROR, "图像检测服务不可用");
        }
    }
```

> 建议把 `buildAudioMultipart` 抽象成通用 `buildFileMultipart(byte[], String filename, String fieldName, boolean flag, String boundary)`，
> 让 audio / image 共用；字段名 `return_segments`（audio）与 `return_regions`（image）作为参数传入。若不想动 audio 现有代码，
> 可只复制一份 `buildImageMultipart`。

### 4.4 修改 `$PKG/domain/entity/DetectTask.java`

新增字段（照抄 `audioSegments` 写法）：

```java
    /** 图像区域级明细 · JSON 列 image_segments_json（V0.2.0.003 迁移加列） */
    @TableField(value = "image_segments_json", typeHandler = JacksonTypeHandler.class)
    private List<ImageSegmentResult> imageSegments;
```

### 4.5 修改 `$PKG/service/impl/DetectTaskServiceImpl.java`（核心）

1. `submit()` switch 分支，`MODALITY_IMAGE` 从抛异常改为：

```java
            case DetectConstants.MODALITY_IMAGE -> submitImage(file, scenario, title, userId);
```

2. 新增 `submitImage()`（照抄 `submitAudio()`）：

```java
    private DetectTask submitImage(MultipartFile file, String scenario, String title, Long userId) {
        if (file.getSize() > DetectConstants.FILE_SIZE_MAX_IMAGE) {
            throw new BizException(ErrorCode.DETECT_FILE_TOO_LARGE, "图片超过 20MB");
        }
        String mime = file.getContentType();
        String name = file.getOriginalFilename();
        String ext = (name != null && name.lastIndexOf('.') >= 0)
                ? name.substring(name.lastIndexOf('.') + 1).toLowerCase() : "";
        boolean allowed = (mime != null && DetectConstants.ALLOWED_IMAGE_MIME.contains(mime))
                || DetectConstants.ALLOWED_IMAGE_EXT.contains(ext);
        if (!allowed) throw new BizException(ErrorCode.DETECT_FORMAT_UNSUPPORT, "图片格式不支持");

        String sc = ParamUtils.isBlank(scenario) ? ScenarioConstants.OTHER : scenario;
        String paperTitle = (title != null && !title.isBlank()) ? title : name;
        DetectTask task = DetectTask.builder()
                .userId(userId)
                .modality(DetectConstants.MODALITY_IMAGE)
                .paperTitle(paperTitle)
                .status(DetectConstants.STATUS_PENDING)
                .scenario(sc)
                .threshold(scenarioThresholdService.threshold(sc))
                .modelVersion("image-stub-v0")
                .originalFilename(name)
                .fileSize(file.getSize())
                .createdAt(LocalDateTime.now())
                .build();
        task = taskRepository.save(task);

        try {
            task.setFilePath(storageService.save(file, task.getId()));
        } catch (Exception e) {
            log.warn("save image failed but continue task {}", task.getId(), e);
        }

        runImageInference(task, file);
        taskRepository.update(task);
        return task;
    }
```

3. 新增 `runImageInference()`（照抄 `runAudioInference()`）+ `runImageInferenceBytes()`（照抄 `runAudioInferenceBytes()`，供 retry）：

```java
    @SuppressWarnings("unchecked")
    private void runImageInference(DetectTask task, MultipartFile file) {
        try {
            byte[] bytes = file.getBytes();
            Map<String, Object> py = inferenceClient.detectImage(bytes, file.getOriginalFilename(), true);

            Double cp = ParamUtils.toDouble(py.get("calibrated_prob"));
            List<Map<String, Object>> raw = (List<Map<String, Object>>) py.getOrDefault("regions", List.of());

            List<ImageSegmentResult> segs = new ArrayList<>(raw.size());
            for (int i = 0; i < raw.size(); i++) {
                Map<String, Object> r = raw.get(i);
                segs.add(ImageSegmentResult.builder()
                        .segmentIdx(ParamUtils.toInt(r.getOrDefault("segment_idx", i)))
                        .x(ParamUtils.toIntNullable(r.get("x")))
                        .y(ParamUtils.toIntNullable(r.get("y")))
                        .w(ParamUtils.toIntNullable(r.get("w")))
                        .h(ParamUtils.toIntNullable(r.get("h")))
                        .aiProb(ParamUtils.toDouble(r.get("ai_prob")))
                        .calibratedProb(ParamUtils.toDouble(r.get("calibrated_prob")))
                        .sourceLabel((String) r.get("source_label"))
                        .build());
            }

            task.setImageSegments(segs);
            task.setAiRate(cp == null ? null : Math.round(cp * 1000) / 10.0);
            task.setStatus(DetectConstants.STATUS_DONE);
            task.setFinishedAt(LocalDateTime.now());
        } catch (Exception e) {
            log.error("image inference failed for task {}", task.getId(), e);
            task.setStatus(DetectConstants.STATUS_FAILED);
            task.setFinishedAt(LocalDateTime.now());
        }
    }
```

> 注：`ParamUtils.toIntNullable` 若不存在，需在 `ParamUtils` 补一个（或直接 `r.get("x")==null?null:((Number)r.get("x")).intValue()`）。实施时先核对 `ParamUtils` 现有工具方法清单。

4. `retry()` 里增加 image 分支（照抄 audio 分支）：

```java
            if (DetectConstants.MODALITY_AUDIO.equals(mod)) {
                // ... 现有 audio 分支
            } else if (DetectConstants.MODALITY_IMAGE.equals(mod)) {
                byte[] bytes;
                try (java.io.InputStream is = storageService.read(task.getFilePath())) {
                    bytes = is.readAllBytes();
                }
                runImageInferenceBytes(task, bytes);
            } else {
                // ... 现有 text 分支
            }
```

5. `retry()` 开头清状态处，补充 `task.setImageSegments(null);`（与现有 `task.setAudioSegments(null)` 并列）。

### 4.6 修改 `$PKG/domain/vo/DetectTaskVO.java` + `$PKG/domain/vo/DetectTaskDetailVO.java`

- `DetectTaskDetailVO`：加 `private List<ImageSegmentResult> imageSegments;`，`from()` 里补 `.imageSegments(t.getImageSegments())`。
- `DetectTaskVO`（列表）：**不加** imageSegments（对齐 audio —— 列表只传主表字段，`audioSegments` 也没进列表 VO，只进了 DetailVO）。

### 4.7 修改 `backend-java/scripts/patch-schema.sql`

`detect_task` 表新增列（紧跟 `audio_segments_json` 之后）：

```sql
  image_segments_json       JSON NULL COMMENT '图像区域级 · [{segmentIdx,x,y,w,h,aiProb,calibratedProb,sourceLabel}]',
```

同步在 `ALTER TABLE`/幂等迁移语句里补（若该文件用 `CREATE TABLE IF NOT EXISTS` 且已有对应 `ALTER` 段，需两处都加，参照 `audio_segments_json` 的既有写法）。

---

## 5. 数据模型 & 待拍板项

**主推方案（推荐）**：图像结果用 `List<ImageSegmentResult>` 存 `image_segments_json` JSON 列。
整图单结果时列表仅一个元素（`segmentIdx=0`、`bbox=null`）；未来接篡改/区域能力时同一列可扩展多个带 bbox 的区域。与 audio 结构完全统一，前端按 `modality` 走不同渲染即可。

**备选方案**：若确定图像只有「整图一个结果」，可改用扁平字段（`image_ai_prob` / `image_calibrated_prob` / `image_source_label` 三列），更简单但没有区域扩展性。

三个需拍板的点：
1. **结果形态**：`List<ImageSegmentResult>`（推荐） vs 扁平单结果字段。
2. **bbox 语义**：是否本阶段就要支持区域/篡改定位（若否，`x/y/w/h` 先恒为 null，仅保留字段）。
3. **Python 契约字段名**：`regions` vs `segments`，`return_regions` vs `return_segments`——需与 §9 的 Python 端点约定一致后再冻结 Java 侧解析 key。

## 6. 数据库迁移

- 新增列：`detect_task.image_segments_json JSON NULL`（版本号建议 `V0.2.0.003`，与 entity 注释一致）。
- 无独立子表（对齐 audio，JSON 单列存储，不做 `detect_image_result` 表）。

## 7. 同步注意（源 vs 开发副本）

项目存在两处业务模块，改完源目录后需同步检查：
- 源：`backend-java/business-modules/ruoyi-detect/`
- 开发副本：`RuoYi-Vue-Plus/ruoyi-modules/ruoyi-detect/`

上述 §4 的 8 个文件在两处各有一份，**改动需两边对齐**（或确认以哪边为准后单向拷贝，避免再次出现「源/副本未同步」的坑）。

## 8. 验收标准

1. `POST /api/v1/detect/submit` 传 `modality=image` + jpg/png 文件，返回 `taskId`、`status`，不再抛「格式不支持」。
2. 任务落库 `modality='image'`，`image_segments_json` 有内容（stub 阶段至少有 1 个区域元素）。
3. `GET /api/v1/detect/tasks/{id}` 详情返回 `imageSegments` 列表。
4. 不传 `modality`、直接提交 `.jpg` 时，`guessModality` 能识别为 `image`。
5. 非法格式（如 `.exe`）仍被正确拒绝。
6. 现有 text / audio 链路回归无影响（`detectParagraph` / `submitAudio` 行为不变）。

## 9. 前置依赖 & 风险

1. **Python 无 image 端点**：`detectImage()` 首次调用会 404。两个选择：
   - A（推荐）：Java 侧照常实现，`runImageInference` 捕获异常 → `STATUS_FAILED`；Python `/api/v1/detect/image` 端点后续单独补，补完后无需改 Java。
   - B：Java 侧先本地 stub（不真调 Python，直接返回固定 `calibrated_prob`）——但会引入一次性假逻辑，不推荐。
2. **`ParamUtils` 工具方法**：核对是否存在 `toIntNullable`，无则补或内联。
3. **前端配合**：`image.vue` 的展示逻辑（整图概率 vs 多区域）需等数据模型拍板后对齐，本次不改前端。