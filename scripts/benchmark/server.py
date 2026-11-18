"""仅供 localhost 压测的入口；生产 main:app 不包含这些控制端点。"""
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
