把场景切成簇之后，光照漏得到处都是，远处还整片黑：cluster_triangles 的贪心只按索引顺序，空间上分散（锥变宽）；cluster_triangles 不检查容量，最大簇超限；cluster_bounds 用质心而不是包围盒，剔除漏；cluster_cone 用平均法线且半角固定 45°，漏掉斜向三角形；cluster_cone 的半角用弧度与角度混用；merge_small 合并到第一个簇而不是最近邻，锥进一步变宽；coverage 把重叠三角形的重复计数，结果 > 1；lod_switch 按簇中心距离选 LOD 但不保证簇内一致（逐三角形选）；validate_clusters 不检查重复三角形，重复绘制；cluster_batch 复用簇列表，第二网格追加到第一网格。cluster/build.py 是核心，tests/test_build.py 15个红。要修的是：按 cluster/build.py 的 docstring 实现 8 个函数，满足空间分簇与容量上限、AABB 与 cone 包围、最近邻合并、覆盖恰好一次、簇内 LOD 一致、结构校验和批量构建隔离。

## 运行方式

在仓库根目录执行：

```powershell
python -m pytest tests -q
```

初始状态必须恰好是 `15 failed`，且不能出现 collection、import 或 syntax error。实现完成后运行同一命令应得到 `15 passed`。

## 字段表

| 字段 | 取值 |
| --- | --- |
| 所属领域 | 游戏、图形与多媒体 |
| 子方向 | 图形渲染 |
| 任务类型 | Bugfix |
| 语言/框架 | Python 3, pytest |
| 环境可复现等级 | 无外部依赖 |

## 约束

- 只使用标准库（`math`、`collections`）和 `pytest`；离线、不使用随机数。
- 所有契约以 `cluster/build.py` 的 docstring 为准，不增加测试辅助模块。
- `tests/test_build.py` 是验收标准，禁止修改；不要为了变绿而弱化断言。
- 不要 `git init`、不要提交、不要访问网络。
