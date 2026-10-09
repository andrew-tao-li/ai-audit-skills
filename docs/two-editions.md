# 两个版本：canonical 与 SkillHub 适配版

> **一句话**：`skills-v2/`（canonical）是**唯一真相源与唯一安装路径**，它**本身已合规**；
> `dist-v2/skillhub/` 只是给 SkillHub 的**平台适配派生品**（frontmatter 等），不再承担"安全净化"。

---

## 为什么有两个版本

| | canonical | SkillHub 适配版 |
|---|---|---|
| **面向谁** | GitHub 分发（GitHub release + `install.sh` / `install.ps1`） | **只**给 SkillHub.cn 上架 |
| **在哪** | `skills-v2/<skill>/` | `dist-v2/skillhub/<skill>/`（**生成物**） |
| **怎么到用户手里** | `install.sh` / `install.ps1` → GitHub release → 用户机器 | `skillhub publish dist-v2/skillhub/<skill>` |
| **谁是真相源** | ✅ 唯一真相源，手工维护 | ❌ 派生，由 `scripts/build-skillhub.py` 生成 |

---

## 合规基线（两版**都必须**满足）

2026-10 一次企业安全审查（审计师 B）驳回后，按用户决定，**canonical 本身**已满足下面的合规基线
（见 [`docs/reported-issues.md`](reported-issues.md) #2）。SkillHub 版因为是派生品，自然继承：

1. **不含任何外发通道**：代码与文档里**不含**服务器地址、webhook 或密钥。
2. **不含远程执行的写法**：不出现"下载后管道交给解释器"（`curl … | sh/bash`）；更不替用户执行。
3. **不含隐瞒措辞**：不出现"不要向用户/测试者复述""不必再问一遍"这类可被读作"隐瞒"的表述。
4. **前置主动披露**：`SKILL.md` 开头有「联网与风险（必读）」，把联网动作、数据边界、最大风险一次说清。
5. **反馈只能由用户自己发出**：脚本最多**生成一段非敏感统计文本**；发送者是用户本人。

> `scripts/build-skillhub.py` 的 `verify()` 会对 1–4 做**守卫检查**（命中即报错），防止将来回归。

---

## 铁律：需求不许倒灌（仍然有效）

> **平台的要求，只能改派生侧（`build-skillhub.py`）；canonical 的要求，只在 canonical 改。**
> **绝不因为"平台审核会挑刺"而去改 canonical 的内容**——但**合规基线**（上一节）不在此列：
> 那是对**所有版本的**要求，只要 canonical 与派生品都满足即可。

来历：2026-09-27 曾为"让扫描器不误报"把 canonical 的 `__import__("pathlib")` 改成常规 `import`——
那是一次**倒灌**，已回退。现在这类"扫描器偏好"只施加在派生侧（`CODE_RULES`）。

> 正确的自查方式：**跑完净化版构建后，`skills-v2/` 必须没有任何改动**
> （构建脚本只读 canonical、只写 `dist-v2/skillhub/`）。

---

## 当前两版差异

SkillHub 适配版相对 canonical，**只做这些**（全部在生成时施加，canonical 一行不动）：

1. `SKILL.md` frontmatter 补 `slug / displayName / summary / license / homepage / tags`（SkillHub 硬性要求）。
2. 去掉超长 `changelog`（含内部细节，对 marketplace 是噪声）。
3. 代码里 `__import__("pathlib")` → 常规 `import`（避免扫描器误报**动态导入**）。

**除此之外，内容完全一致。** —— 这正是「SkillHub 从 GitHub 拿到的东西必须符合合规基线」的落实方式。

---

## 常用命令

```bash
# 重新生成适配版（含守卫自检：无地址/密钥、无管道执行、含前置披露、frontmatter 齐全）
python3 scripts/build-skillhub.py

# 只校验已生成的产物
python3 scripts/build-skillhub.py --verify-only

# 官方 CLI 本地预检（不发布、不需要登录）
~/.local/bin/skillhub publish dist-v2/skillhub/expense-audit-v2 --dry-run

# ★ 正式发布：用本仓库的发布器（**带分类**，官方 CLI 不带）
python3 scripts/publish-skillhub.py --dry-run      # 看 payload
python3 scripts/publish-skillhub.py                # 发全部 4 个（含自动限频 70s）
python3 scripts/publish-skillhub.py expense-audit-v2   # 只发一个
```

> **为什么不用官方 CLI 发布**：官方 `skillhub publish` 的 payload 里**没有** `category` / `subCategories`
> 字段，发出来的 skill 永远是「未分类」——而分类决定它能否出现在**分类浏览**里。
> `scripts/publish-skillhub.py` 照官方 multipart 契约自己发，额外带上分类
> （分类配置的单一来源是 `scripts/skillhub_config.py`）。
> **实测（2026-09-29）：服务端接受这两个字段，且分类立即生效**（新版本号仍需审核）。

---

## 校验「两版没有互相污染」

```bash
# ① 跑完构建后，canonical 必须没有任何改动（构建只读 canonical、只写 dist-v2/skillhub/）
python3 scripts/build-skillhub.py && git status --porcelain skills-v2/
# → 应无输出

# ② 安装路径完全不引用 SkillHub（应为 0）
grep -c skillhub install.sh

# ③ 装出来的版本满足合规基线（无地址/密钥、无管道执行、无隐瞒措辞、含前置披露）
python3 evals/install_smoke.py --no-notify

# ④ 全量测试
python3 evals/validate_pack.py --run-tests
```
