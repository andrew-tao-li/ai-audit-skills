# WorkBuddy 5.5.6 文件级回归测试

测试日期：2026-09-17  
宿主：WorkBuddy 5.5.6，macOS  
目标版本：三个 skill 均为 `0.1.1`  
测试数据：`evals/fixtures/` 下的纯合成文件  
输出根目录：`evals/workbuddy-output/file-regression-2026-09-17/`

## 结论

6/6 场景通过。它们是实际读取 CSV/JSON/TXT、运行 skill 脚本并检查输出文件的回归测试，不是知识问答。

| Skill | 场景 | 核心期望 | 结果 |
|---|---|---|---|
| `expense-audit` | `clean-control` | 6 条有效、0 坏行、0 finding、0 evidence；中文字段映射正确 | PASS |
| `expense-audit` | `dirty-input` | 2 条有效、3 条坏行、0 finding；三类错误原因完整；空币种默认为 CNY | PASS |
| `procurement-fraud` | `clean-control` | 五张表全部载入；0 坏行、0 finding；不建议调查移交 | PASS |
| `procurement-fraud` | `dirty-input` | 3 条坏行；有效供应商 1、采购单 1；三张可选表记为未提供 | PASS |
| `investigation-assistant` | `scope-filter` | 3 个原始文件；4 条结构化记录全部越界；时间线 0、finding 0 | PASS |
| `investigation-assistant` | `authorization-denied` | 返回码 2；先拒绝后产出；输出目录不存在 | PASS |

调查场景另验证了三个原始文件与只读副本 SHA-256 一致，副本无写权限，越界记录的 Evidence ID 均可回到证据文件。所有成功场景的 manifest 均为 `network_access:false`。

## 独立复核

WorkBuddy 完成执行后，在宿主外运行统一校验器：

```bash
python3 evals/verify_file_regression.py \
  --root evals/workbuddy-output/file-regression-2026-09-17
```

结果为 `status: pass`，发现并核验 5 个成功场景，且确认未授权场景没有输出目录。之所以是“5 个成功场景”，是因为第 6 个场景的正确结果正是拒绝执行、不创建产物。

WorkBuddy 自身生成的逐项记录保存在：

- `evals/workbuddy-output/file-regression-2026-09-17/regression-report-2026-09-17.md`
- `evals/workbuddy-output/file-regression-2026-09-17/regression-report-procurement-investigation-2026-09-17.md`

## 边界

本轮显式指定了要使用的三个 skill，因此证明的是文件处理和产物契约，不计入隐式路由准确率。每个 skill 的 40 条独立会话路由验收仍是单独的未完成工作。
