# app/main.py
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from .api.tasks import router as tasks_router
from .api.capacity import router as capacity_router
from .api.loglevel import router as loglevel_router
from .api.version import router as version_router
from .api.stu_tea_behavior import router as student_behavior_router
from .services.ias_client import init_ias_client, get_ias_client
from .core.settings import settings
import logging
import asyncio
import uvloop

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

app = FastAPI(
    title="SeaCraft智能分析app服务接口",
    version="1.5",
)

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    # 记录验证错误的详细信息
    logger.error(f"Request validation failed for {request.url.path}. Error: {exc.errors()}")
    # 返回标准的 422 错误响应
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )

@app.on_event("startup")
async def startup_event():
    ias_base_url = settings.SERVER
    await asyncio.sleep(3)
    if not ias_base_url:
        logger.warning("未设置IAS服务URL环境变量(SERVER)，无法向IAS服务注册")
        return
    if ias_base_url:
        ias_client = init_ias_client(ias_base_url)
        if ias_client.register():
            from .services.capacity_service import set_register_time
            set_register_time()
            # 启动保活线程
            ias_client.start_keepalive_thread()
    else:
        logger.error("向IAS服务注册失败")


@app.on_event("shutdown")
async def shutdown_event():
    ias_client = get_ias_client()
    if ias_client:
        ias_client.stop_keepalive_thread()
        ias_client.unregister()


app.include_router(tasks_router)
app.include_router(capacity_router)
app.include_router(loglevel_router)
app.include_router(version_router)
app.include_router(student_behavior_router)


