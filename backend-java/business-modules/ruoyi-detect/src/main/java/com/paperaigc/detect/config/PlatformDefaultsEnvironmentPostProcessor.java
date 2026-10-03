package com.paperaigc.detect.config;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.env.EnvironmentPostProcessor;
import org.springframework.boot.env.YamlPropertySourceLoader;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.MutablePropertySources;
import org.springframework.core.env.PropertySource;
import org.springframework.core.io.ClassPathResource;

import java.io.IOException;
import java.util.List;

/**
 * 把 {@code classpath:platform-defaults.yml} 里的 {@code platform.*} 默认值追加进 Environment。
 *
 * <p><b>要解决的问题</b>：若依基座态 {@code ruoyi-admin} 的 application-dev.yml 只声明了
 * {@code platform.inference.{host,port}}，而 {@code deploy/docker-compose.yml} 用
 * {@code SPRING_PROFILES_ACTIVE=prod} 启动，dev profile 不加载；{@code platform.assistant.*}
 * 与 {@code platform.storage.*} 在若依态从未被声明过。原先只能靠 {@code @Value} 的行内兜底值，
 * 既不可审查也容易写错（{@code platform.storage} 曾把 {@code local-root} 写成 {@code local-path}）。</p>
 *
 * <p><b>为什么不直接在 application.yml 里写</b>：{@code ruoyi-admin/src/main/resources} 属于若依基座，
 * 本仓库只保留业务模块（见 {@code RUOYI_INTEGRATION.md}），部署镜像里的基座是 clone 来的，
 * 改本地基座副本不会被带进镜像。用 EnvironmentPostProcessor 则随本模块一起被构建。
 * 本模块的 {@code spring.factories} 也未被 standalone-app 的 build-helper 排除（那里只排
 * {@code META-INF/spring/**}），所以两种后端形态共用同一份默认值。</p>
 *
 * <p><b>优先级</b>：以 {@code addLast} 追加，优先级最低。application.yml、profile 文件、
 * 命令行参数、环境变量都能覆盖它 —— 它只负责"没配的时候有个可审查的正确值"。</p>
 *
 * <p>启动阶段很早执行，故不依赖 Lombok / SLF4J 绑定，失败只打印到 stderr，不阻断启动：
 * 缺这个文件不该让服务起不来，{@code @Value} 的行内兜底仍然在。</p>
 */
public class PlatformDefaultsEnvironmentPostProcessor implements EnvironmentPostProcessor {

    /** 默认值配置文件；随本模块打包，若依态与 standalone 共用 */
    private static final String DEFAULTS_LOCATION = "platform-defaults.yml";

    @Override
    public void postProcessEnvironment(ConfigurableEnvironment environment, SpringApplication application) {
        MutablePropertySources sources = environment.getPropertySources();

        // 幂等：YamlPropertySourceLoader 以文件名作为 source 名，重复追加前先判断
        if (sources.contains(DEFAULTS_LOCATION)) {
            return;
        }

        ClassPathResource resource = new ClassPathResource(DEFAULTS_LOCATION);
        if (!resource.exists()) {
            System.err.println("[PlatformDefaults] 未找到 classpath:" + DEFAULTS_LOCATION
                    + "，platform.* 将退化为各 @Value 的行内兜底值");
            return;
        }

        List<PropertySource<?>> loaded;
        try {
            loaded = new YamlPropertySourceLoader().load(DEFAULTS_LOCATION, resource);
        } catch (IOException e) {
            System.err.println("[PlatformDefaults] 读取 classpath:" + DEFAULTS_LOCATION
                    + " 失败，platform.* 将退化为各 @Value 的行内兜底值：" + e.getMessage());
            return;
        }

        if (loaded.isEmpty()) {
            return;
        }

        // addLast = 优先级最低，只填没人配过的键
        for (PropertySource<?> source : loaded) {
            sources.addLast(source);
        }
    }
}
