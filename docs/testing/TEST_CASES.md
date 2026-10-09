# 知源 AIGC 检测平台 · 测试用例文档

> 版本：v1.1 ｜ 生成日期：2026-10-09 ｜ 适用代码：`backend-java/standalone-app` + `web/`
>
> 本文档与自动化测试代码一一对应，可直接按「用例编号」定位到源码。
>
> v1.1 新增：真实 MySQL / Redis 集成冒烟测试（§2.14、§2.15），并修复 JDBC 字符集配置缺陷（DEF-03）。

---

## 1. 测试范围与策略

| 维度 | 说明 |
| --- | --- |
| 测试对象 | 文本/论文 AIGC 检测主链路（登录注册 → 上传/粘贴 → 检测任务 → 报告详情 → 报告验证） |
| 后端范围 | `ruoyi-detect` 业务模块的常量、工具、认证、检测任务、文本处理、限流、阈值服务与 HTTP 契约 |
| 集成范围 | 真实 MySQL（连通/表结构/主子表事务/JSON 列）与 Redis（连通/读写/TTL/原子自增/Hash/多库隔离）冒烟 |
| 前端范围 | `web/`（Vue3 + Vite）关键用户旅程的端到端行为 |
| 不在范围 | 音频/图像检测（已归档）、真实模型推理质量、移动端（uni-app）UI |
| 测试分层 | 后端：单元测试 + MockMvc 接口契约测试 + 集成冒烟测试；前端：Playwright 端到端测试 |
| 后端框架 | JUnit 5 + Mockito + AssertJ + MyBatis-Plus + Spring MockMvc + Spring Boot Test |
| 前端框架 | Playwright（复用本机 Chrome，`channel: chrome`） |
| 数据隔离 | 单元/契约测试全部 Mock 仓储与客户端，不连真实 DB/Redis/推理服务；集成冒烟测试连真实 MySQL/Redis，写入带 `SMOKE-IT-` 前缀并在用例内物理清理；前端拦截 `/api/v1/**` 返回确定性 fixture |

### 1.1 运行方式

```bash
# 后端单元 + 契约测试（需 JDK 21；默认零外部依赖）
mvn -f backend-java/standalone-app/pom.xml test

# 后端集成冒烟测试（需真实 MySQL 3306 + Redis 16379）
mvn -f backend-java/standalone-app/pom.xml test -Pintegration
# 仅跑集成用例
mvn -f backend-java/standalone-app/pom.xml test -Pintegration -Dtest='*IntegrationSmokeTest'

# 前端 E2E（需 Node 18+，会自动复用/拉起 5173 dev server）
cd web && npx playwright test
```

> 集成用例统一打 `@Tag("integration")`。不加 `-Pintegration` 时被 Surefire 排除，保证 `mvn test`
> 在无外部服务的机器上依然全绿；加该 profile 后解除排除并激活 `application-integration.yml`。

### 1.2 测试环境

| 项 | 值 |
| --- | --- |
| JDK | 21（`java.version=21`） |
| Maven | 3.9.x（build-helper-maven-plugin 3.5.0 要求 Maven ≥ 3.6.3） |
| MySQL | 8.0，`127.0.0.1:3306`，库 `ry-vue`（集成冒烟用，可经 `SMOKE_MYSQL_*` 覆盖） |
| Redis | `127.0.0.1:16379`，密码 `123456`（集成冒烟用，可经 `SMOKE_REDIS_*` 覆盖） |
| Node | 22.x |
| 浏览器 | Google Chrome（Playwright `channel: chrome`） |
| 前端 dev server | http://127.0.0.1:5173 |

---

## 2. 后端测试用例（共 124 条）

> 其中单元/契约测试 112 条（§2.1–§2.13），真实环境集成冒烟 12 条（§2.14–§2.15）。

约定：**类型** U = 单元测试，C = 接口契约测试，I = 集成冒烟测试；**自动化** ✅ = 已纳入 `mvn test`（I 类需 `-Pintegration`）。

### 2.1 DetectConstantsTest — 检测常量（5 条）

| 编号 | 用例名称 | 输入/前置 | 预期结果 | 类型 |
| --- | --- | --- | --- | --- |
| BE-CONST-01 | 后缀白名单仅含 pdf/doc/docx/txt | 读取 `ALLOWED_EXT` | 恰好为这 4 个后缀 | U ✅ |
| BE-CONST-02 | MIME 白名单含 pdf / docx / octet-stream | 读取 `ALLOWED_MIME` | 含上述 3 类 MIME | U ✅ |
| BE-CONST-03 | 大小限制为 20MB | 读取 `MAX_FILE_SIZE` | 等于 `20 * 1024 * 1024` | U ✅ |
| BE-CONST-04 | 状态集合含 4 个状态 | 读取 `STATUS_*` | PENDING/RUNNING/DONE/FAILED | U ✅ |
| BE-CONST-05 | 当前仅文本模态 | 读取模态常量 | 仅 `text` 启用 | U ✅ |

### 2.2 ScenarioConstantsTest — 场景阈值常量（4 条）

| 编号 | 用例名称 | 输入/前置 | 预期结果 | 类型 |
| --- | --- | --- | --- | --- |
| BE-SCN-01 | 各场景默认红线符合运营口径 | 读取阈值 Map | 本科 20 / 硕士 15 / 博士 10 / 职业 15 / 自媒体 30 / 其他 25 | U ✅ |
| BE-SCN-02 | 未知场景兜底 OTHER(25) | `threshold("not_exist")` | 返回 25 | U ✅ |
| BE-SCN-03 | degreeType 旧字段迁移到新场景码 | 传旧 `degreeType` | 正确映射为新场景码 | U ✅ |
| BE-SCN-04 | label 展示名与兜底规则 | 已知/未知场景 | 已知返回中文名，未知返回兜底名 | U ✅ |

> 注：`threshold(null)` 的 NPE 防护为本次修复项，见 §5 缺陷记录 DEF-01。

### 2.3 ErrorCodeTest — 业务错误码（4 条）

| 编号 | 用例名称 | 预期结果 | 类型 |
| --- | --- | --- | --- |
| BE-ERR-01 | 所有错误码数值唯一 | 无重复码值 | U ✅ |
| BE-ERR-02 | 所有错误码文案非空 | `msg` 均非空 | U ✅ |
| BE-ERR-03 | 关键错误码数值符合分段约定 | 各段位与约定一致 | U ✅ |
| BE-ERR-04 | 错误码均在 4 位区间且前缀段不重复 | 值域校验通过 | U ✅ |

### 2.4 ParamUtilsTest — 参数取值工具（10 条）

| 编号 | 用例名称 | 预期结果 | 类型 |
| --- | --- | --- | --- |
| BE-PARAM-01 | 正常取值返回 `String.valueOf` | 非空值正确转字符串 | U ✅ |
| BE-PARAM-02 | map 为 null 或键不存在返回 null | 返回 null 不抛异常 | U ✅ |
| BE-PARAM-03 | 带默认值：缺失时返回默认值 | 命中默认值 | U ✅ |
| BE-PARAM-04 | Number 直接取 `longValue` | 数值正确 | U ✅ |
| BE-PARAM-05 | 数字字符串可解析为 Long | 解析成功 | U ✅ |
| BE-PARAM-06 | null 与非数字串转 Long 返回 null | 返回 null | U ✅ |
| BE-PARAM-07 | `toInt` 正常与异常路径 | 正常转值，异常返回 null | U ✅ |
| BE-PARAM-08 | `toDouble` 正常与异常路径 | 正常转值，异常返回 null | U ✅ |
| BE-PARAM-09 | `containsIgnoreCase` 大小写不敏感包含 | 忽略大小写命中 | U ✅ |
| BE-PARAM-10 | `isBlank` 空白判定 | null/空白为 true，其余 false | U ✅ |

### 2.5 PasswordHasherTest — 密码散列（5 条）

| 编号 | 用例名称 | 预期结果 | 类型 |
| --- | --- | --- | --- |
| BE-PWD-01 | hash 输出 `salt:sha256` 格式 | salt 16 位、摘要 64 位十六进制 | U ✅ |
| BE-PWD-02 | 相同明文两次 hash 不同 | 随机 salt 生效 | U ✅ |
| BE-PWD-03 | verify 正确明文通过 | 返回 true | U ✅ |
| BE-PWD-04 | verify 错误明文 / null / 无冒号格式失败 | 返回 false 且不抛异常 | U ✅ |
| BE-PWD-05 | tempPassword 长度 10 且含字母与数字 | 同时含字母和数字 | U ✅ |

### 2.6 AuthServiceImplTest — 认证服务（18 条）

| 编号 | 用例名称 | 输入 | 预期结果 | 类型 |
| --- | --- | --- | --- | --- |
| BE-AUTH-01 | 用户名为空 | `""` | `LOGIN_USERNAME_EMPTY` | U ✅ |
| BE-AUTH-02 | 密码为空 | `""` | `LOGIN_PASSWORD_EMPTY` | U ✅ |
| BE-AUTH-03 | 账号不存在（非 admin） | 不存在用户 | 记录失败次数并报错 | U ✅ |
| BE-AUTH-04 | admin/admin 且表内无账号 | admin/admin | 自动建管理员并签发 token | U ✅ |
| BE-AUTH-05 | 密码错误 | 错误密码 | 记录失败次数 | U ✅ |
| BE-AUTH-06 | 账号已停用 | 停用用户 | `ACCOUNT_DISABLED` | U ✅ |
| BE-AUTH-07 | 登录成功 | 正确凭据 | 清零失败计数、签发 token，有效期 7 天 | U ✅ |
| BE-AUTH-08 | 用户名含非法字符 | 非法用户名 | `REGISTER_USERNAME_INVALID` | U ✅ |
| BE-AUTH-09 | 开启验证码但未传 | 缺 captcha | `CAPTCHA_REQUIRED` | U ✅ |
| BE-AUTH-10 | 两次密码不一致 | 不一致 | `REGISTER_PASSWORD_MISMATCH` | U ✅ |
| BE-AUTH-11 | 弱密码（不含数字） | `abcdef` | `PASSWORD_WEAK` | U ✅ |
| BE-AUTH-12 | 用户名已存在 | 重复用户名 | `REGISTER_USERNAME_EXISTS` | U ✅ |
| BE-AUTH-13 | 注册成功 | 合法入参 | 落库并签发 USER 角色 token | U ✅ |
| BE-AUTH-14 | usernameAvailable 三态 | 非法/已存在/可用 | false / false / true | U ✅ |
| BE-AUTH-15 | me：token 无效 | 无效 token | `LOGIN_TOKEN_INVALID` | U ✅ |
| BE-AUTH-16 | me：token 有效 | 有效 token | 返回用户信息 | U ✅ |
| BE-AUTH-17 | 改密：两次新密码不一致 | 不一致 | `REGISTER_PASSWORD_MISMATCH` | U ✅ |
| BE-AUTH-18 | 改密：原密码错误 | 错误原密码 | `OLD_PASSWORD_WRONG` | U ✅ |

### 2.7 CaptchaServiceTest — 图形验证码（5 条）

| 编号 | 用例名称 | 预期结果 | 类型 |
| --- | --- | --- | --- |
| BE-CAP-01 | generate 返回非空 captchaId 与 PNG data URI | 两字段均有效 | U ✅ |
| BE-CAP-02 | 两次生成 captchaId 不同 | id 唯一 | U ✅ |
| BE-CAP-03 | null / 未知 id 校验失败 | 返回 false | U ✅ |
| BE-CAP-04 | 正确验证码通过（不区分大小写）且一次性消费 | 首次 true，复用 false | U ✅ |
| BE-CAP-05 | 错误验证码失败 | 返回 false | U ✅ |

### 2.8 DetectTaskServiceImplTest — 检测任务服务（22 条）

| 编号 | 用例名称 | 输入/前置 | 预期结果 | 类型 |
| --- | --- | --- | --- | --- |
| BE-TASK-01 | 提交空文件 | 空文件 | `DETECT_EXTRACT_FAILED` | U ✅ |
| BE-TASK-02 | 提交非法格式 | 不支持的格式 | `DETECT_FORMAT_UNSUPPORT` | U ✅ |
| BE-TASK-03 | 提交后无有效正文 | 全为非正文 | `DETECT_EXTRACT_FAILED` | U ✅ |
| BE-TASK-04 | 提交成功 | 正常论文 | 状态 DONE、汇总 AI 率、签发凭证、落库更新 | U ✅ |
| BE-TASK-05 | 提交未传 scenario | 仅传 degreeType | 旧字段迁移生效 | U ✅ |
| BE-TASK-06 | 全部段落推理失败 | 推理异常 | 状态 FAILED 且不发完成通知 | U ✅ |
| BE-TASK-07 | 列表：状态 + 关键字过滤、倒序分页 | 过滤参数 | 结果正确且按创建时间倒序 | U ✅ |
| BE-TASK-08 | 列表：关键字大小写不敏感 + AI 率区间 | 混合条件 | 命中正确 | U ✅ |
| BE-TASK-09 | 列表：页码越界 | 超范围页码 | 返回空行但总数不变 | U ✅ |
| BE-TASK-10 | 详情：任务不存在 | 不存在 id | `DETECT_TASK_NOT_FOUND` | U ✅ |
| BE-TASK-11 | 详情：填充指纹/验证地址并回填父任务对比 | 有 parent | 字段齐全 | U ✅ |
| BE-TASK-12 | 重试：原文件丢失 | 文件不可读 | 置 FAILED | U ✅ |
| BE-TASK-13 | 重试：文件可读 | 正常文件 | 重跑推理并回到 DONE | U ✅ |
| BE-TASK-14 | 取消：置 FAILED | 进行中任务 | 状态 FAILED | U ✅ |
| BE-TASK-15 | 取消：任务不存在 | 不存在 id | `DETECT_TASK_NOT_FOUND` | U ✅ |
| BE-TASK-16 | 删除：删除存储文件并移除记录 | 正常任务 | 文件与记录均删除 | U ✅ |
| BE-TASK-17 | 删除：任务不存在时静默返回 | 不存在 id | 不抛异常 | U ✅ |
| BE-TASK-18 | 统计：今日/本月/总数/达标率/30 天趋势 | 有数据 | 各指标正确 | U ✅ |
| BE-TASK-19 | 统计：无 DONE 任务 | 空数据 | 均值与达标率为 null | U ✅ |
| BE-TASK-20 | humanize：优先取任务段落原文 | 传 taskId | 取库中段落 | U ✅ |
| BE-TASK-21 | humanize：无 taskId 时用请求体 text | 传 text | 使用请求体文本 | U ✅ |
| BE-TASK-22 | detectParagraph / inferenceHealth 直接透传 | 正常调用 | 原样透传推理客户端 | U ✅ |

### 2.9 IpRateLimiterTest — IP 限流（3 条）

| 编号 | 用例名称 | 预期结果 | 类型 |
| --- | --- | --- | --- |
| BE-IP-01 | 未超限放行，超限抛 `AUTH_RATE_LIMITED` | 达到阈值后拒绝 | U ✅ |
| BE-IP-02 | `perMinute <= 0` 表示不限流 | 始终放行 | U ✅ |
| BE-IP-03 | 不同 IP / 不同 scope 互不影响 | 计数相互隔离 | U ✅ |

### 2.10 LoginAttemptGuardTest — 登录失败锁定（4 条）

| 编号 | 用例名称 | 预期结果 | 类型 |
| --- | --- | --- | --- |
| BE-LOCK-01 | 达到上限前返回剩余次数，达到后锁定 | 剩余次数递减并最终锁定 | U ✅ |
| BE-LOCK-02 | reset 清零失败计数与锁定 | 恢复可用 | U ✅ |
| BE-LOCK-03 | 用户名按 trim + 小写归并 | Admin 与 admin 同桶 | U ✅ |
| BE-LOCK-04 | 非法配置被夹紧为最小值 1 | 兜底为 1 | U ✅ |

### 2.11 ScenarioThresholdServiceImplTest — 场景阈值服务（6 条）

| 编号 | 用例名称 | 输入 | 预期结果 | 类型 |
| --- | --- | --- | --- | --- |
| BE-THR-01 | DB 无配置 | 空库 | 回退 `ScenarioConstants` 默认值 | U ✅ |
| BE-THR-02 | DB 有配置 | 有记录 | 取 DB 值并 HALF_UP 取整 | U ✅ |
| BE-THR-03 | scenario 为空 | null/空串 | 兜底 OTHER(25) | U ✅ |
| BE-THR-04 | label：DB 为空时回退常量展示名 | 无 label | 返回常量名 | U ✅ |
| BE-THR-05 | updateThreshold 后缓存失效 | 更新阈值 | 读到新值 | U ✅ |
| BE-THR-06 | listAll 直接委托仓储 | 调用 | 返回仓储结果 | U ✅ |

### 2.12 TextProcessorTest — 文本处理（13 条）

| 编号 | 用例名称 | 预期结果 | 类型 |
| --- | --- | --- | --- |
| BE-TXT-01 | MIME 命中白名单放行 | `isAllowedFormat` true | U ✅ |
| BE-TXT-02 | MIME 不可靠时按后缀兜底 | 依据后缀判定 | U ✅ |
| BE-TXT-03 | 不在白名单的格式拒绝 | 返回 false | U ✅ |
| BE-TXT-04 | null / 空白文本返回空列表 | 空列表 | U ✅ |
| BE-TXT-05 | 按空行分段，长段落各成一段 | 分段正确 | U ✅ |
| BE-TXT-06 | CRLF 换行同样可切分 | 分段正确 | U ✅ |
| BE-TXT-07 | 过短段落合并 | 段数少于输入行数 | U ✅ |
| BE-TXT-08 | 超长段落（>800 字）按句末标点切分且不超限 | 每段不超限 | U ✅ |
| BE-TXT-09 | 章节标题识别并归一化章节名 | 归一化正确 | U ✅ |
| BE-TXT-10 | 正文段落保留，继承当前章节名 | 继承正确 | U ✅ |
| BE-TXT-11 | 图表 caption 识别为 caption | 标注正确 | U ✅ |
| BE-TXT-12 | 命中「参考文献」后其后所有段落一并排除 | 后续段落全排除 | U ✅ |
| BE-TXT-13 | 致谢起始段标注为 acknowledgement | 标注正确 | U ✅ |

### 2.13 DetectControllerTest — 检测接口 HTTP 契约（13 条）

| 编号 | 用例名称 | 方法 / 路径 | 预期结果 | 类型 |
| --- | --- | --- | --- | --- |
| BE-API-01 | 提交论文 | POST `/api/v1/detect/submit` | `code=200`，回传 taskId / status | C ✅ |
| BE-API-02 | 任务列表 | GET `/api/v1/detect/tasks` | 返回 `{total, rows}` | C ✅ |
| BE-API-03 | 任务详情 | GET `/api/v1/detect/tasks/{id}` | 返回详情 | C ✅ |
| BE-API-04 | 复测对比 | GET `/api/v1/detect/tasks/{id}/compare` | 返回对比视图 | C ✅ |
| BE-API-05 | 重试 | POST `/api/v1/detect/tasks/{id}/retry` | 返回最新详情 | C ✅ |
| BE-API-06 | 取消 | POST `/api/v1/detect/tasks/{id}/cancel` | `code=200` 空数据 | C ✅ |
| BE-API-07 | 删除 | DELETE `/api/v1/detect/tasks/{id}` | `code=200` | C ✅ |
| BE-API-08 | 统计 | GET `/api/v1/detect/statistics` | 返回统计字段 | C ✅ |
| BE-API-09 | 降 AIGC | POST `/api/v1/humanize` | 返回改写结果 | C ✅ |
| BE-API-10 | 直接文本检测（合法） | POST `/api/v1/detect/paragraph` | 透传推理结果 | C ✅ |
| BE-API-11 | 直接文本检测（空文本） | POST `/api/v1/detect/paragraph` | 参数校验失败 `code=1001` | C ✅ |
| BE-API-12 | 场景阈值列表 | GET `/api/v1/detect/scenario-thresholds` | 返回启用配置列表 | C ✅ |
| BE-API-13 | 推理健康检查 | GET `/api/v1/detect/health` | 返回推理健康状态 | C ✅ |

### 2.14 MySqlIntegrationSmokeTest — MySQL 集成冒烟（5 条）

> 真实 DataSource + Mapper + Repository，`@SpringBootTest` + `@ActiveProfiles("integration")`，
> 连接 `application-integration.yml` 指定的真实库。写入数据带 `SMOKE-IT-` 前缀并在 `@AfterEach` 物理清理。

| 编号 | 用例名称 | 输入/前置 | 预期结果 | 类型 |
| --- | --- | --- | --- | --- |
| BE-INT-MY-01 | DataSource 建立真实连接并连到目标库 | 真实 MySQL | `isValid` true、产品为 MySQL、catalog=`ry-vue`、`SELECT VERSION()` 非空 | I ✅ |
| BE-INT-MY-02 | 核心业务表均已建好 | 真实库 information_schema | `detect_task` / `detect_scenario_threshold` / `detect_paragraph_result` / `detect_sentence_result` 四表均存在 | I ✅ |
| BE-INT-MY-03 | 场景阈值种子数据可读 | 真实库 | 启用行非空且字段完整；`academic_master` 阈值 > 0 | I ✅ |
| BE-INT-MY-04 | detect_task 主子表写入→读回组装→更新替换→删除级联 | 构造 2 段 3 句任务 | JSON 列（`source_labels_json`/`confidence_interval`/`warnings_json`）正确反序列化；段按 `paragraph_idx` 升序、句按 `sentence_idx` 升序组装；更新后子表被替换为 1 段 1 句；删除后主表与子表记录均清空 | I ✅ |
| BE-INT-MY-05 | findAll 按 createdAt 倒序 | 插入新旧两条 | 返回序列 `createdAt` 单调不增，新记录排在前 | I ✅ |

### 2.15 RedisIntegrationSmokeTest — Redis 集成冒烟（7 条）

> 真实 Lettuce 连接（`spring-boot-starter-data-redis`，test 作用域），验证部署环境 Redis 可用性。
> 业务代码本身不消费 Redis（限流/登录锁定为进程内实现），故仅做环境冒烟。

| 编号 | 用例名称 | 预期结果 | 类型 |
| --- | --- | --- | --- |
| BE-INT-RD-01 | 连接可用性 | 底层为 `LettuceConnectionFactory`，`PING` 返回 `PONG` | I ✅ |
| BE-INT-RD-02 | 服务端 INFO 可读 | `redis_version` 非空 | I ✅ |
| BE-INT-RD-03 | String 读写删 | `set/get/hasKey/delete` 一致，重复删除返回 false | I ✅ |
| BE-INT-RD-04 | TTL 过期 | 设置 1s 过期后 TTL∈[0,1]，等待后键自动消失 | I ✅ |
| BE-INT-RD-05 | 原子自增 | `INCR` 三次依次得 1/2/3，值为 `"3"` | I ✅ |
| BE-INT-RD-06 | Hash 读写 | `putAll` 后 `entries` 含全部字段 | I ✅ |
| BE-INT-RD-07 | 多库隔离 | db15 写入的键在 db0 不可见 | I ✅ |

---

## 3. 前端 E2E 测试用例（共 27 条）

约定：所有 `/api/v1/**` 请求由 Playwright `page.route` 拦截并返回 fixture，因此用例只验证前端渲染、交互与路由，与后端实现解耦。

### 3.1 auth.spec.ts — 登录 / 注册 · 认证（9 条）

| 编号 | 用例名称 | 步骤 | 预期结果 |
| --- | --- | --- | --- |
| E2E-AUTH-01 | 未登录访问受保护路由 | 直接访问 `/dashboard` | 重定向到 `/login`，展示登录页 |
| E2E-AUTH-02 | 表单空值禁用提交 | 账号/密码留空 | 提交按钮 disabled；两项填齐后 enabled |
| E2E-AUTH-03 | 登录成功跳转 | 填账号密码并提交 | 跳转 `/dashboard` 并加载「检测记录」列表 |
| E2E-AUTH-04 | 登录失败提示 | mock 返回「用户名或密码错误」 | 展示 `.alert` 错误文案 |
| E2E-AUTH-05 | 切换到注册模式 | 点击「立即注册」 | URL 带 `mode=register`，出现确认密码与验证码字段 |
| E2E-AUTH-06 | 注册密码规则实时校验 | 输入 `abc` → `abc123` | 「含数字」「6-32 位」规则由未满足变满足 |
| E2E-AUTH-07 | 注册成功自动登录 | 填全字段并勾选同意后提交 | 跳转 `/dashboard` |
| E2E-AUTH-08 | 登录态持久化 | 登录后读 localStorage | `access_token` 与 `user_info.username` 正确 |
| E2E-AUTH-09 | 密码可见性切换 | 点击眼睛按钮 | `type` 由 `password` 变 `text` |

### 3.2 dashboard.spec.ts — 检测记录 Dashboard（5 条）

| 编号 | 用例名称 | 预期结果 |
| --- | --- | --- |
| E2E-DASH-01 | 渲染统计卡片、趋势图与列表 | 4 张统计卡 + 趋势卡 + 2 条任务可见 |
| E2E-DASH-02 | 任务状态中文标签 | 列表含「已完成」「检测中」 |
| E2E-DASH-03 | 无任务空状态 | 展示「还没有检测记录」与「去上传」 |
| E2E-DASH-04 | 点击标题进入详情 | 跳转 `/task/101` |
| E2E-DASH-05 | 顶部导航进入上传页 | 跳转 `/upload` |

### 3.3 upload.spec.ts — 论文检测 · 上传 / 粘贴（6 条）

| 编号 | 用例名称 | 预期结果 |
| --- | --- | --- |
| E2E-UP-01 | 默认上传模式渲染 | 6 个场景卡 + 投放区可见，CTA 禁用 |
| E2E-UP-02 | 切换场景红线联动 | 选「学术·博士」后红线显示 `≤ 10%` |
| E2E-UP-03 | 选择文件并提交 | 显示文件名，CTA 可用，提交后跳 `/task/999` |
| E2E-UP-04 | 拒绝不支持格式 | 提示「只支持 PDF / Word / TXT」，不生成已选文件 |
| E2E-UP-05 | 粘贴即时检测 | 展示校准概率 `25.0%` 与结论「更像人写」 |
| E2E-UP-06 | 短文本可靠性提示 | 少于 120 字提示「不足 120 字」 |

### 3.4 taskdetail.spec.ts — 检测报告详情（3 条）

| 编号 | 用例名称 | 预期结果 |
| --- | --- | --- |
| E2E-TASK-01 | 渲染 AI 率 / 红线 / 标题 | 显示 `12.5`、`红线 15%`、论文标题 |
| E2E-TASK-02 | 正文与非正文区分 | 2 个段落卡片，参考文献段落带排除徽标 |
| E2E-TASK-03 | 关键动作可见 | 下载/报告类按钮可见 |

### 3.5 verify.spec.ts — 报告真伪验证 · 公开页（4 条）

| 编号 | 用例名称 | 预期结果 |
| --- | --- | --- |
| E2E-VER-01 | 未登录可访问 | 展示「验证检测报告」，停留 `/verify` |
| E2E-VER-02 | 缺参数前端拦截 | 提示「请输入报告编号和验证码」 |
| E2E-VER-03 | 输入编号+验证码 | 展示「报告真实有效」与编号 |
| E2E-VER-04 | URL 带参数自动验证 | 直接展示验证结果 |

---

## 4. 需求覆盖矩阵

| 功能点 | 后端用例 | 前端用例 |
| --- | --- | --- |
| 登录 / 注册 / 改密 | BE-AUTH-01…18、BE-PWD-01…05、BE-CAP-01…05、BE-LOCK-01…04、BE-IP-01…03 | E2E-AUTH-01…09 |
| 上传论文（格式/大小/场景） | BE-TASK-01…05、BE-TXT-01…03、BE-CONST-01…05 | E2E-UP-01…04 |
| 文本粘贴即时检测 | BE-API-10、BE-API-11 | E2E-UP-05、E2E-UP-06 |
| 段落切分与非正文过滤 | BE-TXT-04…13 | E2E-TASK-02 |
| 检测任务生命周期 | BE-TASK-06…17 | E2E-DASH-01…05、E2E-TASK-01…03 |
| 统计与趋势 | BE-TASK-18、BE-TASK-19、BE-API-08 | E2E-DASH-01 |
| 场景阈值配置 | BE-SCN-01…04、BE-THR-01…06、BE-API-12 | E2E-UP-02 |
| 报告签发与验证 | BE-TASK-11 | E2E-VER-01…04 |
| 错误码与参数工具 | BE-ERR-01…04、BE-PARAM-01…10 | — |
| 部署环境连通性（MySQL/Redis） | BE-INT-MY-01…05、BE-INT-RD-01…07 | — |

---

## 5. 缺陷与风险记录

| 编号 | 类型 | 描述 | 影响 | 状态 |
| --- | --- | --- | --- | --- |
| DEF-01 | 缺陷（已修复） | `ScenarioConstants.threshold(null)` 在 `Map.of(...).getOrDefault(null, ...)` 上抛 NPE | 未传/传空场景时 500 | 已修复：入口增加 null/blank 判断，兜底 OTHER(25)，见 BE-SCN-02、BE-THR-03 |
| DEF-02 | 体验缺陷（待修复） | 登录页账号框自动聚焦；若账号为空，点击底部「立即注册」时 blur 立即插入「请输入账号」错误文案导致布局位移，使 `mousedown`/`mouseup` 落在不同元素上，点击落空 | 空账号下首次点击「立即注册」无响应 | 待修复（E2E 用例 E2E-AUTH-05 已规避并记录） |
| DEF-03 | 缺陷（已修复） | JDBC 连接串使用 `characterEncoding=utf8mb4`，但 `utf8mb4` 不是合法 Java 字符集名，Connector/J 抛 `UnsupportedEncodingException: utf8mb4`，导致数据源**完全无法建连** | 应用/容器一旦访问 MySQL 即失败（`mvn test` 全 Mock 时不可见，集成冒烟测试暴露） | 已修复：`utf8mb4` → `utf8`（Java 别名，Connector/J 8 映射为服务端 utf8mb4）。涉及 `application.yml`、`application-integration.yml`、`deploy/docker-compose.yml` 三处 |
| RISK-01 | 测试盲区（已缓解） | 后端原为纯 Mock 单测，未覆盖真实 MySQL/Redis 联调 | 集成层问题可能漏检 | 已缓解：新增 12 条集成冒烟（§2.14、§2.15），覆盖真实库连通、表结构、主子表事务、JSON 列与 Redis 基础语义；推理服务联调仍为后续项 |
| RISK-02 | 测试盲区 | 前端 E2E 拦截了全部 API，未做前后端契约联调 | 接口字段不一致可能漏检 | 已知，建议补充契约测试 |
| RISK-03 | 覆盖缺口 | 运营后台（`/admin/*`）、移动端 uni-app 未纳入本轮 | 相关回归风险 | 已知，后续迭代补充 |

---

## 6. 结论

- 后端 124 条用例（112 单元/契约 + 12 集成冒烟）、前端 27 条用例全部通过，主链路（登录 → 上传/粘贴 → 检测 → 报告 → 验证）具备自动化回归能力。
- 发现 2 个功能性缺陷（DEF-01、DEF-03，均已修复）与 1 个体验缺陷（DEF-02，待修复）；其中 DEF-03（JDBC 字符集非法导致数据源无法建连）由本轮集成冒烟测试首次暴露，纯 Mock 单测无法发现。
- 建议下一步：`mvn test` 作为合并门禁（零外部依赖，稳定快跑）；真实环境联调冒烟以 `mvn test -Pintegration` 在具备 MySQL/Redis 的流水线阶段执行；推理服务联调与前后端契约测试作为后续补充。
