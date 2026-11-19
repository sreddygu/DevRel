"""
max_graph_demo.mojo

Demonstrates building and executing a MAX computation graph from Mojo.
Runs on the ARM CPU (or GPU if a MAX GPU backend is available).
This is the MAX path — it does not use the Genie/QNN stack.

Run:
  mojo run src/max_graph_demo.mojo
"""

from python import Python


fn run_matmul_demo() raises:
    var np = Python.import_module("numpy")
    var engine = Python.import_module("max.engine")
    var graph_mod = Python.import_module("max.graph")
    var dtype_mod = Python.import_module("max.dtype")

    var DType = dtype_mod.DType
    var Graph = graph_mod.Graph
    var TensorType = graph_mod.TensorType

    print("Building MAX matmul graph (4x4 float32)...")

    var input_types = Python.list()
    input_types.append(TensorType(DType.float32, shape=[4, 4]))
    input_types.append(TensorType(DType.float32, shape=[4, 4]))

    with Graph("matmul_demo", input_types=input_types) as g:
        var a = g.inputs[0]
        var b = g.inputs[1]
        var out = a.__matmul__(b)
        g.output(out)

    var session = engine.InferenceSession()
    var model = session.load(g)

    var A = np.eye(4, dtype=np.float32).__mul__(2.0)
    var B = np.ones([4, 4], dtype=np.float32)

    var result = model.execute(input0=A, input1=B)
    print("Result (2*I @ ones):")
    print(result[0])


fn run_elementwise_demo() raises:
    var np = Python.import_module("numpy")
    var engine = Python.import_module("max.engine")
    var graph_mod = Python.import_module("max.graph")
    var dtype_mod = Python.import_module("max.dtype")
    var ops = Python.import_module("max.graph.ops")

    var DType = dtype_mod.DType
    var Graph = graph_mod.Graph
    var TensorType = graph_mod.TensorType

    print("\nBuilding MAX elementwise ReLU graph (1x8 float32)...")

    var input_types = Python.list()
    input_types.append(TensorType(DType.float32, shape=[1, 8]))

    with Graph("relu_demo", input_types=input_types) as g:
        var x = g.inputs[0]
        var zero = ops.constant(
            np.zeros([1, 8], dtype=np.float32), DType.float32
        )
        var out = ops.max(x, zero)
        g.output(out)

    var session = engine.InferenceSession()
    var model = session.load(g)

    var X = np.array(
        [[-3.0, -1.5, 0.0, 0.5, 1.0, 2.5, -0.1, 4.0]], dtype=np.float32
    )
    var result = model.execute(input0=X)
    print("Input: ", X)
    print("ReLU:  ", result[0])


fn main() raises:
    run_matmul_demo()
    run_elementwise_demo()
    print("\nMAX graph demos complete.")
