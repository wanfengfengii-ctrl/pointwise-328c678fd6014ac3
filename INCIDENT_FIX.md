# 交班幅件封口错报事故记录（F 单封 P）

## 现象

东幅随检修单 F 声明关闭共享口 P 后，值班员断源离线签报仍给出 3 分钟、依次经过 P、Q
的旧路线；西幅换用另一版修订得到同一份错报。期望两份西幅修订分别签 6、8 分钟且只经 Q，
换回无封口东幅恢复 3 分钟、经 P、Q。

## 根因（链路两处缺陷，均在离线侧，源站测绘与单据绑定本身正确）

1. 封口只在声明幅内生效（`routing/eligibility.py`）。
   `build_eligible_network` 已正确汇总各选件视图的 `closed_portals` 并集，但过滤
   转移时用的是每幅各自视图的 `local_closed`。东幅 F 视图关闭 P，只能挡掉东幅自身
   经过 P 的转移；西幅普通视图里 S→Q 途经 P 的转移不被任何本幅封口拦截，于是仍按
   2 分钟经 P 走线，再拼东幅 Q→T 的 1 分钟，错报 3 分钟。
   规则要求任一所选幅件声明关闭的共享口在整程关闭，含起终点与各幅同幅途中。

2. 出件证据只保留单条最短路（`issue/transfers.py`）。
   内部路网不出站，离线签报只能使用幅件中的公开转移。旧 `_local_paths` 对每个
   目标节点只留一条最短路：西幅 S→Q 仅保留 2 分钟、经过 P、Q 的一条，绕开 P 的
   5/7 分钟旁路（只经 Q）在出件时被压缩丢弃。仅修第 1 处时，P 被全程关闭后西幅
   再无可用 S→Q 转移，结果变成不可达，而非 6/8 分钟绕行。

## 修复

- `routing/eligibility.py`：转移资格过滤改用所有选件视图的封口并集 `closed_portals`，
  任一转移的途经口与并集相交即整条剔除；起终点封口判断仍由 `routing/search.py`
  用同一并集处理（含同点请求列口一次的语义）。
- `issue/transfers.py`：`_local_paths` 改为标签式最短路，对每个目标按“途经共享口
  集合”分别保留最省的一条，并以“口子集且不更贵”做支配剪枝；每个公开边界对按
  （起点、终点、分钟、口序）稳定排序输出全部候选。私有节点与通道号仍不出站，
  离站证据仍只含整数分钟、公开端点和经过的共享口，V1 信封、件号与摘要机制不变。

修复后西幅普通视图同时携带 S→Q 的 2 分钟（P、Q）与 5/7 分钟（仅 Q）两类证据；
F 封 P 时前者被全程剔除，选中后者并拼东幅 Q→T 1 分钟，得 6/8 分钟、只经 Q。

## 实测（2026-11-23，Python 3.11 标准库，仓库根目录）

- `python3 -B check_project.py`：修复前 19 项中 3 项失败
  （test_remote_portal_closure×2、test_unreachable_and_history，均误报 3 分钟）；
  修复并补回归后 21 项全部 PASS。
- `python3 -B incident.py`（源库出件后删除，仅靠离线库核定）：
  `{"ordinary": 3/[P,Q], "closed_5": 6/[Q], "closed_7": 8/[Q], "restored": 3/[P,Q]}`，
  退出码 0（修复前打印 PATROL_F_CLOSURE_ROUTE_MISMATCH，退出码 1）。
- `python3 -B -m routing.cli demo`：四项签报与按号复领的 6 分钟历史报告一致。
- README 命令行链路手测：F 封口签 6 分钟只经 Q；无单/换回无封口东幅均 3 分钟经 P、Q；
  以 P 为起点在 F 下签不可达（minutes=null）；未实收件号报错且退出码 1、不落报告；
  `reissue` 重发字节与原归档逐字节相同。

## 新增回归

- `tests/test_routes.py::test_remote_closure_blocks_same_tile_passage_elsewhere`：
  东幅 F 封 P 后，西幅与东幅途经 P 的转移整程失效，只能走西幅旁路，锁定根因 1。
- `tests/test_handoff.py::test_piece_keeps_every_portal_set_alternative`：
  西幅件普通视图对同一 S→Q 边界对必须同时保留 2 分钟（P、Q）与 5/7 分钟（仅 Q）
  两类口序证据，锁定根因 2。
