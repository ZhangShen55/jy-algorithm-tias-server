"""有界的客户端异常链；不保留异常对象、帧、请求或模型数据。"""


def exception_details(exc):
    nodes, seen = [], set()
    current, relation, stop = exc, 'raised', 'end'
    while current is not None:
        if id(current) in seen:
            stop = 'cycle'
            break
        if len(nodes) >= 8:
            stop = 'depth_limit'
            break
        seen.add(id(current))
        try:
            message = repr(current)
        except Exception as formatting_error:
            message = f'<repr failed: {type(formatting_error).__name__}>'
        node = {'type': f'{type(current).__module__}.{type(current).__qualname__}',
                'relation': relation, 'repr': message[:1000], 'repr_truncated': len(message) > 1000}
        if isinstance(current, OSError) and isinstance(current.errno, int):
            node['errno'] = current.errno
        nodes.append(node)
        if current.__cause__ is not None:
            current, relation = current.__cause__, 'cause'
        elif len(current.args) == 1 and isinstance(current.args[0], BaseException):
            # httpcore有时将下层异常作为参数包装，而不挂在__cause__上。
            current, relation = current.args[0], 'argument'
        elif not current.__suppress_context__:
            current, relation = current.__context__, 'context'
        else:
            current = None
    return {'error_type': nodes[0]['type'], 'error_chain': nodes,
            'error_chain_truncated': stop != 'end', 'error_chain_stop': stop,
            'os_errno_available': any('errno' in node for node in nodes)}
