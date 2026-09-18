# W3.a · 若依基座 + 业务模块一键挂载（Windows PowerShell 5.1+）
# 用法：powershell -ExecutionPolicy Bypass -File scripts/setup-ruoyi.ps1 [-Target <目录>]
param(
    [string]$Target = ""
)

$ErrorActionPreference = 'Stop'
$Here = Resolve-Path (Join-Path $PSScriptRoot '..')   # backend-java/
if ([string]::IsNullOrWhiteSpace($Target)) {
    $Target = Join-Path $Here '.workspace'
}
$RuoyiBranch    = '5.X'
$RuoyiRepoGitee = 'https://gitee.com/dromara/RuoYi-Vue-Plus.git'
$RuoyiRepoGh    = 'https://github.com/dromara/RuoYi-Vue-Plus.git'
$PlusUiRepo     = 'https://gitee.com/JavaLionLi/plus-ui.git'

New-Item -ItemType Directory -Force -Path $Target | Out-Null
Set-Location $Target

# ---------- 1. clone 若依基座 ----------
if (-not (Test-Path 'RuoYi-Vue-Plus')) {
    Write-Host "[1/4] clone RuoYi-Vue-Plus ($RuoyiBranch)"
    git clone --depth 1 -b $RuoyiBranch $RuoyiRepoGitee RuoYi-Vue-Plus
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  gitee 失败，退回 github"
        git clone --depth 1 -b $RuoyiBranch $RuoyiRepoGh RuoYi-Vue-Plus
    }
} else {
    Write-Host "[1/4] RuoYi-Vue-Plus 已存在，跳过 clone"
}

# ---------- 2. clone plus-ui 前端 ----------
if (-not (Test-Path 'plus-ui')) {
    Write-Host "[2/4] clone plus-ui"
    try { git clone --depth 1 $PlusUiRepo plus-ui }
    catch { Write-Warning "  plus-ui 拉取失败，可稍后手动 clone" }
} else {
    Write-Host "[2/4] plus-ui 已存在，跳过 clone"
}

# ---------- 3. 挂载业务模块（软链，需管理员或开发者模式）----------
$ModulesDir = 'RuoYi-Vue-Plus\ruoyi-modules'
Write-Host "[3/4] 挂载 business-modules -> $ModulesDir\"
foreach ($m in @('ruoyi-detect', 'ruoyi-inference')) {
    $src = Join-Path $Here "business-modules\$m"
    $dst = Join-Path $ModulesDir $m
    if (Test-Path $dst) { Write-Host "  $m 已挂载，跳过"; continue }
    if (-not (Test-Path $src)) { Write-Warning "  $src 不存在，跳过"; continue }
    try {
        New-Item -ItemType SymbolicLink -Path $dst -Target $src | Out-Null
        Write-Host "  ln $m"
    } catch {
        Write-Warning "  软链失败（需管理员 / 开发者模式）；退回复制"
        Copy-Item -Recurse -Force $src $dst
    }
}

# ---------- 4. 提示 ----------
@"

[4/4] 挂载完成。下一步：

  1) 在 $Target\RuoYi-Vue-Plus\ruoyi-modules\pom.xml 的 <modules> 里追加：
       <module>ruoyi-detect</module>
       <module>ruoyi-inference</module>

  2) 在 $Target\RuoYi-Vue-Plus\ruoyi-admin\pom.xml 追加依赖：
       <dependency>
         <groupId>org.dromara</groupId>
         <artifactId>ruoyi-detect</artifactId>
         <version>`${revision}</version>
       </dependency>

  3) 数据库初始化：
       mysql -uroot -p < $Target\RuoYi-Vue-Plus\script\sql\ry_vue_5.X.sql
       mysql -uroot -p ry-vue < $Here\scripts\patch-schema.sql

  4) 启动：cd $Target\RuoYi-Vue-Plus; mvn -pl ruoyi-admin -am spring-boot:run

  5) 前端：cd $Target\plus-ui; pnpm install; pnpm dev
"@ | Write-Host
