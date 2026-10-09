package com.paperaigc.detect.integration;

import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.redis.connection.RedisConnection;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.connection.RedisPassword;
import org.springframework.data.redis.connection.RedisStandaloneConfiguration;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.test.context.ActiveProfiles;

import java.time.Duration;
import java.util.Map;
import java.util.Properties;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Redis 集成冒烟测试 —— 真实连接 + 读写 / TTL / 原子自增 / Hash / 多库隔离
 *
 * <p>目的：验证部署环境中 Redis 的连通性与基本语义。业务代码本身不依赖 Redis
 * （限流与登录锁定为进程内实现），故本用例只做环境可用性冒烟。</p>
 *
 * <p>默认不参与 {@code mvn test}（被 Surefire 按 {@code @Tag("integration")} 排除）。
 * 运行：{@code mvn test -Pintegration -Dtest=RedisIntegrationSmokeTest}</p>
 *
 * <p>连接参数见 {@code src/test/resources/application-integration.yml}，可用
 * {@code SMOKE_REDIS_*} 环境变量覆盖。</p>
 */
@Tag("integration")
@SpringBootTest(classes = com.paperaigc.app.PaperAigcApplication.class,
        webEnvironment = SpringBootTest.WebEnvironment.NONE)
@ActiveProfiles("integration")
@DisplayName("Redis 集成冒烟 · 真实连接与基础语义")
class RedisIntegrationSmokeTest {

    private static final String KEY_PREFIX = "smoke:it:";
    /** 用于多库隔离验证的独立库号（默认 16 库，取末位避免与业务库冲突） */
    private static final int ALT_DB = 15;

    @Autowired private StringRedisTemplate redisTemplate;
    @Autowired private RedisConnectionFactory connectionFactory;

    @Value("${spring.data.redis.host}") private String host;
    @Value("${spring.data.redis.port}") private int port;
    @Value("${spring.data.redis.password:}") private String password;

    private static LettuceConnectionFactory altDbFactory;
    private static StringRedisTemplate altDbTemplate;

    private final String runKey = KEY_PREFIX + UUID.randomUUID();

    @AfterAll
    static void tearDownAltDatabase() {
        if (altDbFactory != null) {
            altDbFactory.destroy();
        }
    }

    /* ==================== 连通性 ==================== */

    @Test
    @DisplayName("连接可用：PING → PONG，且底层为 Lettuce")
    void pingReturnsPong() {
        assertThat(connectionFactory).isInstanceOf(LettuceConnectionFactory.class);
        try (RedisConnection conn = connectionFactory.getConnection()) {
            assertThat(conn.ping()).isEqualTo("PONG");
        }
        // 清理可能的残留
        redisTemplate.delete(runKey);
    }

    @Test
    @DisplayName("服务端 INFO 可读且版本非空")
    void serverInfoReadable() {
        Properties info = redisTemplate.execute((RedisConnection conn) ->
                conn.serverCommands().info("server"));
        assertThat(info).isNotNull();
        assertThat(info.getProperty("redis_version")).isNotBlank();
    }

    /* ==================== 基础语义 ==================== */

    @Test
    @DisplayName("String 读写删：set/get/hasKey/delete 一致")
    void stringRoundTrip() {
        redisTemplate.opsForValue().set(runKey, "hello-redis");
        assertThat(redisTemplate.hasKey(runKey)).isTrue();
        assertThat(redisTemplate.opsForValue().get(runKey)).isEqualTo("hello-redis");

        assertThat(redisTemplate.delete(runKey)).isTrue();
        assertThat(redisTemplate.hasKey(runKey)).isFalse();
        assertThat(redisTemplate.delete(runKey)).isFalse();
    }

    @Test
    @DisplayName("TTL：设置 1s 过期后键自动消失")
    void ttlExpiresKey() throws InterruptedException {
        redisTemplate.opsForValue().set(runKey, "temp", Duration.ofSeconds(1));
        Long ttl = redisTemplate.getExpire(runKey);
        assertThat(ttl).isNotNull().isBetween(0L, 1L);

        Thread.sleep(1300);
        assertThat(redisTemplate.hasKey(runKey)).isFalse();
    }

    @Test
    @DisplayName("原子自增：INCR 三次得到 3")
    void atomicIncrement() {
        redisTemplate.delete(runKey);
        assertThat(redisTemplate.opsForValue().increment(runKey)).isEqualTo(1L);
        assertThat(redisTemplate.opsForValue().increment(runKey)).isEqualTo(2L);
        assertThat(redisTemplate.opsForValue().increment(runKey)).isEqualTo(3L);
        assertThat(redisTemplate.opsForValue().get(runKey)).isEqualTo("3");
        redisTemplate.delete(runKey);
    }

    @Test
    @DisplayName("Hash 读写：字段写入后整表可读")
    void hashRoundTrip() {
        redisTemplate.opsForHash().putAll(runKey, Map.of("status", "done", "aiRate", "12.34"));
        Map<Object, Object> entries = redisTemplate.opsForHash().entries(runKey);
        assertThat(entries)
                .containsEntry("status", "done")
                .containsEntry("aiRate", "12.34");
        redisTemplate.delete(runKey);
    }

    /* ==================== 多库隔离 ==================== */

    @Test
    @DisplayName("多库隔离：db15 写入的键在 db0 不可见")
    void multiDatabaseIsolation() {
        StringRedisTemplate alt = altDatabaseTemplate();

        String key = KEY_PREFIX + "db15:" + UUID.randomUUID();
        alt.opsForValue().set(key, "in-db15");

        try {
            assertThat(alt.opsForValue().get(key)).isEqualTo("in-db15");
            // 默认模板连的是 db0，不应看到 db15 的键
            assertThat(redisTemplate.hasKey(key)).isFalse();
        } finally {
            alt.delete(key);
        }
    }

    private StringRedisTemplate altDatabaseTemplate() {
        if (altDbTemplate == null) {
            RedisStandaloneConfiguration cfg = new RedisStandaloneConfiguration(host, port);
            if (password != null && !password.isBlank()) {
                cfg.setPassword(RedisPassword.of(password));
            }
            cfg.setDatabase(ALT_DB);
            altDbFactory = new LettuceConnectionFactory(cfg);
            altDbFactory.afterPropertiesSet();
            altDbTemplate = new StringRedisTemplate(altDbFactory);
            altDbTemplate.afterPropertiesSet();
        }
        return altDbTemplate;
    }
}
