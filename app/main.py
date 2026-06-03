# app/main.py
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from .api.tasks import router as tasks_router
from .api.capacity import router as capacity_router
from .api.loglevel import router as loglevel_router
from .api.version import router as version_router
from .api.stu_tea_behavior import router as student_behavior_router
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

app.include_router(tasks_router)
app.include_router(capacity_router)
app.include_router(loglevel_router)
app.include_router(version_router)
app.include_router(student_behavior_router)


