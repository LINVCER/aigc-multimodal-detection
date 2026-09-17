# Java 后端多阶段构建：
#   1) builder: clone 若依基座 → 挂业务模块 → mvn package
#   2) runtime: JRE + jar
# 上下文 = 仓库根（compose 里 context: .. 已设置）

# ============ Builder ============
FROM maven:3.9-eclipse-temurin-21 AS builder

ARG RUOYI_GIT_URL=https://gitee.com/dromara/RuoYi-Vue-Plus.git
ARG RUOYI_BRANCH=5.X

WORKDIR /build

# 配 Maven 阿里云镜像加速
RUN mkdir -p /root/.m2 && cat > /root/.m2/settings.xml <<'EOF'
<settings>
  <mirrors>
    <mirror>
      <id>aliyunmaven</id>
      <mirrorOf>*</mirrorOf>
      <name>aliyun</name>
      <url>https://maven.aliyun.com/repository/public</url>
    </mirror>
  </mirrors>
</settings>
EOF

# 1) clone 若依基座（--depth 1 加速）
RUN git clone --depth 1 --branch ${RUOYI_BRANCH} ${RUOYI_GIT_URL} ruoyi

# 2) 复制业务模块进 ruoyi-modules
COPY backend-java/business-modules/ruoyi-detect     ruoyi/ruoyi-modules/ruoyi-detect
COPY backend-java/business-modules/ruoyi-inference  ruoyi/ruoyi-modules/ruoyi-inference

# 3) 挂载业务模块到聚合 pom + 让 ruoyi-admin 依赖 ruoyi-detect
#    用 sed 在 </modules> 前插入两行；用 xmllint 的方案更稳但需装包，sed 够用
RUN sed -i '/<\/modules>/i\        <module>ruoyi-detect</module>\n        <module>ruoyi-inference</module>' \
        ruoyi/ruoyi-modules/pom.xml && \
    sed -i '/<\/dependencies>/i\        <dependency>\n            <groupId>org.dromara</groupId>\n            <artifactId>ruoyi-detect</artifactId>\n            <version>${revision}</version>\n        </dependency>' \
        ruoyi/ruoyi-admin/pom.xml && \
    echo "===== 校验业务模块已挂载 =====" && \
    grep -c "ruoyi-detect\|ruoyi-inference" ruoyi/ruoyi-modules/pom.xml

# 4) 业务模块 pom 里写死的 5.2.3 parent 版本需要对齐若依实际版本
#    从 ruoyi 根 pom 读 revision 再刷入两个业务模块
RUN REVISION=$(grep -m1 '<revision>' ruoyi/pom.xml | sed 's/.*<revision>\(.*\)<\/revision>.*/\1/') && \
    echo "detected RuoYi revision: ${REVISION}" && \
    for M in ruoyi-detect ruoyi-inference; do \
      sed -i "s|<version>5\.[0-9]\+\.[0-9]\+</version>|<version>${REVISION}</version>|" \
              ruoyi/ruoyi-modules/${M}/pom.xml; \
    done

# 5) 打包（跳测试；跳 protobuf 编译若无 proto 需求可去掉 -pl 中的 ruoyi-inference）
RUN cd ruoyi && \
    mvn -B -T 1C -pl ruoyi-admin -am -DskipTests package && \
    ls -lh ruoyi-admin/target/*.jar

# ============ Runtime ============
FROM eclipse-temurin:21-jre-alpine

RUN apk add --no-cache curl fontconfig ttf-dejavu tzdata && \
    cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    echo "Asia/Shanghai" > /etc/timezone

WORKDIR /app

COPY --from=builder /build/ruoyi/ruoyi-admin/target/*.jar app.jar

EXPOSE 8080

ENV JAVA_TOOL_OPTIONS="-Xms512m -Xmx1536m -XX:+UseZGC -Djava.security.egd=file:/dev/./urandom"

HEALTHCHECK --interval=15s --timeout=5s --retries=20 --start-period=60s \
  CMD curl -fsS http://localhost:8080/actuator/health || exit 1

ENTRYPOINT ["java", "-jar", "/app/app.jar"]
