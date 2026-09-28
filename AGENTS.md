# AI Audit Skill Pack 开发约束

- 用户的明确指示优先于本文件和各 skill 的默认流程。
- 每个 skill 必须能脱离本仓库独立运行，不得引用 `../../shared`。
- 核心脚本不得调用大模型 API、上传数据、写入业务系统或保存密钥。
- 默认只读输入；输出必须写入用户指定的新目录，不覆盖原始资料。
- 先做数据体检和确定性分析，再由宿主 Agent 解释结果。
- `finding` 必须引用存在的 `evidence_id`；不得把异常、相似或关联写成舞弊认定。
- 事实、推断、假设和最终判断必须分开。脚本不产生最终责任判断。
- 新规则必须有合成数据正例、合理异常反例和可解释参数。
- 路径使用 `pathlib.Path`，文本使用 UTF-8，兼容 Windows、macOS 和 Linux。
- 修改后运行对应 skill 的单元测试及 `python3 evals/validate_pack.py`。
- **改了面向 Agent 的部分（`description` / `SKILL.md` 工作流 / `scripts/`）后，跑 `python3 evals/cross-agent/run_acceptance.py`**：它在真实 OpenCode Agent 上验证「该触发时是否加载正确 skill、是否执行脚本、是否产出预期文件」，结果写在 `evals/cross-agent/results/latest.md`。**注意它测的是仓库代码（`opencode.json` → `./skills-v2`），不是 release。**
- **发布 release 后，跑 `python3 evals/install_smoke.py`**：它从 `releases/latest/download/` 下载 → 用 `install.sh` 装到临时目录 → 真跑一遍，核对「release 版本 == `VERSIONS.json`」「sha256 == 本机 dist」「装完能产出 dashboard」。这补上了**用户真正的安装路径**（以前零覆盖，已因此踩坑两次）。已接入 `evolve.sh` Step 1c，每日自动跑，漂移会体现在日报「安装冒烟」行。
- **原版与 SkillHub 净化版并存，需求不许倒灌**（详见 `docs/two-editions.md`）：`skills-v2/` 是**唯一真相源与唯一安装路径**；`dist-v2/skillhub/` 只是给 SkillHub 的派生物（`python3 scripts/build-skillhub.py` 生成）。**SkillHub 的审核要求只能改净化版，绝不为了过审去改原版；反之亦然。** 改完用 `git diff v0.3.5 --stat -- skills-v2/` 自检原版是否被动过。
- **改了 `skills-v2/` 下任何文件后，必须立刻重打包并重传 release**：跑 `./scripts/build-dist.sh` → 上传 4 个 zip 到新 release（或用 `gh release`）→ **下载 release zip 核对内容与 sha256 一致**。用户/测试者是从 **release** 安装的，不是从 `main` 分支——只改 main 不重打包 = 用户永远看不到更新。（已有两次事故：一次传错 release ID，一次漏重打包。）
- 文档/README/`install.md` 中**不要写死 release 版本号**（会随每次 release 过时）；需要指向最新版时用 `releases/latest/download/<asset>` 别名或 `releases/latest` 链接。
- **例行脚本（`evolve.sh`）的两条铁律**：① **任一检查失败都不能中止整个例行**——`set -e` 下写 `X=$(某命令)` 会让一次网络抖动直接杀掉脚本（2026-09-28 事故：冒烟瞬时失败 → 日报彻底消失）；必须写 `X=$(某命令 || true)` 并自己判断成败。② **必须有兜底通知**（`trap on_error ERR`）——否则「用户什么也没收到」本身就是最难排查的故障模式。
- 面向用户的文案（README、公众号、marketplace description）**只写事实**：不虚构作者人数、从业年限、测试者数量、机构背书。
