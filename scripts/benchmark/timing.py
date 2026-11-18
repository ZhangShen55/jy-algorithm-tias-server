"""仅用于独立诊断的 HTTP/模型时间线；默认入口不安装任何补丁。"""
from contextlib import contextmanager
from contextvars import ContextVar
import functools
import inspect
import itertools
import json
import logging
import math
import os
from pathlib import Path
import sys
import threading
import time
from urllib.parse import unquote

_current = ContextVar('vbas_benchmark_timing', default=None)
_paths = {'/AE/SyncTasks2', '/ImageDetect/student/v1.0.0', '/ImageDetect/teacher/v1.0.0'}


@contextmanager
def span(name, details=None):
    state = _current.get()
    if state is None:
        yield
        return
    start = time.perf_counter_ns()
    event = {'name': name, 'thread_id': threading.get_ident()}
    try:
        yield
    except BaseException as exc:
        event['error_type'] = type(exc).__name__
        raise
    finally:
        end = time.perf_counter_ns()
        event.update(start_ms=(start-state['started_monotonic_ns'])/1e6,
                     end_ms=(end-state['started_monotonic_ns'])/1e6, duration_ms=(end-start)/1e6)
        if details:
            event.update(details)
        state['spans'].append(event)


def timed(function, name):
    if inspect.iscoroutinefunction(function):
        @functools.wraps(function)
        async def wrapped(*args, **kwargs):
            with span(name):
                return await function(*args, **kwargs)
    else:
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            with span(name):
                return function(*args, **kwargs)
    return wrapped


class HTTPTiming:
    def __init__(self, app, output):
        self.app = app
        self.output = Path(output).open('x')
        self.sequence = itertools.count()
        self.lock = threading.Lock()
        self.restores = []
        self.failed_writes = 0

    def patch(self, owner, attribute, replacement):
        self.restores.append((owner, attribute, getattr(owner, attribute)))
        setattr(owner, attribute, replacement)

    def close(self):
        for owner, attribute, original in reversed(self.restores):
            setattr(owner, attribute, original)
        self.restores.clear()
        self.output.close()

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('path') not in _paths:
            return await self.app(scope, receive, send)
        headers = {k.lower(): v for k, v in scope.get('headers', [])}
        state = {'request_id': f'{os.getpid()}-{next(self.sequence)}', 'pid': os.getpid(),
                 'path': scope['path'], 'started_monotonic_ns': time.perf_counter_ns(),
                 'started_unix_time': time.time(), 'status': None, 'input_body_bytes': 0,
                 'response_body_bytes': 0, 'spans': [],
                 'client_sequence': headers.get(b'x-benchmark-sequence', b'').decode('latin1'),
                 'image_id': unquote(headers.get(b'x-benchmark-image-id', b'').decode('latin1'))}
        token = _current.set(state)
        async def traced_receive():
            with span('asgi_receive_await'):
                message = await receive()
            if message['type'] == 'http.request':
                state['input_body_bytes'] += len(message.get('body') or b'')
                if not message.get('more_body', False):
                    state['body_complete_ms'] = (time.perf_counter_ns()-state['started_monotonic_ns'])/1e6
            return message
        async def traced_send(message):
            if message['type'] == 'http.response.start':
                state['status'] = message['status']
            if message['type'] == 'http.response.body':
                state['response_body_bytes'] += len(message.get('body') or b'')
            with span('asgi_send_await'):
                await send(message)
        try:
            await self.app(scope, traced_receive, traced_send)
        except BaseException as exc:
            state['error_type'] = type(exc).__name__
            raise
        finally:
            state['total_asgi_ms'] = (time.perf_counter_ns()-state['started_monotonic_ns'])/1e6
            _current.reset(token)
            try:
                with self.lock:
                    self.output.write(json.dumps(state, ensure_ascii=False, allow_nan=False)+'\n')
                    self.output.flush()
            except (OSError, ValueError, TypeError):
                self.failed_writes += 1
                logging.getLogger(__name__).exception('Benchmark timing evidence write failed')


def install(app, output, models):
    """只在benchmark worker开启；不保存输入/输出张量，不增加CUDA同步。"""
    import base64
    import cv2
    import fastapi.dependencies.utils
    import fastapi.routing
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    tracer = HTTPTiming(app, output)
    try:
        for owner, attribute, name in [
            (Request, 'json', 'request_json_method_including_cached_body'),
            (fastapi.dependencies.utils, 'request_body_to_args', 'request_body_validation'),
            (fastapi.routing, 'serialize_response', 'response_validation_and_dump'),
            (JSONResponse, 'render', 'response_json_render'),
            (base64, 'b64decode', 'base64_decode'), (cv2, 'imdecode', 'image_decode'),
        ]:
            tracer.patch(owner, attribute, timed(getattr(owner, attribute), name))
        hooks = {
            'api.stu_tea_behavior': ['analyze_student_behavior_parallel', 'analyze_teacher_behavior_by_model'],
            'api.tasks': ['sync_tasks_data'],
            'services.student_behavior_service': ['mask_polygon', 'process_person_detection',
                                                  'process_face_detection', 'process_student_behavior'],
            'services.teacher_behavior_service': ['mask_polygon', 'collect_teacher_behavior_results'],
            'services.task_service_base64': ['mask_polygon', 'process_polygon'],
        }
        for module_name, attributes in hooks.items():
            module = sys.modules.get(module_name)
            if module is not None:
                for attribute in attributes:
                    original = getattr(module, attribute)
                    tracer.patch(module, attribute, timed(original, module_name+'.'+attribute))
        for name, model in models.items():
            original = model.predict
            @functools.wraps(original)
            def predict(*args, _original=original, _name=name, **kwargs):
                details = {'model': _name}
                with span('model_predict_wall_including_lock_wait', details):
                    results = _original(*args, **kwargs)
                    # 不消费stream生成器，也不保留Results或张量引用。
                    if _current.get() is not None and isinstance(results, (list, tuple)):
                        speeds = []
                        for result in results:
                            speed = getattr(result, 'speed', None)
                            if isinstance(speed, dict):
                                values = {}
                                for key in ['preprocess', 'inference', 'postprocess']:
                                    value = speed.get(key)
                                    if isinstance(value, (int, float)):
                                        values[key] = float(value) if math.isfinite(value) else None
                                speeds.append(values)
                        details['ultralytics_reported_speed_ms_not_pure_kernel_time'] = speeds
                    return results
            tracer.patch(model, 'predict', predict)
    except BaseException:
        tracer.close()
        raise
    return tracer
