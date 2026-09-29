# 两个版本：原版 与 SkillHub 净化版

> **一句话**：**原版归原版，净化版只服务 SkillHub；任何一方的需求，都不许倒灌到另一方。**

---

## 为什么会有两个版本

| | 原版（canonical） | 净化版（SkillHub edition） |
|---|---|---|
| **面向谁** | 通过「一段话安装」的 Agent 用户（GitHub 分发） | **只**给 SkillHub.cn 上架 |
| **在哪** | `skills-v2/<skill>/` | `dist-v2/skillhub/<skill>/`（**生成物**） |
| **怎么到用户手里** | `install.sh` → GitHub release → 用户机器 | `skillhub publish dist-v2/skillhub/<skill>` |
| **谁是真相源** | ✅ 唯一真相源，手工维护 | ❌ 派生，由 `scripts/build-skillhub.py` 生成 |

---

## 铁律：需求不许倒灌

> **SkillHub 的要求，只能改净化版；GitHub 的要求，只能改原版。**
> **绝不因为「SkillHub 审核会挑刺」而去改原版。**

这条规则是有来历的：2026-09-27 我为了"让 SkillHub 的扫描器不误报"，把原版 `cli.py` 里的
`__import__("pathlib")` 改成了常规 `import`——**这正是一次倒灌**，已全部回退，
并删掉了当时多发的那个 release。

> 注意：那次之后，**原版自己也有正常的功能迭代**（0.2.8 状态过滤、0.2.9 出差交叉核验），
> 所以**不要**再用"`git diff <某个旧 tag>` 为空"来判断有没有倒灌。正确的判断方式是下面这条：
> **跑完净化版构建后，`skills-v2/` 必须没有任何改动**（构建脚本只读 canonical、只写 `dist-v2/skillhub/`）。

---

## 两版差异（当前）

净化版相对原版，**只做这些**（全部在生成时施加，原版文件一行不动）：

1. 删 `references/feedback.md`、`scripts/build_feedback.py`
   —— 去掉**硬编码 webhook key** 与**数据外发**（SkillHub 安全审核会判「数据外发」）。
2. `SKILL.md` 删「版本检查与一键更新」「匿名反馈」两节，换成无外发的「反馈与更新」
   —— 去掉 `curl … | bash`（SkillHub 会判「远程执行」）。
3. `SKILL.md` frontmatter 补 `slug / displayName / summary / license`
   —— SkillHub 的硬性要求（原版用的是 `name/description/metadata`）。
4. 去掉超长 `changelog`（含内部细节，对 marketplace 是噪声）。
5. 代码里 `__import__("pathlib")` → 常规 `import`（避免扫描器误报**动态导入**）。

**除此之外，核心审计脚本一模一样。** 净化版不是一个"弱化版"，只是"换了个外壳"。

---

## 常用命令

```bash
# 重新生成净化版（含自检：无 key / 无外发 / 无 curl|bash / 无动态导入 / frontmatter 齐全）
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
> （分类配置的单一来源是 `scripts/build-skillhub.py` 的 `SKILLS`）。
> **实测（2026-09-29）：服务端接受这两个字段，且分类立即生效**（新版本号仍需审核）。

**已验证（2026-09-28 首次，之后每次改 skill 都会重跑）**：官方 CLI `skillhub 2026.8.5`
（`--cli-only --no-self-upgrade`，装到 `~/.skillhub` + `~/.local/bin/skillhub`，未改 `.zshrc`），
4 个 skill 的 `--dry-run` **全部通过**（随版本迭代会变，以最近一次运行为准）。

> 注：`--cli-only` **不会**安装该 CLI 自带的 `find-skills` 技能（那是个 "MUST trigger" 的技能，
> 会与我们的审计技能抢触发）；只有默认模式 / `--skill-only` 才会装。装之前已审过安装脚本：
> 无 sudo、只写 `~/.skillhub` 与 `~/.local/bin`。

---

## 校验「两版没有互相污染」

```bash
# ① 跑完净化版构建后，原版必须没有任何改动（构建只读 canonical、只写 dist-v2/skillhub/）
python3 scripts/build-skillhub.py && git status --porcelain skills-v2/
# → 应无输出

# ② 安装路径完全不引用净化版（应为 0）
grep -c skillhub install.sh

# ③ 装出来的必须是【原版】：含反馈机制、含一键更新、不含 SkillHub 字段
python3 evals/install_smoke.py --no-notify
# → 报告里应有「原版特征：保留 references/feedback.md」等 4 项 ✅（install_smoke 每日自动跑）
```
