# 滨河地下通道巡检交班

测绘员按轮次冻结各工区的通道图，检修登记员把关闭目标绑定到实际修订。交班员交付可离线使用的固定幅件。值班员即使无法访问源站，也能签发巡检路线并按原号复核已下达的安排。

## 运行

使用 Python 3.11 标准库及其 SQLite 支持。在项目根目录运行平台提供的完整回归入口和正常演示。

```text
python3 -B check_project.py
python3 -B -m routing.cli demo
```

也可直接用 `python3 -B -m unittest discover -s tests -t . -v` 运行全套业务测试。演示只在临时目录建两座账库，实收后移开源库。手算对照如下。

| 所选依据 | 分钟 | 共享口 |
| --- | ---: | --- |
| 西幅 5 分钟绕行，未选检修单 | 3 | P、Q |
| 西幅 5 分钟绕行，东幅随 F 封 P | 6 | Q |
| 西幅 7 分钟绕行，东幅随 F 封 P | 8 | Q |
| 西幅 5 分钟绕行，选回无封口东幅 | 3 | P、Q |

西幅经 P 到 Q 用 2 分钟，绕开 P 的两份西幅修订分别用 5 和 7 分钟。东幅从 Q 到终点用 1 分钟。演示重开值班库并复领原 6 分钟报告。

## 日常命令

下面的命令以空账库为起点。两次 `register` 会输出修订号。`issue` 将幅件写到指定文件并输出件号，把实收回执中的件号填入后续核定命令。临时试用可在项目根目录另建自己的示例副本。

```text
python3 -B -m issue.cli source.db init
python3 -B -m issue.cli source.db register samples/west-5.json
python3 -B -m issue.cli source.db register samples/east.json
python3 -B -m issue.cli source.db record 2 samples/east-f.json
python3 -B -m issue.cli source.db issue 1 west.piece
python3 -B -m issue.cli source.db issue 2 east.piece
python3 -B -m routing.cli offline offline.db init
python3 -B -m routing.cli offline offline.db receive west.piece
python3 -B -m routing.cli offline offline.db receive east.piece
python3 -B -m routing.cli offline offline.db route --start west S --end east T --notice F <西幅件号> <东幅件号>
python3 -B -m routing.cli offline offline.db read 1
```

`issue.cli` 的 `reissue 件号 输出文件` 按号重发归档正本。出件归档提交后才导出文件。导出路径写入失败时，可按已归档件号重发。离线命令也接受 `--start-portal P` 或 `--end-portal Q`。启动及重复 `init` 均保留操作员录入、实收和签报。通过显式 `register` 和 `record` 导入数据，示例文件只供主动选用。无结果的合法核定也会签报。错误写入标准错误并以非零状态退出。

## Python 接口和数据

连接使用普通 `sqlite3.Connection`，源站各库对象共用一条连接，值班库各对象也共用一条连接。分别调用 `issue.cli.initialize_source(connection)` 和 `routing.cli.initialize_offline(connection)` 初始化。库对象提交自身业务事务，请在没有外部未提交事务的连接上调用。

| 入口 | 输入及返回 |
| --- | --- |
| `survey.imports.register(store, round_id, tile_id, nodes, segments, portals, endpoints)` | 本幅清册以 `DirectedSegment`、`SharedPortal`、`EndpointRef` 表示，成功返回修订号。`RevisionStore.get` 可取固定修订。 |
| `closures.notices.record(revisions, notices, revision_id, notice_id, targets)` | `ClosureTargets` 分别列内部通道号和共享口号，返回固定声明。相同声明重投复用原绑定。更改同修订同单号的关闭目标须登记新修订。 |
| `issue.build.issue(revisions, notices, archive, revision_id)` | 返回 `IssuedPackage` 的件号和固定字节。`reissue(archive, package_id)` 返回存档原字节。后登记的声明只影响以后出件。 |
| `intake.receipts.receive(store, raw)` | 校验幅件后返回固定 `Receipt`。`IntakeStore.get` 按件号读取已验正本。 |
| `routing.reports.route(intake, reports, package_ids, start, end, notice_id=None)` | `Location(key, tile_id)` 定位幅内业务点，`Location(portal_id)` 定位共享口。返回 `SignedReport`，包含签报号、回执号、原请求和结果。 |
| `routing.history.read(reports, report_id)` | 返回原样签报，未知号抛出 `KeyError`。 |

图幅文件含轮次、图幅、本地节点、定向通道及两种定位表。通道分钟必须是严格正整数，布尔、浮点、零和负数均拒绝。通道编号在幅内唯一。每个共享口在本幅绑定一个本地节点，一个节点至多代表一个共享口。业务定位键可指向同一节点或已登记的共享口。所有通道及定位目标都必须先列为本地节点。检修文件按 `notice`、`segments`、`portals` 提供单号及两类目标。未知修订、件号或报告号抛出 `KeyError`。其他不合规输入抛出 `ValueError`，数据库签存异常由 SQLite 报告。

幅件有 V1 信封、固定件号和正文的 SHA-256 完整性摘要。离线验收检查引用、出处及代价格式，摘要用于发现正文变化。源站本地节点标识、原通道清册和业务键到原节点的映射留在源站。离站幅内转移包含整数分钟、公开端点和经过的共享口。固定件可以各自勘误，核定时每幅最多选一个件，件号必须实收且同轮。报告保留调用时的件号顺序。任一所选幅声明关闭的共享口在全程关闭，包括同幅中途经过及起终点。某幅缺所选单时使用其普通依据。单次请求最多选一张单。

值班库只使用实收证据拼接有向路线，按实际行进顺序返回共享口。幅件连接处同一次经过只记一次。可达的同点请求返回零分钟，在共享口同点时列该口一次。等价最短路线可任选。合法位置间无路时，结果分钟为 `None`，共享口序列为空。缺件、混轮、非法定位和签存失败均不增加报告或签报回执。重开后按原报告号读取结果，后续换件另行签报。

## 正常回归范围

`tests/test_survey.py` 和 `tests/test_closures.py` 核对严格分钟、定向通道和指定修订下的双类关闭目标。`tests/test_handoff.py` 核对重投、同号异件、摘要错误、原件重发、明确选旧件、原图留站和重复初始化。`tests/test_routes.py` 用真实断源场景核对整数累加、全程封口、两种绕行、同轮换件、不可达及历史复领，并通过 SQLite 触发器让签报回执写入失败，检查重开后的报告与回执计数。
