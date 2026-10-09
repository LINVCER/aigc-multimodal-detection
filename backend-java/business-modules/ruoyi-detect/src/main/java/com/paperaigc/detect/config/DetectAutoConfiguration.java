package com.paperaigc.detect.config;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.ComponentScan;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

import java.util.concurrent.Executor;

/**
 * ruoyi-detect 业务模块自动装配
 *
 * <p>基座 DromaraApplication 只扫 {@code org.dromara.*}；本模块类落在 {@code com.paperaigc.detect.*}
 * 不在扫描范围内，@Service / @Repository / @Component / @RestController / @RestControllerAdvice
 * 都不会被注册。</p>
 *
 * <p>通过 Spring Boot 3 AutoConfiguration SPI 让基座自动加载本配置（无需改基座启动类）：
 * 见 {@code src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports}</p>
 *
 * <p>备选：如无法通过 SPI 装载，可在基座 DromaraApplication 上补
 * {@code @SpringBootApplication(scanBasePackages = {"org.dromara", "com.paperaigc"})}。</p>
 */
@Configuration
@MapperScan("com.paperaigc.detect.mapper")
@ComponentScan(basePackages = "com.paperaigc.detect")
public class DetectAutoConfiguration {

    /**
     * 检测推理执行器：submit 入队后立即返回，段落级推理在此线程池异步执行。
     * 单机 CPU 推理较慢，先 2 个核心线程串行消化队列；队列满由 AbortPolicy 拒绝，
     * Service 捕获后把任务置 FAILED 而非阻塞提交线程。
     */
    @Bean("detectExecutor")
    public Executor detectExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(2);
        executor.setMaxPoolSize(4);
        executor.setQueueCapacity(200);
        executor.setThreadNamePrefix("detect-");
        executor.setWaitForTasksToCompleteOnShutdown(true);
        executor.setAwaitTerminationSeconds(30);
        executor.initialize();
        return executor;
    }
}
