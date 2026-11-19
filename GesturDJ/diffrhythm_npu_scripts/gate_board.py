"""Board-side accuracy gate: load seg0..3 context binaries with dit_server, run the saved test case twice, save the output.

Run on the IQ8 (detached, as the notebook does):  python3 gate_board.py <ctx_dir> <out_file> [case_dir]
<case_dir> holds the input files (default "case", fp16 inputs; the int8 graphs have fp32 I/O and need a fp32 copy).
<ctx_dir> is one directory with seg0..3.bin, or four comma-separated directories (one per segment) to mix precisions.
Prints the load time and the per-pass time. The notebook pulls <out_file> and compares it with the fp32 PyTorch reference.
"""
import subprocess, sys, time, os
ctx, outfile = sys.argv[1:3]
case = sys.argv[3] if len(sys.argv) > 3 else "case"
CTX = ctx.split(",") * 4 if "," not in ctx else ctx.split(",")
R = "/root/diffrhythm/qnn_rt"
env = dict(os.environ, LD_LIBRARY_PATH=R + "/lib", ADSP_LIBRARY_PATH=R + "/lib/hexagon-v75/unsigned;/usr/lib/rfsa/adsp;/dsp")
cmd = ["./dit_server", R + "/lib/libQnnHtp.so", R + "/lib/libQnnSystem.so"] + [f"{c}/seg{i}.bin:seg{i}" for i, c in enumerate(CTX)]
t = time.time()
p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=open("server.err", "w"), env=env, cwd="/root/diffrhythm")
ins = []; out = None
while True:
    l = p.stdout.readline().decode().split()
    if not l: print("server died; see server.err"); sys.exit(1)
    if l[0] == "IN": ins.append((l[1], int(l[2])))
    elif l[0] == "OUT": out = (l[1], int(l[2]))
    elif l[0] == "READY": break
print("load %.1fs" % (time.time() - t))
data = b"".join(open("%s/%s.raw" % (case, n), "rb").read() for n, _ in ins)
assert len(data) == sum(s for _, s in ins)
for k in range(2):
    t = time.time(); p.stdin.write(data); p.stdin.flush(); v = p.stdout.read(out[1]); print("pass %d %.2fs" % (k, time.time() - t))
open(outfile, "wb").write(v); p.stdin.close()
