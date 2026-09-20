package com.paperaigc.app;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 独立 Spring Boot 启动入口（不依赖若依基座）
 *
 * <p>业务代码在 {@code com.paperaigc.detect.*} 下，通过 build-helper-maven-plugin
 * 把 ruoyi-detect 模块源码纳入编译，此处直接扫描即可。</p>
 *
 * <p>启动方式：
 * <pre>
 *   cd backend-java/standalone-app
 *   mvn spring-boot:run
 *   # 或打包后：
 *   mvn package
 *   java -jar target/standalone-app-0.1.0-SNAPSHOT.jar
 * </pre>
 */
@SpringBootApplication(scanBasePackages = "com.paperaigc")
@MapperScan("com.paperaigc.detect.mapper")
public class PaperAigcApplication {

    public static void main(String[] args) {
        SpringApplication.run(PaperAigcApplication.class, args);
    }
}
