#!/usr/bin/env python3
"""Validate the AI Audit Skill Pack without network access or third-party SDKs."""

import argparse
import ast
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = PACK_ROOT / "skills-v2"
EXPECTED_SKILLS = {"expense-audit-v2", "procurement-fraud-v2", "investigation-assistant-v2"}
NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FORBIDDEN_IMPORTS = {
    "openai",
    "anthropic",
    "google.generativeai",
    "requests",
    "httpx",
    "urllib",
    "socket",
    "aiohttp",
}
REQUIRED_ROOT_FILES = {
    "README.md",
    "AGENTS.md",
    "SECURITY.md",
    "LICENSE",
    "CHANGELOG.md",
    "docs/architecture.md",
    "docs/data-contracts.md",
    "docs/security-model.md",
    "docs/audit-methodology.md",
    "docs/development-guide.md",
    "adapters/codex.md",
    "adapters/pi.md",
    "adapters/openclaw.md",
    "adapters/workbuddy.md",
    "adapters/lobsterai.md",
    "evals/eval-design.md",
    "evals/cross-agent-matrix.md",
    "evals/fixtures/README.md",
    "evals/tests/test_file_scenarios.py",
    "evals/trigger-prompts.jsonl",
    "evals/run_trigger_eval.py",
    "evals/verify_file_regression.py",
}


def parse_frontmatter(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing opening frontmatter delimiter")
    try:
        block, _ = text[4:].split("\n---\n", 1)
    except ValueError as exc:
        raise ValueError("missing closing frontmatter delimiter") from exc
    values = {}
    for line in block.splitlines():
        if not line or line.startswith(" ") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values, text


def imported_roots(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def import_is_forbidden(module):
    return any(module == blocked or module.startswith(blocked + ".") for blocked in FORBIDDEN_IMPORTS)


def validate_trigger_prompts(errors, checks):
    path = PACK_ROOT / "evals" / "trigger-prompts.jsonl"
    if not path.exists():
        return
    counts = Counter()
    seen_prompts = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append("trigger-prompts.jsonl 第 {} 行不是合法 JSON：{}".format(line_number, exc))
            continue
        if set(item) != {"skill", "expected_trigger", "prompt"}:
            errors.append("trigger-prompts.jsonl 第 {} 行字段不符合契约".format(line_number))
            continue
        if item["skill"] not in EXPECTED_SKILLS:
            errors.append("trigger-prompts.jsonl 第 {} 行 skill 未知".format(line_number))
        if not isinstance(item["expected_trigger"], bool):
            errors.append("trigger-prompts.jsonl 第 {} 行 expected_trigger 必须是布尔值".format(line_number))
        if not isinstance(item["prompt"], str) or not item["prompt"].strip():
            errors.append("trigger-prompts.jsonl 第 {} 行 prompt 为空".format(line_number))
        if item["prompt"] in seen_prompts:
            errors.append("trigger-prompts.jsonl 第 {} 行 prompt 重复".format(line_number))
        seen_prompts.add(item["prompt"])
        counts[(item["skill"], item["expected_trigger"])] += 1
    for skill in sorted(EXPECTED_SKILLS):
        for expected in (True, False):
            count = counts[(skill, expected)]
            checks.append({"check": "trigger-prompts", "skill": skill, "expected": expected, "count": count})
            if count != 20:
                errors.append("{} 的 expected_trigger={} 应有 20 条，实际 {} 条".format(skill, expected, count))


def validate_skill(skill_dir, errors, checks):
    skill = skill_dir.name
    required = [
        "SKILL.md",
        "README.md",
        "requirements.txt",
        "agents/openai.yaml",
        "examples/input",
        "examples/expected/expectations.json",
        "references",
        "scripts",
        "tests",
    ]
    for relative in required:
        if not (skill_dir / relative).exists():
            errors.append("{} 缺少 {}".format(skill, relative))

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return
    try:
        frontmatter, text = parse_frontmatter(skill_md)
    except ValueError as exc:
        errors.append("{} 的 SKILL.md：{}".format(skill, exc))
        return

    declared_name = frontmatter.get("name", "")
    description = frontmatter.get("description", "")
    if declared_name != skill:
        errors.append("{} 的 frontmatter name 必须与目录名一致".format(skill))
    if len(declared_name) > 64 or not NAME_PATTERN.fullmatch(declared_name):
        errors.append("{} 的 name 不符合 Agent Skills 命名规则".format(skill))
    if not 1 <= len(description) <= 1024:
        errors.append("{} 的 description 长度必须为 1–1024 字符".format(skill))
    if "Use when" not in description:
        errors.append("{} 的 description 未说明触发场景".format(skill))
    line_count = len(text.splitlines())
    checks.append({"check": "skill-lines", "skill": skill, "count": line_count})
    if line_count >= 500:
        errors.append("{} 的 SKILL.md 应少于 500 行，实际 {} 行".format(skill, line_count))

    yaml_path = skill_dir / "agents" / "openai.yaml"
    if yaml_path.exists():
        yaml_text = yaml_path.read_text(encoding="utf-8")
        default_match = re.search(r'^\s*default_prompt:\s*["\']?(.*?)["\']?\s*$', yaml_text, re.MULTILINE)
        short_match = re.search(r'^\s*short_description:\s*["\'](.*)["\']\s*$', yaml_text, re.MULTILINE)
        if not default_match or "$" + skill not in default_match.group(1):
            errors.append("{} 的 default_prompt 必须显式包含 ${}".format(skill, skill))
        if not short_match or not 25 <= len(short_match.group(1)) <= 64:
            errors.append("{} 的 short_description 应为 25–64 个字符".format(skill))

    scripts = sorted((skill_dir / "scripts").glob("*.py"))
    tests = sorted((skill_dir / "tests").glob("test_*.py"))
    samples = sorted(path for path in (skill_dir / "examples" / "input").rglob("*") if path.is_file())
    if not scripts:
        errors.append("{} 没有 Python 运行脚本".format(skill))
    if not tests:
        errors.append("{} 没有 test_*.py 测试类文件".format(skill))
    if not samples:
        errors.append("{} 没有输入样例".format(skill))
    checks.append({"check": "artifacts", "skill": skill, "scripts": len(scripts), "tests": len(tests), "samples": len(samples)})

    for script in scripts:
        try:
            modules = imported_roots(script)
        except SyntaxError as exc:
            errors.append("{} 存在语法错误：{}".format(script.relative_to(PACK_ROOT), exc))
            continue
        blocked = sorted(module for module in modules if import_is_forbidden(module))
        if blocked:
            errors.append("{} 引入了禁止的模型或网络模块：{}".format(script.relative_to(PACK_ROOT), ", ".join(blocked)))
        script_text = script.read_text(encoding="utf-8")
        if "/home/" in script_text or re.search(r"[A-Za-z]:\\\\Users\\\\", script_text):
            errors.append("{} 含硬编码用户绝对路径".format(script.relative_to(PACK_ROOT)))
        if re.search(r"sk-[A-Za-z0-9_-]{12,}", script_text):
            errors.append("{} 疑似包含 API 密钥".format(script.relative_to(PACK_ROOT)))


def run_tests(errors, checks):
    for skill in sorted(EXPECTED_SKILLS):
        test_dir = SKILLS_ROOT / skill / "tests"
        completed = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", str(test_dir), "-v"],
            cwd=str(PACK_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        checks.append({"check": "unittest", "skill": skill, "passed": completed.returncode == 0})
        if completed.returncode != 0:
            errors.append("{} 测试失败：\n{}".format(skill, completed.stdout + completed.stderr))
    pack_tests = PACK_ROOT / "evals" / "tests"
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", str(pack_tests), "-v"],
        cwd=str(PACK_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    checks.append({"check": "unittest", "skill": "pack-evals", "passed": completed.returncode == 0})
    if completed.returncode != 0:
        errors.append("pack eval 测试失败：\n{}".format(completed.stdout + completed.stderr))


def main():
    parser = argparse.ArgumentParser(description="Validate AI Audit Skill Pack")
    parser.add_argument("--run-tests", action="store_true", help="also run every skill's unittest suite")
    args = parser.parse_args()
    errors = []
    checks = []

    for relative in sorted(REQUIRED_ROOT_FILES):
        if not (PACK_ROOT / relative).exists():
            errors.append("整包缺少 {}".format(relative))

    actual_skills = {path.name for path in SKILLS_ROOT.iterdir() if path.is_dir()} if SKILLS_ROOT.exists() else set()
    if actual_skills != EXPECTED_SKILLS:
        errors.append("skill 集合不符：期望 {}，实际 {}".format(sorted(EXPECTED_SKILLS), sorted(actual_skills)))
    for skill in sorted(EXPECTED_SKILLS & actual_skills):
        validate_skill(SKILLS_ROOT / skill, errors, checks)
    validate_trigger_prompts(errors, checks)
    if args.run_tests:
        run_tests(errors, checks)

    result = {
        "pack": "ai-audit-skills",
        "skills": sorted(actual_skills),
        "status": "pass" if not errors else "fail",
        "checks": checks,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
