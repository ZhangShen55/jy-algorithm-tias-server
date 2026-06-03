# jy-algorithm-tias-server

基于 **Ultralytics YOLO** 的课堂智能分析算法服务（SeaCraft / 教育 IAS 场景）。对外提供 **FastAPI** HTTP 接口，支持 **IAS（智能分析平台）** 注册、保活、能力查询，以及 **人数统计、抬头（人脸）检测、学生行为、老师行为** 等多路推理。

---

## 功能概览

| 能力 | 说明 | 主要模型 / 逻辑 |
|------|------|------------------|
| **人数检测** | 在指定多边形 ROI 内检测头部相关目标并计数 | `person_count_*.pt`（类别：Head、Top_Head、Hat、Headphones、Shoulder） |
| **抬头 / 人脸** | ROI 内人脸框检测，用于抬头率等统计 | `face_count_*.pt` |
| **学生行为** | 玩手机、举手、睡觉、站立、阅读等 | `student_*.pt` + 与人脸/人数并行 |
| **老师行为** | 讲台区域人物、站/坐、板书、打电话（基于姿态关键点规则） | `teacher-pose.pt`（姿态 + 规则引擎） |

- **IAS 同步任务**（`/AE/SyncTasks`）：按任务下发的多边形列表，对本地或挂载目录中的图片做人数 + 人脸，可选输出画框结果图。  
- **学生 / 老师 REST 接口**（`/ImageDetect/...`）：支持 Base64、`data:` URL、HTTP(S) 图片 URL、或 `IMAGE_ROOT` 下的相对路径；可选多边形遮罩。

---

## 技术栈

- **Python 3** + **FastAPI** + **Uvicorn**（可选 **uvloop**）
- **Ultralytics YOLO**（`ultralytics`）
- **OpenCV**、**NumPy**、**PyTorch**
- 生产环境可通过 **Nginx** 对多 Uvicorn 实例做负载均衡（见 `app/start.sh`）

---

## 仓库结构

```
jy-algorithm-tias-server/
├── README.md                 # 本说明
└── app/
    ├── main.py               # FastAPI 入口、IAS 客户端生命周期
    ├── config.toml           # 默认配置示例（部署时常挂载或复制）
    ├── start.sh              # 启动脚本（单实例 / Nginx + 多实例）
    ├── requirements.txt      # PyTorch 2.6 / CUDA 11.8 主线依赖
    ├── requirements_cuda113.txt
    ├── Dockerfile            # pytorch 2.6 + cuda11.8 运行时
    ├── Dockerfile_cuda113    # CUDA 11.3 备选镜像
    ├── core/
    │   └── settings.py       # 配置加载、设备选择、YOLO 模型全局加载
    ├── api/                  # 路由：任务、容量、版本、日志等级、师生行为
    ├── services/             # 任务处理、IAS 注册/保活、师生行为推理
    ├── schemas/              # Pydantic 请求/响应模型
    └── models/               # 权重文件目录（需自行放置，见下文）
```

> **说明**：`Dockerfile` 中会 `COPY nginx/nginx.conf`；若你本地构建镜像，请在构建上下文中提供 `nginx/nginx.conf`（与 Dockerfile 中路径一致）。

---

## 模型文件

请将训练好的权重放到 **`app/models/`**（与 `settings.py` 中路径一致）。当前代码中约定的文件名包括：

| 变量 | 路径（相对 `app/core/settings.py`） |
|------|--------------------------------------|
| 人数 | `app/models/person_count_20251222_1920p.pt` |
| 人脸 | `app/models/face_count_20251212.pt` |
| 学生行为 | `app/models/student_20250819).pt`（若与仓库实际文件名不一致，请同步修改 `STUDENT_MODEL_PATH`） |
| 老师姿态 | `app/models/teacher-pose.pt` |

`app/models/READEME.md` 中说明该目录用于存放模型。

---

## 配置说明

### `config.toml`（或 `CONFIG_PATH` 指向的文件）

应用通过环境变量 **`CONFIG_PATH`** 指定配置文件，默认在 `settings.py` 中解析为 `app/config.toml`；Docker 内 `start.sh` 固定为 **`/app/config.toml`**。

常用字段：

| 字段 | 含义 |
|------|------|
| `AEM` | IAS 注册信息：`AppName`、`InstanceId`、`IpAddr`、`Port`、`MetaData`、`KeepaliveInterval` |
| `SERVER` | IAS 服务基地址，用于 `/AEM/Register`、`Keepalive`、`UnRegister` |
| `IMAGE_ROOT` | 同步任务或行为接口中**相对路径图片**的根目录 |
| `GPU_ID` | GPU 编号；设为字符串 **`cpu`** 时使用 CPU |
| `INSTANCE_COUNT` / `WORKERS_PER_INSTANCE` | 与 `start.sh` 配合：多实例时启动 Nginx + 多个 Uvicorn（后端端口从 8981 递增） |
| `Person_Thresd` | 人数模型各类别置信度阈值（Head、Top_Head、Hat 等） |
| `Face_Thresd` | 人脸检测阈值 |
| `Student_Thresd` | 学生行为各类别阈值（Using_phone、Hand_raising、Sleep 等） |

可选：`RESULT_IMAGE_ROOT`、`SAVE_RESULT_IMAGE`（在 `settings.py` 中定义，用于额外保存结果图）。

---

## HTTP API 摘要

除特别说明外，服务默认监听 **`8881`**。

### IAS / 运维相关（前缀 `/AE`）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/AE/SyncTasks` | IAS 同步任务：多边形 ROI + 图片 URI，返回每 ROI 人数与人脸 |
| POST | `/AE/SyncTasks2` | 与 SyncTasks 类似，实现位于 `task_service_base64`（适合内嵌图片等场景） |
| GET | `/AE/Capacity` | 能力/容量信息 |
| GET | `/AE/Capacity_v2` | 增强信息（连接数、处理图片数、运行时间等） |
| GET | `/AE/Version` | APP / Adapter / 算法版本及累计任务数等 |
| GET/PUT | `/AE/LogLevel` | 查询/设置日志级别 |

### 学生 / 老师行为

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/ImageDetect/student/v1.0.0` | 学生：人数(100)、人脸/抬头(101)、行为(201–205) |
| POST | `/ImageDetect/teacher/v1.0.0` | 老师：讲台人员(100)、站立(201)、坐(202)、板书(203)、打电话(204) |

**学生行为 `ObjectType` 编码**（`student_behavior_service.py`）：

- `100`：人数  
- `101`：人脸（抬头）  
- `201`：使用手机  
- `202`：睡觉  
- `203`：举手  
- `204`：站立  
- `205`：阅读  

**老师行为 `ObjectType` 编码**（`teacher_behavior_service.py`）：

- `100`：讲台区域检测到人（与姿态检测框一致）  
- `201`：站立（板书时也会计入站立）  
- `202`：坐着  
- `203`：板书（手腕高举 + 肘部角度等规则）  
- `204`：打电话（手腕与耳部距离规则）  

请求体见 `schemas/stu_tea_behavior.py`：`ImageList` 中每项含 `StoragePath`、`ImageId`、可选 `Points`（多边形）。

### OpenAPI

启动后访问：**`http://<host>:8881/docs`** 可查看交互式 Swagger 文档。

---

## 本地运行（开发）

1. 安装 **PyTorch**（需与 CUDA 版本匹配，或使用 CPU）。  
2. 安装依赖：

   ```bash
   cd app
   pip install -r requirements.txt
   ```

3. 将模型放入 `app/models/`，并按需修改 `app/core/settings.py` 中的路径或 `config.toml`。
4. 从 **`app` 的父目录** 启动（保证 `app` 为包名）：

   ```bash
   export CONFIG_PATH="/绝对路径/app/config.toml"
   uvicorn app.main:app --host 0.0.0.0 --port 8881 --reload
   ```

若 `config.toml` 中配置了有效的 `SERVER` 与 `AEM`，进程启动约 3 秒后会向 IAS 执行注册并启动保活线程。

---

## Docker 部署

- **主线**：`app/Dockerfile`（`pytorch/pytorch:2.6.0-cuda11.8-cudnn9-runtime`）。  
- **备选**：`app/Dockerfile_cuda113`（CUDA 11.3 + Python 3.8 + 独立 `requirements_cuda113.txt`）。

构建时需保证构建上下文包含：`app/`、`config.toml`、`start.sh`、以及 Dockerfile 引用的 **`nginx/nginx.conf`** 等文件。

容器内：

- 暴露端口 **8881**  
- `start.sh` 根据 `INSTANCE_COUNT` 选择单 Uvicorn 或 Nginx + 多 Uvicorn  

请将图片目录与模型通过卷挂载到容器内对应路径（如 `IMAGE_ROOT`、`/app/app/models`）。

---

## 与 IAS 的集成要点

- **注册**：`POST {SERVER}/AEM/Register`，成功时 `ResponseStatusObject.StatusCode == 2000`。  
- **保活**：后台线程按 `KeepaliveInterval`（秒）调用 `POST {SERVER}/AEM/Keepalive`。  
- **注销**：应用关闭时 `POST {SERVER}/AEM/UnRegister`。  
- 若未配置 `SERVER`，启动日志会提示无法注册，但推理接口仍可在本地使用。

---

## 版本与算法说明

应用版本、适配器版本与算法版本字符串定义在 **`app/core/settings.py`**（如 `APP_VER`、`ALG_VER`），`/AE/Version` 会返回这些信息及已处理同步任务累计数等。

---

## 许可证与作者

Docker 镜像中 `LABEL authors="SeaCraft"`。具体开源协议以仓库内授权文件为准（若未提供，请联系项目维护方）。

---

如有接口字段或 IAS 协议变更，请以 `app/schemas/` 与 `app/services/` 中的实现为准。
