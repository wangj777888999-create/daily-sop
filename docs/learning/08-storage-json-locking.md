# 08 · JSON 持久化 + fcntl 锁：极简持久化的工程要点

> 本章你将看到的代码：
> - `backend/sops/storage.py`（全文 78 行）
> - `data/sops.json`、`data/execution_logs.json`

---

## 1. 为什么不用数据库

第 1 章已经说过：单用户 + 数据量 < 万级 + 部署在本机。SQLite 也行，但即便 SQLite 你也要：

- 写 schema 迁移代码（Alembic / 自己手撸）。
- 处理 `Connection` 生命周期。
- 数据查看不再是"打开 JSON"那么简单。

**JSON + fcntl 锁 + 原子写**就够。**Pydantic 把"序列化/反序列化 + 校验"都办了**，几乎是零成本。

但不能写成"裸 `open + json.dump`"——并发 / 崩溃场景下会丢数据。本章告诉你怎么写"靠谱的极简持久化"。

---

## 2. 全文 78 行，逐段过

### 2.1 路径与读取

```python
# backend/sops/storage.py:1-17
import fcntl
import json
import os
from typing import List, Optional
from .models import SOP, ExecutionLog

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data")
SOPS_FILE = os.path.join(DATA_DIR, "sops.json")
LOGS_FILE = os.path.join(DATA_DIR, "execution_logs.json")


def _read_json(path: str):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        return json.load(f)
```

要点：

- **`fcntl.flock(f, LOCK_SH)`**：**共享锁**。多个读可以同时持有，但写者来时会阻塞。
- **不显式 `flock(f, LOCK_UN)` 解锁**：因为 `with open(...)` 退出时文件关闭，锁自动释放。这依赖于"文件关闭即解锁"的 POSIX 语义——可移植但要心里有数。
- **不存在则返回 `[]`**：避免首次启动 `FileNotFoundError`。

### 2.2 写入：原子 + 排他锁

```python
# backend/sops/storage.py:20-26
def _write_json(path: str, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
```

**两个保护**：

1. **写到 `.tmp`，再 `os.replace(tmp, path)`**：`os.replace` 在 POSIX/NTFS 上是**原子操作**（要么完整看到旧文件，要么完整看到新文件）。如果中途崩溃，旧文件还在；只是会留下 `.tmp` 孤儿（无害）。
2. **`LOCK_EX` 独占锁**：避免两个进程同时写同一份 `.tmp`（虽然 `.tmp` 路径相同，仍可能冲突）。

> 这套写法在现实里叫"write-and-rename pattern"，几乎是**不上数据库时的标配**。

### 2.3 业务函数：典型的"读-改-写"

```python
# backend/sops/storage.py:42-51
def save_sop(sop: SOP) -> SOP:
    sops = get_all_sops()
    for i, existing in enumerate(sops):
        if existing.id == sop.id:
            sops[i] = sop
            _write_json(SOPS_FILE, [s.model_dump(mode="json") for s in sops])
            return sop
    sops.append(sop)
    _write_json(SOPS_FILE, [s.model_dump(mode="json") for s in sops])
    return sop
```

逻辑很直白：

1. 读全部 SOPs。
2. 如果找到同 id 就替换，否则 append。
3. 一次性写回。

**"读-改-写"的代价**：每次保存一条 SOP，整个文件被读一遍 + 写一遍。本项目数据 < 几百 KB，无所谓。**如果数据涨到几十 MB，必须换数据库**——这是规模红线。

### 2.4 `model_dump(mode="json")`

```python
[s.model_dump(mode="json") for s in sops]
```

- `model_dump()` 把 Pydantic model 转成 dict。
- `mode="json"` 让 datetime 等非 JSON 原生类型被序列化为字符串（`"2026-04-28T10:30:00"`）。
- 不带 `mode="json"` 的话直接 `json.dump` 会因 datetime 无法序列化而报错。

> 这是 Pydantic v2 的关键 API，比 v1 时代的 `dict()` + 自己写 encoder 优雅一截。

---

## 3. 这套机制不能保证什么

| 能保证 | 不能保证 |
|---|---|
| 单机进程间不同时写穿一份文件 | 跨机器 / 跨容器并发（fcntl 是本地） |
| 进程崩溃不损坏文件 | 磁盘满时写 `.tmp` 失败 → 数据丢失（未做 fsync） |
| 同进程内多线程写不冲突（在 GIL + flock 双重保护下） | 高并发写吞吐（每次都锁全文件） |
| 简单查询（`get_sop_by_id`）正确 | 复杂查询、聚合、索引——你得自己 grep |

---

## 4. 一个关键安全点：`fsync` 没做

`os.replace(tmp, path)` 是原子的，**但前提是数据已落盘**。如果 `_write_json` 写完 `.tmp`、`os.replace` 完，OS 还在 page cache 里，此时断电——**新数据可能丢**（你以为已经写入了）。

正经做法：

```python
with open(tmp, "w", encoding="utf-8") as f:
    fcntl.flock(f, fcntl.LOCK_EX)
    json.dump(data, f, ensure_ascii=False, indent=2)
    f.flush()
    os.fsync(f.fileno())   # ← 强制刷盘
os.replace(tmp, path)
```

**本项目没做**——单用户、笔记本基本不会断电、丢一条新建 SOP 也只是再点一次。但**如果你在做"金融 / 凭证 / 法律相关"的项目，必须 fsync**。

---

## 5. JSON 持久化的"什么时候必须换数据库"

清单：

1. **多用户写**（不是单进程）。
2. **数据 > 50MB**（每次读全文件 IO 不再"零成本"）。
3. **要支持并发查询/分析**（单文件全锁 → 吞吐崩盘）。
4. **要事务性保证**（"扣款 + 转账"两步必须一起成功）。
5. **要复杂查询**（join、agg、index）。

满足任何一条都换。从 JSON 迁到 SQLite **极其便宜**（几个小时）——所以不要提前优化。

---

## 6. 已知小缺陷

- **读锁不释放显式标记**：`fcntl.flock(f, LOCK_SH)` 后没显式 `LOCK_UN`，依赖 close。这写法没错，但**审计 explore agent 提到了**——若以后有别的需求（比如 with 块里多次操作），最好显式 unlock。
- **没有 fsync**（见第 4 节）。
- **没有备份机制**：意外 `rm data/sops.json` 直接清零。**做个 `git commit data/` 的 daily cron 是简单解**。

---

## 动手练习

1. **写一个并发测试**：开两个 Python 进程同时调用 `save_sop`，看是否会有数据竞争。预期：因为 `LOCK_EX`，两个进程会串行——但你可能会发现"读时间窗口"内的不一致（两进程都读到了 N 条，各自加 1 条，最后只剩 N+1 而不是 N+2）。这就是**"读-改-写"在并发下的经典问题**。
2. **加 fsync**：按第 4 节加 `os.fsync`，跑一下 SOP 创建测试看吞吐变化（笔记本上一般 10ms → 30ms）。
3. **加备份**：写一个 cron 脚本每天 `cp data/sops.json data/backups/sops-$(date +%F).json`。**最简单的灾难恢复**。

## 延伸阅读

- LWN 的 [Atomic file writes](https://lwn.net/Articles/789600/) —— write-and-rename 的工程踩坑史。
- 想理解 `fsync` / `fdatasync` / `O_DIRECT`：[The dangers of fsync](https://danluu.com/fsync/)。
- Python `fcntl` 模块的 [官方文档](https://docs.python.org/zh-cn/3/library/fcntl.html)：仅限 Unix；Windows 上需要换 `msvcrt.locking`。
