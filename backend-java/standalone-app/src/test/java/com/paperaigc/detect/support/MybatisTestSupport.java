package com.paperaigc.detect.support;

import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.core.metadata.TableInfoHelper;
import org.apache.ibatis.builder.MapperBuilderAssistant;

/**
 * 测试辅助：在无 Spring 容器 / 无 MyBatis 启动流程下，手动初始化实体 TableInfo，
 * 使 LambdaQueryWrapper / LambdaUpdateWrapper 能解析方法引用到列名。
 */
public final class MybatisTestSupport {

    private MybatisTestSupport() {}

    private static volatile boolean initialized = false;

    public static synchronized void init(Class<?>... entities) {
        if (initialized) return;
        MybatisConfiguration configuration = new MybatisConfiguration();
        MapperBuilderAssistant assistant = new MapperBuilderAssistant(configuration, "");
        for (Class<?> entity : entities) {
            TableInfoHelper.initTableInfo(assistant, entity);
        }
        initialized = true;
    }
}
