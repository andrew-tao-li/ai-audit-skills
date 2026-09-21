# LobsterAI 2026.5.22 文件级回归测试

测试日期：2026-09-17  
宿主：LobsterAI 2026.5.22，macOS  
安装状态：已移除同名 `0.1.0` 条目，仅保留三个 `0.1.1` skill  
测试数据：`evals/fixtures/` 下的纯合成文件  
输出根目录：`evals/lobsterai-output/file-regression-2026-09-17/`

## 结论

6/6 场景通过。LobsterAI 实际读取测试文件、运行已安装 skill 的本地脚本，并生成可复核产物。

| Skill | 场景 | 核心期望 | 结果 |
|---|---|---|---|
| `expense-audit` | `clean-control` | 6 条有效、0 坏行、0 finding、0 evidence；中文字段映射正确 | PASS |
| `expense-audit` | `dirty-input` | 2 条有效、3 条坏行、0 finding；三类错误原因完整；空币种默认为 CNY | PASS |
| `procurement-fraud` | `clean-control` | 五张表全部载入；0 坏行、0 finding；不建议调查移交 | PASS |
| `procurement-fraud` | `dirty-input` | 3 条坏行；有效供应商 1、采购单 1；可选表缺失被显式记录 | PASS |
| `investigation-assistant` | `scope-filter` | 3 个原始文件；4 条结构化记录全部越界；时间线 0、finding 0 | PASS |
| `investigation-assistant` | `authorization-denied` | 返回码 2；错误信息指出授权未确认；输出目录不存在 | PASS |

调查场景另验证了三个原始文件与只读副本 SHA-256 一致、副本无写权限；全部成功场景均记录 `network_access:false`。

## 独立复核

LobsterAI 完成执行后，在宿主外运行统一校验器：

```bash
python3 evals/verify_file_regression.py \
  --root evals/lobsterai-output/file-regression-2026-09-17
```

结果为 `status: pass`，核验了 5 个有产物的成功场景，并确认未授权场景没有输出目录。

## 边界

本轮显式指定了 skill，验证的是版本清理后的 `0.1.1` 文件执行能力和边界行为。它没有重跑 6 条隐式路由小样本，也不能替代每个 skill 40 条的正式路由验收。
