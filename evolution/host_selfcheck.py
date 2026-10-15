#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""host_selfcheck.py — 例行日报的「主机 + 网络」自检

用途：这台机器（Mac mini）是**无头远端**运行、通过 Tailscale 连接。
本脚本把「机器本身稳不稳」「Tailscale 通不通」变成日报里的一段，避免
"日报没来 / 来晚了" 时只能靠猜。

设计铁律（与 evolve.sh 一致）：
  * **永不失败**：任何一项取不到都不抛异常、不退出非 0，只少写一行。
  * **只用本地命令**：不访问任何第三方网络；全部调用 native macOS 工具。
  * **绝对路径**：launchd 的 PATH 不含 /usr/sbin，必须写绝对路径。
  * **硬超时**：每个子进程都有 timeout，绝不拖住每日例行。

输出：若干行 Markdown（notify.sh 会转成纯文本发到企业微信）。
"""

import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "evolution" / "log"
STATE_PATH = ROOT / "evolution" / "host_state.json"

PY = {
    "sysctl": "/usr/sbin/sysctl",
    "launchctl": "/bin/launchctl",
    "pmset": "/usr/bin/pmset",
    "df": "/bin/df",
    "vm_stat": "/usr/bin/vm_stat",
    "ipconfig": "/usr/sbin/ipconfig",
}
TAILSCALE_CANDIDATES = (
    "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
    "/usr/local/bin/tailscale",
    "/opt/homebrew/bin/tailscale",
    "/usr/bin/tailscale",
)

WARNINGS = []      # 需要在日报里显眼提示的项
INFO = {}          # 存档到 host_state.json 的原始值


# ── 基础工具 ────────────────────────────────────────────────────────────────
def run(cmd, timeout=8):
    """跑一个命令，任何异常/超时都返回 ""（永不抛出）。"""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (p.stdout or "").strip()
    except Exception:
        return ""


def find_tailscale():
    for c in TAILSCALE_CANDIDATES:
        if Path(c).is_file():
            return c
    return ""


def human_duration(seconds):
    try:
        seconds = int(seconds)
    except Exception:
        return "?"
    days, rem = divmod(max(seconds, 0), 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return "%d天%d小时" % (days, hours)
    if hours:
        return "%d小时%d分" % (hours, minutes)
    return "%d分钟" % minutes


def human_ago(ts):
    """把 unix 时间戳说成「X 分钟前」；取不到就返回 None。"""
    if not ts:
        return None
    try:
        delta = time_now() - float(ts)
    except Exception:
        return None
    if delta < 120:
        return "刚刚"
    if delta < 3600:
        return "%d 分钟前" % (delta // 60)
    if delta < 86400:
        return "%d 小时前" % (delta // 3600)
    return "%d 天前" % (delta // 86400)


def time_now():
    return datetime.now(timezone.utc).timestamp()


# ── ① 主机（macOS）──────────────────────────────────────────────────────────
def check_system():
    lines = []

    model = run([PY["sysctl"], "-n", "hw.model"]) or platform.machine()
    mem_total = 0
    try:
        mem_total = int(run([PY["sysctl"], "-n", "hw.memsize"]) or 0)
    except Exception:
        mem_total = 0

    # 启动时间 / 运行时长
    boot_raw = run([PY["sysctl"], "-n", "kern.boottime"])
    m = re.search(r"sec\s*=\s*(\d+)", boot_raw)
    boot_ts = int(m.group(1)) if m else 0
    boot_str, up_str = "?", "?"
    if boot_ts:
        INFO["boot_time"] = boot_ts
        boot_str = datetime.fromtimestamp(boot_ts).strftime("%Y-%m-%d %H:%M")
        up_str = human_duration(time_now() - boot_ts)

    # 负载
    load = "?"
    lm = re.search(r"\{([^}]*)\}", run([PY["sysctl"], "-n", "vm.loadavg"]))
    if lm:
        load = " / ".join(x.strip() for x in lm.group(1).split())

    # 内存：free + inactive（近似"可用"）；swap 使用量反映内存压力
    free_gb = None
    vm = run([PY["vm_stat"]], timeout=6)
    if vm:
        page = 4096
        pm = re.search(r"page size of (\d+) bytes", vm)
        if pm:
            page = int(pm.group(1))
        pages = 0
        for key in ("Pages free", "Pages inactive"):
            km = re.search(re.escape(key) + r":\s+(\d+)", vm)
            if km:
                pages += int(km.group(1))
        if pages:
            free_gb = pages * page / 1073741824.0
    swap = run([PY["sysctl"], "-n", "vm.swapusage"])
    swap_used = "?"
    sm = re.search(r"used\s*=\s*([\d.]+)([MG])", swap or "")
    if sm:
        val, unit = float(sm.group(1)), sm.group(2)
        swap_gb = val / 1024.0 if unit == "M" else val
        swap_used = "%.1f GB" % swap_gb
        INFO["swap_used_gb"] = round(swap_gb, 2)
        # macOS 日常就有少量 swap，属正常；只有明显偏高才提示，
        # 否则会变成"每天都报同一句"，把真正的异常淹没。
        mem_gb = mem_total / 1073741824.0 if mem_total else 0
        if swap_gb > max(4.0, 0.25 * mem_gb):
            WARNINGS.append("swap 已用 %s（内存偏紧）" % swap_used)

    # 磁盘（根卷）
    disk = "?"
    dm = run([PY["df"], "-k", "/"])
    if dm:
        parts = [l.split() for l in dm.strip().splitlines() if l.strip()]
        if len(parts) >= 2:
            f = parts[-1]
            try:
                total = int(f[1]) / 1048576.0
                avail = int(f[3]) / 1048576.0
                pct = avail / total * 100 if total else 0
                disk = "可用 %.0f/%.0f GB (%.0f%%)" % (avail, total, pct)
                if avail < 10 or pct < 10:
                    WARNINGS.append("磁盘可用仅 %.0f GB（%.0f%%）" % (avail, pct))
            except Exception:
                pass

    INFO["disk_avail_gb"] = (int(f[3]) / 1048576.0) if dm and len(parts) >= 2 else None

    # 例行任务上次退出码
    lc = run([PY["launchctl"], "list", "com.audit.skill.box"])
    last_exit = None
    em = re.search(r'"LastExitStatus"\s*=\s*(-?\d+)', lc or "")
    if em:
        last_exit = int(em.group(1))
        INFO["last_exit_status"] = last_exit
        if last_exit != 0:
            WARNINGS.append("例行任务上次退出码 %d（非 0）" % last_exit)

    # 电源：会不会睡眠 / 断电后是否自动开机
    pm_out = run([PY["pmset"], "-g"], timeout=6)
    sleep_setting = None
    autorestart = None
    sm2 = re.search(r"^\s*sleep\s+(\d+)", pm_out or "", re.M)
    if sm2:
        sleep_setting = int(sm2.group(1))
    am = re.search(r"^\s*autorestart\s+(\d+)", pm_out or "", re.M)
    if am:
        autorestart = int(am.group(1))
    power_bits = []
    if sleep_setting is not None:
        # 同样只写正文：这是配置状态，不是每次的异常
        power_bits.append("不会睡眠 ✓" if sleep_setting == 0
                          else "空闲 %d 分钟后睡眠 ⚠️（可能推迟每日例行）" % sleep_setting)
    if autorestart is not None:
        # 持续性的"配置建议"只写在正文里（每天可见、可自行决定改不改），
        # **不**放进 ⚠️ 汇总——否则每天都报同一条，真正的异常就被淹没了。
        power_bits.append("断电自启 ✓" if autorestart == 1 else "断电自启 ✗（远程无头机建议开启）")
    INFO["sleep_setting"] = sleep_setting
    INFO["autorestart"] = autorestart

    # 重启检测：与上次记录对比
    reboot_note = ""
    prev = {}
    try:
        if STATE_PATH.is_file():
            prev = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        prev = {}
    prev_boot = prev.get("boot_time")
    if prev_boot and boot_ts and int(prev_boot) != int(boot_ts):
        reboot_note = " ⚠️ 期间重启过（上次启动 %s）" % datetime.fromtimestamp(
            int(prev_boot)).strftime("%Y-%m-%d %H:%M")
        WARNINGS.append("期间重启过（上次启动 %s）" % datetime.fromtimestamp(
            int(prev_boot)).strftime("%Y-%m-%d %H:%M"))

    mem_str = "内存可用 %.1f/%.0f GB" % (free_gb, mem_total / 1073741824.0) if free_gb and mem_total else "内存 ?"
    lines.append("**主机自检**（%s · %s）" % (platform.node() or "?", model))
    lines.append("- 运行: 已连续 %s（启动 %s）%s" % (up_str, boot_str, reboot_note))
    lines.append("- 负载: %s · %s · swap %s" % (load, mem_str, swap_used))
    lines.append("- 磁盘: %s" % disk)
    bits = []
    if last_exit is not None:
        bits.append("例会上次退出码 %d%s" % (last_exit, "" if last_exit == 0 else " ✗"))
    if power_bits:
        bits.append("电源 " + " · ".join(power_bits))
    if bits:
        lines.append("- " + " · ".join(bits))
    return lines


# ── ② Tailscale 连通性 ──────────────────────────────────────────────────────
def check_tailscale():
    lines = []
    ts = find_tailscale()
    if not ts:
        lines.append("**Tailscale**：未找到 CLI（跳过；不影响其余检查）")
        return lines

    raw = run([ts, "status", "--json"], timeout=15)
    if not raw:
        WARNINGS.append("Tailscale 状态读取失败")
        lines.append("**Tailscale**：⚠️ 无法读取状态（CLI 存在但调用失败）")
        return lines
    try:
        data = json.loads(raw)
    except Exception:
        lines.append("**Tailscale**：⚠️ 状态输出无法解析")
        return lines

    backend = data.get("BackendState") or "?"
    self_node = data.get("Self") or {}
    ips = self_node.get("TailscaleIPs") or []
    v4 = next((i for i in ips if "." in i), "")
    dns = (self_node.get("DNSName") or "").rstrip(".")
    online = self_node.get("Online")

    if backend != "Running":
        WARNINGS.append("Tailscale 非 Running（%s）" % backend)

    peers = data.get("Peer") or {}
    online_peers = [(k, v) for k, v in peers.items() if v.get("Online")]

    lines.append("**Tailscale 连通性**")
    state_str = "Running ✓" if backend == "Running" else "**%s ✗**" % backend
    lines.append("- 状态: %s · 本机 %s%s" % (
        state_str, v4 or "?", (" (%s)" % dns) if dns else ""))

    if peers:
        names = []
        newest = 0.0
        for _k, p in online_peers[:3]:
            hs = p.get("LastHandshake") or ""
            ts_epoch = 0.0
            if hs:
                try:
                    ts_epoch = datetime.strptime(
                        hs.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()
                except Exception:
                    try:
                        ts_epoch = datetime.strptime(
                            hs.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z").timestamp()
                    except Exception:
                        ts_epoch = 0.0
            newest = max(newest, ts_epoch)
            ago = human_ago(ts_epoch) if ts_epoch else None
            names.append("%s%s" % (p.get("HostName") or "?", ("（%s）" % ago) if ago else ""))
        lines.append("- 节点: 在线 %d/%d%s" % (
            len(online_peers), len(peers),
            ("，" + "、".join(names)) if names else ""))
        # 长时间无握手 → 主动探一次（证明端到端真的通）
        if newest and (time_now() - newest) > 3600:
            ping = run([ts, "ping", "--timeout=5s", "--c", "1",
                        (online_peers[0][1].get("TailscaleIPs") or [""])[0]], timeout=12)
            ok = "pong" in (ping or "").lower()
            lines.append("- 实测: %s" % ("✓ 可连通对端" if ok else "⚠️ ping 无响应（可能被 ACL 限制）"))
            if not ok:
                WARNINGS.append("Tailscale ping 无响应")
        # 「对端离线」只写正文、不报警：你自己笔记本合盖就属正常，
        # 报警会天天出现，反而盖住真问题。
        if not online_peers and peers:
            lines.append("- 提示: %d 个节点当前全部离线（对端未开机属正常）" % len(peers))
    else:
        lines.append("- 节点: 无（tailnet 里只有本机）")

    expiry = self_node.get("KeyExpiry")
    if expiry:
        try:
            e = datetime.strptime(expiry.replace("Z", "+0000"),
                                  "%Y-%m-%dT%H:%M:%S.%f%z") if "." in expiry else \
                datetime.strptime(expiry.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z")
            days = (e.timestamp() - time_now()) / 86400.0
            lines.append("- 密钥: %s 后过期（%s）" % ("%.1f 天" % days, e.strftime("%Y-%m-%d")))
            if days < 7:
                WARNINGS.append("Tailscale 节点密钥 %.1f 天后过期（到期会断连）" % days)
        except Exception:
            lines.append("- 密钥: 有到期时间（%s）" % expiry)
    else:
        lines.append("- 密钥: 不过期 ✓")

    INFO["tailscale"] = {
        "backend": backend, "ip": v4, "dns": dns,
        "peers_total": len(peers), "peers_online": len(online_peers),
    }
    return lines


def main():
    out = []
    for fn in (check_system, check_tailscale):
        try:
            out.extend(fn())
        except Exception as e:      # 绝不因自检本身中断例行
            out.append("（自检项 %s 异常：%s）" % (fn.__name__, e))
    if WARNINGS:
        out.append("- ⚠️ **需关注**: " + "；".join(WARNINGS))
    else:
        out.append("- ✅ 主机与网络未见异常")
    print("\n".join(out))

    # 存档（供下次对比"是否重启过"）；写失败也不影响任何事
    try:
        INFO["checked_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        prev = {}
        if STATE_PATH.is_file():
            try:
                prev = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            except Exception:
                prev = {}
        if not INFO.get("boot_time"):
            INFO["boot_time"] = prev.get("boot_time")
        INFO["previous_checked_at"] = prev.get("checked_at")
        STATE_PATH.write_text(json.dumps(INFO, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
