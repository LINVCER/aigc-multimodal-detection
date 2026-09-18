#!/usr/bin/env bash
# W3.a · 若依基座 + 业务模块一键挂载（Linux/macOS/WSL）
# 用法：bash scripts/setup-ruoyi.sh [目标目录]
# 默认在 backend-java/.workspace/ 下拉取若依代码。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # backend-java/
TARGET="${1:-$HERE/.workspace}"
RUOYI_BRANCH="5.X"
RUOYI_REPO_GITEE="https://gitee.com/dromara/RuoYi-Vue-Plus.git"
RUOYI_REPO_GITHUB="https://github.com/dromara/RuoYi-Vue-Plus.git"
PLUS_UI_REPO="https://gitee.com/JavaLionLi/plus-ui.git"

mkdir -p "$TARGET"
cd "$TARGET"

# ---------- 1. clone 若依基座 ----------
if [[ ! -d "RuoYi-Vue-Plus" ]]; then
  echo "[1/4] clone RuoYi-Vue-Plus ($RUOYI_BRANCH)"
  if git clone --depth 1 -b "$RUOYI_BRANCH" "$RUOYI_REPO_GITEE" RuoYi-Vue-Plus 2>/dev/null; then :;
  else
    echo "  gitee 失败，退回 github"
    git clone --depth 1 -b "$RUOYI_BRANCH" "$RUOYI_REPO_GITHUB" RuoYi-Vue-Plus
  fi
else
  echo "[1/4] RuoYi-Vue-Plus 已存在，跳过 clone"
fi

# ---------- 2. clone plus-ui 前端 ----------
if [[ ! -d "plus-ui" ]]; then
  echo "[2/4] clone plus-ui"
  git clone --depth 1 "$PLUS_UI_REPO" plus-ui || echo "  plus-ui 拉取失败，可稍后手动 clone"
else
  echo "[2/4] plus-ui 已存在，跳过 clone"
fi

# ---------- 3. 挂载业务模块（软链，Windows 走 setup-ruoyi.ps1）----------
MODULES_DIR="RuoYi-Vue-Plus/ruoyi-modules"
echo "[3/4] 挂载 business-modules → $MODULES_DIR/"
for m in ruoyi-detect ruoyi-inference; do
  src="$HERE/business-modules/$m"
  dst="$MODULES_DIR/$m"
  if [[ -e "$dst" ]]; then
    echo "  $m 已挂载，跳过"
    continue
  fi
  if [[ ! -d "$src" ]]; then
    echo "  ⚠ $src 不存在，跳过（可能还没实现）"
    continue
  fi
  ln -sfn "$src" "$dst"
  echo "  ln $m"
done

# ---------- 4. 提示 ----------
cat <<EOF

[4/4] 挂载完成。下一步：

  1) 在 $TARGET/RuoYi-Vue-Plus/ruoyi-modules/pom.xml 的 <modules> 里追加：
       <module>ruoyi-detect</module>
       <module>ruoyi-inference</module>

  2) 在 $TARGET/RuoYi-Vue-Plus/ruoyi-admin/pom.xml 追加依赖：
       <dependency>
         <groupId>org.dromara</groupId>
         <artifactId>ruoyi-detect</artifactId>
         <version>\${revision}</version>
       </dependency>

  3) 数据库初始化（先建库再跑）：
       mysql -uroot -p < $TARGET/RuoYi-Vue-Plus/script/sql/ry_vue_5.X.sql
       mysql -uroot -p ry-vue < $HERE/scripts/patch-schema.sql

  4) 启动：cd $TARGET/RuoYi-Vue-Plus && mvn -pl ruoyi-admin -am spring-boot:run

  5) 前端：cd $TARGET/plus-ui && pnpm install && pnpm dev
EOF
