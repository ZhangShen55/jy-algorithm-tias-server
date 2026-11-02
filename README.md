# jy-algorithm-tias-server

基于 **Ultralytics YOLO** 的课堂智能分析算法服务（SeaCraft / 教育 IAS 场景）。对外提供 **FastAPI** HTTP 接口，支持 **能力查询、人数统计、抬头（人脸）检测、学生行为、老师行为** 等多路推理。

---

## 功能概览

| 能力 | 说明 | 主要模型 / 逻辑 |
|------|------|------------------|
| **人数检测** | 在指定多边形 ROI 内检测头部相关目标并计数 | `person_count_*.pt`（类别：Head、Top_Head、Hat、Headphones、Shoulder） |
| **抬头 / 人脸** | ROI 内人脸框检测，用于抬头率等统计 | `face_count_*.pt` |
| **学生行为** | 玩手机、举手、睡觉、站立、阅读等 | `student_*.pt` + 与人脸/人数并行 |
| **老师行为** | 讲台区域人物、站/坐、板书、讲授（同主体多标签聚合） | `teacher_behavior.pt` |

- **IAS 同步任务**（`/AE/SyncTasks`）：按任务下发的多边形列表，对本地或挂载目录中的图片做人数 + 人脸，可选输出画框结果图。  
- **学生 / 老师 REST 接口**（`/ImageDetect/...`）：支持 Base64、`data:` URL、HTTP(S) 图片 URL、或 `IMAGE_ROOT` 下的相对路径；可选多边形遮罩。

---

## 技术栈

- **Python 3** + **FastAPI** + **Uvicorn**（可选 **uvloop**）
- **Ultralytics YOLO**（`ultralytics`）
- **OpenCV**、**NumPy**、**PyTorch**
- 生产环境可通过 **Nginx** 对多 Uvicorn 实例做负载均衡（见 `tias/start.sh`）

---

## 仓库结构

```
jy-algorithm-tias-server/
├── README.md                 # 本说明
├── tias/
    ├── main.py               # FastAPI 入口、IAS 客户端生命周期
    ├── config.toml           # 默认配置示例（部署时常挂载或复制）
    ├── config.toml.example   # TIAS 6.0 配置样例
    ├── start.sh              # 启动脚本（单实例 / Nginx + 多实例）
    ├── requirements.txt      # PyTorch 2.6 / CUDA 11.8 主线依赖
    ├── requirements_cuda113.txt
    ├── docker/               # Dockerfile、compose、secure runtime 部署入口
    ├── core/
    │   └── settings.py       # 配置加载、设备选择、YOLO 模型全局加载
    ├── api/                  # 路由：师生行为、WorkerStatus、Health、Drain
    ├── services/             # 师生行为推理、本地准入、注册心跳
    ├── schemas/              # Pydantic 请求/响应模型
    └── models/               # 权重文件目录（需自行放置，见下文）
```

> **说明**：Docker 构建需从仓库根目录执行，`tias/docker/Dockerfile*` 会引用 `tias/docker/nginx.conf` 和 `scripts/` 下的构建脚本。

---

## 模型文件

请将训练好的权重放到 **`tias/models/`**（与 `settings.py` 中路径一致）。当前代码中约定的文件名包括：

| 变量 | 路径（相对 `tias/core/settings.py`） |
|------|--------------------------------------|
| 人数 | `tias/models/person_count_20251222_1920p.pt` |
| 人脸 | `tias/models/face_count_20251212.pt` |
| 学生行为 | `tias/models/student_20250819.pt`（若与仓库实际文件名不一致，请同步修改 `STUDENT_MODEL_PATH`） |
| 老师行为 | `tias/models/teacher_behavior.pt` |

`tias/models/READEME.md` 中说明该目录用于存放模型。

---

## 配置说明

### `config.toml`（或 `CONFIG_PATH` 指向的文件）

应用通过环境变量 **`CONFIG_PATH`** 指定配置文件，默认在 `settings.py` 中解析为 `tias/config.toml`；Docker 内 `start.sh` 默认读取 **`/workspace/tias/config.toml`**。

常用字段：

| 字段 | 含义 |
|------|------|
| `IMAGE_ROOT` | 同步任务或行为接口中**相对路径图片**的根目录 |
| `GPU_ID` | GPU 编号；设为字符串 **`cpu`** 时使用 CPU |
| `INSTANCE_COUNT` / `WORKERS_PER_INSTANCE` | 与 `start.sh` 配合：多实例时启动 Nginx + 多个 Uvicorn（后端端口从 8981 递增） |
| `Person_Thresd` | 人数模型各类别置信度阈值（Head、Top_Head、Hat 等） |
| `Face_Thresd` | 人脸检测阈值 |
| `Student_Thresd` | 学生行为各类别阈值（Using_phone、Hand_raising、Sleep 等） |
| `Teacher_Behavior_Thresd.MergeIoU` | 新老师行为模型同主体多类别框的高重叠合并阈值，默认 `0.8` |
| `Teacher_Behavior_Thresd.SubjectClusterIoU` | 主体聚类 IoU 阈值，用于把同一老师的姿态框和授课行为框合成一个主体，默认 `0.45` |
| `Teacher_Behavior_Thresd.ImageSize` | 新老师行为模型推理尺寸，默认 `640` |
| `Teacher_Behavior_Thresd.sit` / `stand` / `bbwriting` / `teach` | 新老师行为模型各类别默认置信度阈值；`sit` / `stand` 默认 `0.4`，`bbwriting` / `teach` 默认 `0.25`，接口请求中同名字段可临时覆盖 |
| `Teacher_Behavior_Thresd.KeepOnlyMainSubject` | 是否只保留一个主老师主体，默认 `true` |
| `Teacher_Behavior_Thresd.MainSubjectStrategy` | 主主体选择策略，默认 `posture_confidence`：优先按 `sit` / `stand` 姿态置信度选择老师主体 |
| `Teacher_Behavior_Thresd.PostureConflictRatio` | `sit` / `stand` 同时过阈值时的置信度差值比例阈值，默认 `0.10` |
| `Teacher_Behavior_Thresd.PostureConflictDefault` | 姿态冲突不明显或缺失时的默认姿态，默认 `stand` |
| `Teacher_Behavior_Thresd.ForcePostureWhenMissing` | 主体存在但姿态都未过阈值时是否强制输出默认姿态，默认 `true` |

可选：`RESULT_IMAGE_ROOT`、`SAVE_RESULT_IMAGE`（在 `settings.py` 中定义，用于额外保存结果图）。

---

## HTTP API 摘要

除特别说明外，服务默认监听 **`8881`**。

### 运维相关（前缀 `/AE`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/AE/WorkerStatus` | TIAS 6.0 实例状态、并发、队列和耗时指标 |
| GET | `/AE/Health` | 轻量健康检查 |
| PUT | `/AE/Drain` | 实例进入排空状态，不再接收新批次 |
| POST | `/AE/SyncTasks` | 旧 IAS 同步任务，默认不暴露；`TiasExposeLegacySyncTasks=true` 时启用 |
| POST | `/AE/SyncTasks2` | 旧 IAS 同步任务 base64 变体，默认不暴露 |

6.0 默认移除 `/AE/Capacity`、`/AE/Capacity_v2`、`/AE/Version`、`/AE/LogLevel` 和 `/ImageDetect/student/v1.0.1`。

### 学生 / 老师行为

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/ImageDetect/student/v1.0.0` | 学生：人数(100)、人脸/抬头(101)、行为(201–205) |
| POST | `/ImageDetect/teacher/v1.0.0` | 老师：讲台人员(100)、坐(201)、站立(202)、板书(203)、讲授(204) |

**学生行为 `ObjectType` 编码**（`student_behavior_service.py`）：

- `100`：人数  
- `101`：人脸（抬头）  
- `201`：使用手机  
- `202`：睡觉  
- `203`：举手  
- `204`：站立  
- `205`：阅读  

**老师行为 `ObjectType` 编码**（`teacher_behavior.pt` + 同主体 IoU 聚合）：

- `100`：讲台区域检测到老师主体
- `201`：坐着（`sit`）
- `202`：站立（`stand`）
- `203`：板书（`bbwriting`）
- `204`：讲授（`teach`）

老师接口会按 `SubjectClusterIoU` 把同一老师的姿态框和授课行为框聚合为一个主体。默认只保留一个主主体，选择规则为优先按 `sit` / `stand` 姿态置信度确认主体，再保留 `bbwriting` / `teach` 等授课行为。`sit` / `stand` 最终互斥；当两者置信度差值比例小于等于 `PostureConflictRatio` 时默认输出 `stand` 并标记 `SuspectedSitting=true`，主体存在但姿态都没过阈值时按 `PostureConflictDefault` 兜底输出并标记 `PostureFallback=true`。

老师接口请求体可选传 `Teacher_Behavior_Thresd` 覆盖单次请求阈值，例如只覆盖 `sit` 和 `teach`：

```json
{
  "ImageList": [],
  "Teacher_Behavior_Thresd": {
    "sit": 0.35,
    "teach": 0.4
  }
}
```

未传的类别继续使用 `tias/config.toml` 中的默认阈值。

请求体见 `schemas/stu_tea_behavior.py`：`ImageList` 中每项含 `StoragePath`、`ImageId`、可选 `Points`（多边形）。

### OpenAPI

启动后访问：**`http://<host>:8881/docs`** 可查看交互式 Swagger 文档。

---

## 本地运行（开发）

1. 安装 **PyTorch**（需与 CUDA 版本匹配，或使用 CPU）。  
2. 安装依赖：

   ```bash
   pip install -r tias/requirements.txt
   ```

3. 将模型放入 `tias/models/`，并按需修改 `tias/core/settings.py` 中的路径或 `config.toml`。
4. 从仓库根目录启动：

   ```bash
   export CONFIG_PATH="/绝对路径/tias/config.toml"
   uvicorn tias.main:app --host 0.0.0.0 --port 8881 --reload
   ```

服务启动后不再向 IAS 执行注册、注销或保活请求，推理接口可直接在本地或容器内使用。

### 视觉任务编排服务

Kafka 消费、课程任务编排、TIAS 调度、指标聚合和结果入库由独立仓库 `jy-vision-orchestrator-server` 负责。本仓库不再包含编排服务源码、Kafka 生产脚本或课次任务夹具。

TIAS 只通过 `[TIAS].VisionOrchestratorBaseUrl` 向编排服务注册并上报心跳。编排服务的部署和测试方式请查看独立仓库的 `README.md` 和 `app/RUNNING.md`。

---

## Docker 部署

Docker 构建入口统一放在 `tias/docker/`：

- **开发/普通部署**：`tias/docker/Dockerfile`（PyTorch 2.6 / CUDA 11.8）。
- **CUDA 11.3 兼容部署**：`tias/docker/Dockerfile.cuda113`（CUDA 11.3 + Python 3.8 + `requirements_cuda113.txt`）。
- **生产 secure runtime**：`tias/docker/Dockerfile.runtime`（最小运行镜像、Cython 编译产物、加密模型挂载）。

构建时需从仓库根目录执行，保证构建上下文包含 `tias/`、`scripts/` 和 `tias/docker/nginx.conf` 等文件。

容器内：

- 暴露端口 **8881**  
- `start.sh` 根据 `INSTANCE_COUNT` 选择单 Uvicorn 或 Nginx + 多 Uvicorn  

请将图片目录与模型通过卷挂载到容器内对应路径（如 `IMAGE_ROOT`、`/workspace/tias/models`）。

---

## 版本与算法说明

应用版本、适配器版本与算法版本字符串定义在 **`tias/core/settings.py`**（如 `APP_VER`、`ALG_VER`）。6.0 默认不再暴露 `/AE/Version`，版本和模型信息通过注册/心跳字段上报给 vision_orchestrator。

---

## 许可证与作者

Docker 镜像中 `LABEL authors="SeaCraft"`。具体开源协议以仓库内授权文件为准（若未提供，请联系项目维护方）。

---

如有接口字段或 IAS 协议变更，请以 `tias/schemas/` 与 `tias/services/` 中的实现为准。
