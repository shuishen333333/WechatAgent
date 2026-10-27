# 把本仓库里改过的文件覆盖到本机 WeChatAgent 的"安装模板"和"运行目录"。
# 用途：WeChatAgent 每次更新/修复安装都会整包替换 app\resources\project，
# 并覆盖 data\workspace，所以更新后跑一次这个脚本即可恢复本机补丁。
#
# 用法：pwsh -File scripts\apply-local-patches.ps1
#   可选参数：-InstallRoot "D:\zlh‘s program"

param(
  [string]$InstallRoot = "D:\zlh‘s program"
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot

# 本机打过的补丁（相对仓库根的路径）
$patched = @(
  'scripts\reader-api.py',
  'scripts\resolve-wechat-image.py',
  'scripts\wechat_files.py',
  'packages\dsh-social-bridge-plugin\image-input.mjs'
)

$targets = @(
  (Join-Path $InstallRoot 'app\resources\project'),
  (Join-Path $InstallRoot 'data\workspace')
)

foreach ($target in $targets) {
  if (-not (Test-Path $target)) {
    Write-Warning "跳过不存在的目录：$target"
    continue
  }
  foreach ($rel in $patched) {
    $src = Join-Path $repo $rel
    $dst = Join-Path $target $rel
    if (-not (Test-Path $src)) { Write-Warning "缺少补丁文件：$src"; continue }
    if (-not (Test-Path (Split-Path -Parent $dst))) { Write-Warning "跳过不存在的目标目录：$dst"; continue }
    Copy-Item $src $dst -Force
    $same = (Get-FileHash $src).Hash -eq (Get-FileHash $dst).Hash
    Write-Host ("{0,-8} {1} copy={2}" -f (Split-Path -Leaf $dst), $rel, $same)
  }
}

Write-Host ''
Write-Host '完成。请重启 WeChatAgent 服务，DSH 里改动过的插件需要重启 DSH 才生效。'
