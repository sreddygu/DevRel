"""
Local orchestration — shows which ops run on the Hexagon NPU vs CPU.
This is the client-side replacement for mcp orchestrate_workload when
the MCP server has no NPU (the common cloud-server + local-device setup).

Usage:
    .venv-arm64/Scripts/python.exe run_split.py <model.onnx>

Example:
    .venv-arm64/Scripts/python.exe run_split.py devrel_artifacts/mobilenetv2-12-static-qdq/mobilenetv2-12-static-qdq.onnx
"""
import sys

sys.path.insert(0, 'src')
from devrel_client import ort_qnn

if len(sys.argv) < 2:
    print("Usage: python run_split.py <model.onnx>")
    sys.exit(1)

model = sys.argv[1]
split = ort_qnn.provider_split(model)
s = split['summary']

print()
print('=' * 60)
print('  DevRel ORCHESTRATION - NPU vs CPU Layer Split')
print('=' * 60)
print('  Model     :', model)
print('  Total ops :', s['total_nodes'])
print('  On NPU    :', str(s['on_npu']) + '  (' + str(s['npu_percent']) + '%)')
print('  On CPU    :', str(s['on_cpu']) + '  (' + str(s['cpu_percent']) + '%)')
print('=' * 60)

npu_ops = [n for n, ep in split.items() if n != 'summary' and 'QNN' in ep]
cpu_ops = [n for n, ep in split.items() if n != 'summary' and 'CPU' in ep]

if npu_ops:
    print()
    print('NPU ops (' + str(len(npu_ops)) + '):')
    for n in npu_ops:
        print('  ', n)

if cpu_ops:
    print()
    print('CPU fallback ops (' + str(len(cpu_ops)) + '):')
    for n in cpu_ops:
        print('  ', n)

if s['npu_percent'] >= 90:
    print()
    print('  Result: Excellent -- model is fully NPU-accelerated.')
elif s['on_npu'] == 1 and s['on_cpu'] <= 3:
    print()
    print('  Result: Excellent -- entire model fused into 1 NPU subgraph.')
    print('  The', s['on_cpu'], 'CPU op(s) are intentional float/int boundary ops, not fallbacks.')
elif s['npu_percent'] >= 50:
    print()
    print('  Result: Partial NPU usage -- consider INT8 QDQ quantization.')
else:
    print()
    print('  Result: Mostly CPU -- convert to INT8 QDQ for full NPU utilisation.')
