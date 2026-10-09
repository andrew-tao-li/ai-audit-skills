#Requires -Version 5.1
<#
install.ps1 — Windows 版安装脚本（PowerShell 5.1+ / PowerShell 7+）

为什么有它：install.sh 是 bash 脚本，Windows 上需要 Git Bash / WSL。很多审计师的机器上
并没有 bash，于是只能让宿主 Agent「临场发挥」去下载安装 —— 不可控、无校验。本脚本让
Windows 用户有一条**官方、可控**的路。

────────────────────────────────────────────────────────────────────────────
用法 A（推荐，最省事 —— 让本机自己跑，看得见每一步）：

    powershell -ExecutionPolicy Bypass -File .\install.ps1

用法 B（一行，从 GitHub 拉脚本再跑）：

    $f="$env:TEMP\ai-audit-install.ps1"; iwr -UseBasicParsing https://raw.githubusercontent.com/andrew-tao-li/ai-audit-skills/main/install.ps1 -OutFile $f; powershell -ExecutionPolicy Bypass -File $f

用法 C（零命令行，最不吓人 —— 适合不放心「远程脚本」的人）：

    浏览器打开 https://github.com/andrew-tao-li/ai-audit-skills/releases/latest
    下载需要的 <skill>.zip → 右键「全部解压缩」→ 把解出来的整个文件夹放进你的技能目录
    （目录见下方 -DetectOnly 的输出，或 adapters/doubao.md）

参数 / 环境变量：
    -Agent    auto|opencode|workbuddy|lobsterai|doubao|claude|cursor|codex|gemini   （等价 HOST=）
    -Prefix   覆盖默认安装目录（等价 PREFIX=）
    -Version  锁定版本，如 v0.3.10（等价 VERSION=）
    -Mirror   下载源前缀，github.com 被墙/超时时用（等价 MIRROR=）
    -Skills   只装指定 skill，如 -Skills expense-audit-v2
    -DetectOnly  只打印解析出的目标目录，不联网、不安装

卸载：Remove-Item -Recurse -Force "$Prefix\<skill-name>"
#>
[CmdletBinding()]
param(
    [string]   $Agent  = $env:HOST,
    [string]   $Prefix = $env:PREFIX,
    [string]   $Version = $env:VERSION,
    [string]   $Mirror  = $env:MIRROR,
    [string[]] $Skills,
    [switch]   $DetectOnly
)

$ErrorActionPreference = 'Stop'
# PS 5.1 默认可能不启 TLS1.2，GitHub 会握手失败
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch {}

# Windows 上 USERPROFILE / LOCALAPPDATA 一定有；其他平台（偶尔有人用 pwsh 跑）兜底到 HOME，避免空路径报错
if (-not $env:USERPROFILE)  { $env:USERPROFILE  = if ($HOME) { $HOME } else { '.' } }
if (-not $env:LOCALAPPDATA) { $env:LOCALAPPDATA = Join-Path $env:USERPROFILE 'AppData' }

$Repo      = 'andrew-tao-li/ai-audit-skills'
$UA        = 'ai-audit-installer'
$AllSkills = @('expense-audit-v2', 'procurement-fraud-v2', 'investigation-assistant-v2', 'cn-entity-relation-check')

# 用平台自己的分隔符拼路径（Windows 上是 \，其他地方是 /）——避免把 \ 写死进路径
function Join-All([string]$Base, [string[]]$Parts) {
    $p = $Base
    foreach ($x in $Parts) { $p = Join-Path $p $x }
    return $p
}

# ── 豆包：两个不同产品，两套目录（2026-10 由真实审计师实机纠正）─────────────────
#   ① 豆包（个人版）     应用目录 Doubao      → profile 目录 .doubao
#   ② 豆包工作（办公版） 应用目录 DoubaoWork  → profile 目录 .doubaowork
function Find-DoubaoWorkspace {
    $apps = @(
        @{ App = 'DoubaoWork'; Profile = '.doubaowork' },
        @{ App = 'Doubao';     Profile = '.doubao' }
    )
    foreach ($a in $apps) {
        $cand = Join-All $env:LOCALAPPDATA @($a.App, 'User Data', 'Default', $a.Profile, 'agent_mode', 'workspace')
        if (Test-Path -LiteralPath $cand) { return @{ Path = $cand; Flavor = $a.App } }
    }
    # 兜底：workspace 尚未创建（没进过「工作任务」模式），只要应用数据目录在就认它
    foreach ($a in $apps) {
        $root = Join-All $env:LOCALAPPDATA @($a.App, 'User Data', 'Default')
        if (Test-Path -LiteralPath $root) {
            return @{ Path = (Join-All $root @($a.Profile, 'agent_mode', 'workspace')); Flavor = $a.App }
        }
    }
    return $null
}

$DoubaoInfo      = Find-DoubaoWorkspace
$DoubaoWorkspace = if ($DoubaoInfo) { $DoubaoInfo.Path }   else { '' }
$DoubaoFlavor    = if ($DoubaoInfo) { $DoubaoInfo.Flavor } else { '' }

function Get-HostDirs([string]$h) {
    switch ($h) {
        'opencode'  { @((Join-All $env:USERPROFILE @('.config', 'opencode', 'skills'))) }
        'workbuddy' { @((Join-All $env:USERPROFILE @('.workbuddy', 'skills'))) }
        'lobsterai' { @((Join-All $env:USERPROFILE @('.lobsterai', 'skills')), (Join-All $env:LOCALAPPDATA @('LobsterAI', 'SKILLs'))) }
        'claude'    { @((Join-All $env:USERPROFILE @('.claude', 'skills'))) }
        'cursor'    { @((Join-All $env:USERPROFILE @('.cursor', 'skills'))) }
        'codex'     { @((Join-All $env:USERPROFILE @('.codex', 'skills')), (Join-All $env:USERPROFILE @('.agents', 'skills'))) }
        'gemini'    { @((Join-All $env:USERPROFILE @('.gemini', 'skills'))) }
        'doubao'    { if ($DoubaoWorkspace) { @($DoubaoWorkspace) } else { @() } }
        default     { @() }
    }
}

# ── 探测 Agent（优先级与 install.sh 一致；豆包等追加在后，不影响既有结果）────────
$HostOrder = @('opencode', 'workbuddy', 'lobsterai', 'doubao', 'claude', 'cursor', 'codex', 'gemini')
if (-not $Agent -or $Agent -eq 'auto') {
    $detected = ''
    $found    = @()
    foreach ($h in $HostOrder) {
        foreach ($d in (Get-HostDirs $h)) {
            if ($d -and (Test-Path -LiteralPath $d)) {
                $found += $h
                if (-not $detected) { $detected = $h }
            }
        }
    }
    $Agent = if ($detected) { $detected } else { 'opencode' }
    if (-not $detected -and $DoubaoWorkspace) {
        $Agent = 'doubao'
        Write-Host "ℹ 未发现其他 Agent；检测到豆包（$DoubaoFlavor，workspace 尚未创建，将自动创建）。" -ForegroundColor Cyan
    }
    $uniq = @($found | Select-Object -Unique)
    if ($uniq.Count -gt 1) {
        Write-Host "ℹ 检测到多个 Agent 目录：$($uniq -join ' ')。已按优先级装到 $Agent；如需装到别的，加 -Agent <名称> 或 -Prefix <路径>。" -ForegroundColor Cyan
    }
}

# ── 解析安装目录 ───────────────────────────────────────────────────────────────
$PrefixExplicit = [bool]$Prefix
if (-not $Prefix) {
    switch ($Agent) {
        'opencode'  { $Prefix = Join-All $env:USERPROFILE @('.config', 'opencode', 'skills') }
        'workbuddy' { $Prefix = Join-All $env:USERPROFILE @('.workbuddy', 'skills') }
        'lobsterai' { $Prefix = Join-All $env:USERPROFILE @('.lobsterai', 'skills') }
        'claude'    { $Prefix = Join-All $env:USERPROFILE @('.claude', 'skills') }
        'cursor'    { $Prefix = Join-All $env:USERPROFILE @('.cursor', 'skills') }
        'codex'     { $Prefix = Join-All $env:USERPROFILE @('.codex', 'skills') }
        'gemini'    { $Prefix = Join-All $env:USERPROFILE @('.gemini', 'skills') }
        'doubao'    {
            if ($DoubaoWorkspace) {
                $Prefix = Join-Path $DoubaoWorkspace '.user_skills'
                Write-Host "ℹ 检测到豆包（$DoubaoFlavor）：$DoubaoWorkspace" -ForegroundColor Cyan
            } else {
                Write-Host "⚠ 未找到豆包数据目录（已探测两套：DoubaoWork\.doubaowork 与 Doubao\.doubao）。" -ForegroundColor Yellow
                Write-Host "  请确认已安装「豆包」或「豆包工作」桌面客户端，并进入过「工作任务」模式；或用 -Prefix <目录> 指定。" -ForegroundColor Yellow
                $Prefix = Join-All $env:USERPROFILE @('.doubao', 'skills')
            }
        }
        default     { $Prefix = $Agent }   # 当作字面路径
    }
}
$HostLabel = if ($PrefixExplicit) { 'custom' } else { $Agent }

if ($DetectOnly) {
    Write-Host "HOST=$HostLabel"
    Write-Host "PREFIX=$Prefix"
    if ($DoubaoFlavor) { Write-Host "DOUBAO_FLAVOR=$DoubaoFlavor" }
    exit 0
}

# ── 解析版本（API → raw 上的 VERSION 文件；不依赖 git）────────────────────────
function Get-LatestVersion {
    try {
        $r = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" `
            -Headers @{ Accept = 'application/vnd.github+json' } -UserAgent $UA -TimeoutSec 30
        if ($r.tag_name) { return $r.tag_name }
    } catch {}
    try {
        $v = (Invoke-WebRequest -Uri "https://raw.githubusercontent.com/$Repo/main/VERSION" `
            -UseBasicParsing -UserAgent $UA -TimeoutSec 30).Content.Trim()
        if ($v -match '^v[0-9]') { return $v }
    } catch {}
    return ''
}
if (-not $Version) { $Version = Get-LatestVersion }
if (-not $Version) {
    Write-Host "⚠ 无法获取最新版本（GitHub API 与 raw 都失败）。请用 -Version v0.X.Y 重试。" -ForegroundColor Red
    exit 1
}

# ── 选择要装的 skill ──────────────────────────────────────────────────────────
if (-not $Skills -or $Skills.Count -eq 0) {
    $Skills = $AllSkills
    $Mode   = 'all'
} else {
    foreach ($s in $Skills) {
        if ($AllSkills -notcontains $s) {
            Write-Host "✗ 未知的 skill 名：`"$s`"" -ForegroundColor Red
            Write-Host "  可选：$($AllSkills -join ', ')"
            exit 2
        }
    }
    $Mode = 'subset'
}

Write-Host "▶ 安装 AI Audit Skills $Version → $Prefix  (host=$HostLabel)"
Write-Host "  范围：$(if ($Mode -eq 'all') { "全部 $($Skills.Count) 个 skill" } else { "选中 $($Skills.Count)/$($AllSkills.Count) 个 skill（$($Skills -join ' ')）" })"
foreach ($s in $Skills) { Write-Host "  · $s" }

New-Item -ItemType Directory -Force -Path $Prefix | Out-Null

# ── 下载（带降级）→ 解压 ─────────────────────────────────────────────────────
#   ① MIRROR=<前缀>（若设）→ ② github.com 直连 → ③ GitHub API 资产接口（跟随 302 到 CDN）
function Save-SkillZip([string]$s, [string]$out) {
    $urls = @()
    if ($Mirror) { $urls += ("{0}/{1}/{2}.zip" -f $Mirror.TrimEnd('/'), $Version, $s) }
    $urls += "https://github.com/$Repo/releases/download/$Version/$s.zip"
    foreach ($u in $urls) {
        try {
            Invoke-WebRequest -Uri $u -OutFile $out -UseBasicParsing -UserAgent $UA -TimeoutSec 90
            return $true
        } catch {
            if (Test-Path -LiteralPath $out) { Remove-Item -LiteralPath $out -Force }
        }
    }
    try {
        $rel = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/tags/$Version" `
            -Headers @{ Accept = 'application/vnd.github+json' } -UserAgent $UA -TimeoutSec 30
        $asset = $rel.assets | Where-Object { $_.name -eq "$s.zip" } | Select-Object -First 1
        if ($asset) {
            Write-Host "  ℹ github.com 直连失败，改用 GitHub API 资产接口…" -ForegroundColor Yellow
            Invoke-WebRequest -Uri $asset.url -Headers @{ Accept = 'application/octet-stream' } `
                -OutFile $out -UseBasicParsing -UserAgent $UA -TimeoutSec 180
            return $true
        }
    } catch {}
    return $false
}

foreach ($s in $Skills) {
    $dest = Join-Path $Prefix $s
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    $tmp = Join-Path $Prefix "$s.zip.downloading"
    if (-not (Save-SkillZip $s $tmp)) {
        Write-Host "✗ 下载失败：$s（版本 $Version）" -ForegroundColor Red
        Write-Host "  可照做的替代方案（任选其一）："
        Write-Host "    1) 设置镜像后重试：-Mirror <镜像前缀>"
        Write-Host "    2) 手动下载：https://github.com/$Repo/releases/tag/$Version"
        Write-Host "       下载 $s.zip，解压到 $dest"
        Write-Host "    3) 换网络/开代理后重试；或用 -Version 指定版本以排除版本解析问题"
        exit 1
    }
    try {
        Expand-Archive -LiteralPath $tmp -DestinationPath $dest -Force
    } finally {
        if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force }
    }
}

Write-Host ""
if ($Mode -eq 'all') {
    Write-Host "✓ 完成（$Version）。已装全部 $($Skills.Count) 个 skill 到：$Prefix" -ForegroundColor Green
} else {
    $notInstalled = @($AllSkills | Where-Object { $Skills -notcontains $_ })
    Write-Host "✓ 完成（$Version）。本次装到 $($Skills.Count) 个 skill 到：$Prefix" -ForegroundColor Green
    Write-Host "  装的：$($Skills -join ' ')"
    if ($notInstalled.Count -gt 0) {
        Write-Host "  未装的（$($notInstalled.Count) 个）：$($notInstalled -join ' ')"
        Write-Host "  想全装请不带 -Skills 再跑一次"
    }
}
Write-Host "  当前内容："
Get-ChildItem -Path $Prefix -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "    $($_.Name)" }
