"""仅供 localhost 压测的入口；生产 main:app 不包含这些控制端点。"""
import os
import torch
from main import app


@app.post('/_benchmark/reset_peak', include_in_schema=False)
def reset_peak():
    torch.cuda.reset_peak_memory_stats(0)
    return {'reset': True}


@app.get('/_benchmark/memory', include_in_schema=False)
def memory():
    return {'allocated_bytes': torch.cuda.memory_allocated(0),
            'reserved_bytes': torch.cuda.memory_reserved(0),
            'peak_allocated_bytes': torch.cuda.max_memory_allocated(0),
            'peak_reserved_bytes': torch.cuda.max_memory_reserved(0),
            'scope': 'pytorch_allocator_not_total_cuda_or_tensorrt_memory'}


if os.environ.get('VBAS_BENCHMARK_TRACE_FILE'):
    from core import settings as cfg
    from scripts.benchmark.timing import install
    app = install(app, os.environ['VBAS_BENCHMARK_TRACE_FILE'], {
        name: getattr(cfg, name) for name in ['yolo_person_model', 'yolo_face_model',
                                            'yolo_student_model', 'yolo_teacher_behavior_model']})
