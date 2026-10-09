#!/usr/bin/env python3
"""安装脚本「目标目录解析」回归测试（不联网、不安装）。

锁定的真实故障（2026-10）：一位真实审计师的 Windows 机器上，
  - 他用的是「豆包工作」——目录是 DoubaoWork/…/.doubaowork/…，而 install.sh 只认「豆包」Doubao/…/.doubao/…，
    于是自动探测失败；
  - 他的机器上没有 bash（.sh 跑不了），宿主 Agent 只好「自己想办法」逐个文件去抓，版本与完整性都不受控。
本测试锁死修复后的行为：
  1. 「豆包工作」与「豆包」两套目录都能被探测到；
  2. 弱匹配（只有应用数据目录、workspace 尚未创建）也能选中豆包；
  3. 探测优先级不变（有 opencode 目录时仍选 opencode）；
  4. 显式指定 HOST=doubao / -Agent doubao 的行为稳定；
  5. install.ps1（Windows 原生）与 install.sh 结果一致（仅当本机有 pwsh 时执行）。

只调用 install.sh --detect-only / install.ps1 -DetectOnly：不联网、不下载、不写技能目录。
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALL_SH = ROOT / "install.sh"
INSTALL_PS1 = ROOT / "install.ps1"


def _pwsh():
    for c in (os.environ.get("PWSH"), shutil.which("pwsh")):
        if c and Path(c).exists():
            return c
    return None


def _make_doubao(local: Path, app: str, profile: str, *, workspace: bool) -> Path:
    """在 <local>/<app>/User Data/Default/<profile>/agent_mode/ 下建 workspace（或只建到 Default）。"""
    default = local / app / "User Data" / "Default"
    if workspace:
        ws = default / profile / "agent_mode" / "workspace"
        ws.mkdir(parents=True, exist_ok=True)
        return ws
    default.mkdir(parents=True, exist_ok=True)
    return default / profile / "agent_mode" / "workspace"


def _parse(out: str) -> dict:
    d = {}
    for line in out.splitlines():
        m = re.match(r"^(HOST|PREFIX|DOUBAO_FLAVOR)=(.*)$", line)
        if m:
            d[m.group(1)] = m.group(2)
    return d


def run_sh(local: Path, home: Path, host=None):
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(home),
        "LOCALAPPDATA": str(local),
    }
    if host:
        env["HOST"] = host
    p = subprocess.run(
        ["bash", str(INSTALL_SH), "--detect-only"],
        capture_output=True, text=True, env=env, timeout=60,
    )
    return p.returncode, _parse(p.stdout), p.stdout + p.stderr


def run_ps1(pwsh: str, local: Path, userprofile: Path, agent=None):
    env = {k: v for k, v in os.environ.items() if k != "HOST"}
    env["LOCALAPPDATA"] = str(local)
    env["USERPROFILE"] = str(userprofile)
    args = [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(INSTALL_PS1), "-DetectOnly"]
    if agent:
        args += ["-Agent", agent]
    p = subprocess.run(args, capture_output=True, text=True, env=env, timeout=120)
    return p.returncode, _parse(p.stdout), p.stdout + p.stderr


class TestDetectCases(unittest.TestCase):
    """install.sh 与 install.ps1 共用同一组场景。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="install-detect-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _case(self, name):
        local = self.tmp / name / "local"
        home = self.tmp / name / "home"
        local.mkdir(parents=True, exist_ok=True)
        home.mkdir(parents=True, exist_ok=True)
        return local, home

    def _assert_both(self, local, home, expected_host, prefix_contains=None, prefix_endswith=None, host=None):
        # install.sh
        rc, got, raw = run_sh(local, home, host=host)
        self.assertEqual(rc, 0, "install.sh 退出码非 0：%s" % raw)
        self.assertEqual(got.get("HOST"), expected_host, "install.sh HOST 解析错误：%s\n%s" % (got, raw))
        self._check_prefix(got.get("PREFIX", ""), prefix_contains, prefix_endswith, "install.sh")
        # install.ps1（有 pwsh 才跑）
        pwsh = _pwsh()
        if not pwsh:
            return
        rc, got, raw = run_ps1(pwsh, local, home, agent=host)
        self.assertEqual(rc, 0, "install.ps1 退出码非 0：%s" % raw)
        self.assertEqual(got.get("HOST"), expected_host, "install.ps1 HOST 解析错误：%s\n%s" % (got, raw))
        self._check_prefix(got.get("PREFIX", ""), prefix_contains, prefix_endswith, "install.ps1")

    def _check_prefix(self, prefix, contains, endswith, who):
        if contains:
            self.assertIn(contains, prefix, "%s PREFIX 应包含 %r：%r" % (who, contains, prefix))
        if endswith:
            self.assertTrue(prefix.replace("\\", "/").endswith(endswith),
                            "%s PREFIX 应以 %r 结尾：%r" % (who, endswith, prefix))

    # ── 核心回归：豆包工作 vs 豆包 ────────────────────────────────────────────
    def test_doubaowork_workspace(self):
        """「豆包工作」应有自己的路径（这是 2026-10 故障的根因）。"""
        local, home = self._case("doubaowork")
        _make_doubao(local, "DoubaoWork", ".doubaowork", workspace=True)
        self._assert_both(local, home, "doubao",
                          prefix_contains="DoubaoWork", prefix_endswith=".doubaowork/agent_mode/workspace/.user_skills")

    def test_doubao_personal_workspace(self):
        """「豆包」个人版路径仍要能用。"""
        local, home = self._case("doubao")
        _make_doubao(local, "Doubao", ".doubao", workspace=True)
        self._assert_both(local, home, "doubao",
                          prefix_contains="Doubao", prefix_endswith=".doubao/agent_mode/workspace/.user_skills")

    def test_doubao_work_preferred_over_personal(self):
        """两套都在时，优先「豆包工作」。"""
        local, home = self._case("both")
        _make_doubao(local, "DoubaoWork", ".doubaowork", workspace=True)
        _make_doubao(local, "Doubao", ".doubao", workspace=True)
        self._assert_both(local, home, "doubao", prefix_contains="DoubaoWork")

    def test_doubao_weak_match_no_workspace(self):
        """只装了豆包、还没进过「工作任务」模式（workspace 未创建）也能选中。"""
        local, home = self._case("weak")
        _make_doubao(local, "DoubaoWork", ".doubaowork", workspace=False)
        self._assert_both(local, home, "doubao",
                          prefix_contains="DoubaoWork", prefix_endswith=".doubaowork/agent_mode/workspace/.user_skills")

    # ── 不能破坏既有优先级 ──────────────────────────────────────────────────
    def test_opencode_priority_unchanged(self):
        """机器上同时有 opencode 目录时，仍按原优先级选 opencode。"""
        local, home = self._case("prio")
        _make_doubao(local, "DoubaoWork", ".doubaowork", workspace=True)
        (home / ".config" / "opencode" / "skills").mkdir(parents=True, exist_ok=True)
        self._assert_both(local, home, "opencode")

    def test_empty_defaults_to_opencode(self):
        """什么都没有时，默认仍是 opencode（不改变旧行为）。"""
        local, home = self._case("empty")
        self._assert_both(local, home, "opencode")

    # ── 显式指定 ────────────────────────────────────────────────────────────
    def test_explicit_doubao_without_app(self):
        """显式指定豆包、但机器上没装：仍解析出落点，并给出提示。"""
        local, home = self._case("explicit")
        self._assert_both(local, home, "doubao", prefix_endswith=".doubao/skills", host="doubao")

    def test_explicit_opencode(self):
        local, home = self._case("explicit-oc")
        self._assert_both(local, home, "opencode", prefix_endswith=".config/opencode/skills", host="opencode")


class TestScriptsExist(unittest.TestCase):
    def test_install_ps1_present(self):
        self.assertTrue(INSTALL_PS1.exists(), "install.ps1（Windows 原生安装脚本）缺失")


if __name__ == "__main__":
    unittest.main(verbosity=2)
