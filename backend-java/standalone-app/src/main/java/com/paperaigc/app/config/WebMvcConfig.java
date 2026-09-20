package com.paperaigc.app.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Web MVC 配置 · 跨域
 *
 * <p>注意：当前认证逻辑由业务层自研（AuthServiceImpl + InMemoryAuthTokenRepository），
 * 未启用 Sa-Token 登录态拦截。Controller 上的 @SaIgnore 仅作标记，无运行时效果。
 * 如需接入 Sa-Token 认证，可在此类中加 SaInterceptor。</p>
 */
@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    /**
     * 全局跨域（开发用，生产走 Nginx 就不需要）
     */
    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/**")
                .allowedOriginPatterns("*")
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
                .allowedHeaders("*")
                .allowCredentials(true)
                .maxAge(3600);
    }
}
