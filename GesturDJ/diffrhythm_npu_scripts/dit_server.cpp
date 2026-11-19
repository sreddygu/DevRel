// dit_server: persistent DiffRhythm DiT runner for the IQ8 NPU (HTP v75).
//
// What it does
//   Loads several QNN HTP context binaries ONCE (the four 4-block segments seg0..seg3 of the DiT), keeps them resident,
//   and chains them per request, so a full 16-block pass costs about 9 s instead of paying the ~3 min graph prepare
//   for every launch. It talks to its parent over stdin/stdout; all logging goes to stderr.
//
// Build   (WSL, cross-compile for the board)   ./build_dit_server.sh      needs g++-aarch64-linux-gnu + QAIRT headers
// Run     (on the board, QNN runtime on LD_LIBRARY_PATH, ADSP_LIBRARY_PATH set to the v75 skel dir)
//           dit_server <libQnnHtp.so> <libQnnSystem.so> ctx/seg0.bin:seg0 ctx/seg1.bin:seg1 ctx/seg2.bin:seg2 ctx/seg3.bin:seg3
//         each positional argument is "<context binary path>:<label>"; the label is only used in log lines. The graph
//         name inside each binary is read from the binary itself (one graph per binary is assumed; the first is used).
//
// Wire protocol
//   1. Startup (stdout, text lines):   "IN <tensor name> <bytes>"   one per input of the FIRST segment, in the order
//                                      the requests must supply them
//                                      "OUT <tensor name> <bytes>"  the first output of the LAST segment
//                                      "READY"
//      Loading takes about 4-5 s; do not send anything before READY.
//   2. Per request: write the raw bytes of every IN tensor, concatenated in the printed order (stdin, no framing,
//      native dtypes: fp16 for x, cond, time, style_prompt, start_time; int32 for text). The server runs seg0..seg3 and
//      writes the raw bytes of the OUT tensor to stdout (fp16 v, [1,2048,64]). Closing stdin (EOF) ends the server.
//   3. Per request it also logs "pass <seconds>" to stderr.
//
// How segments are chained
//   Tensors are matched BY NAME through a pool of "latest value per name": a later segment's inputs are filled from the
//   pool (h, c, text_embed); when producer and consumer differ in float width (an fp32-I/O int8 graph next to an fp16 graph)
//   the tensor is converted at that boundary (cast_copy). An output named "h_out" is also stored as "h", because the next segment consumes the hidden
//   state as "h". Set QNN_CHAIN_OUTPUT and QNN_CHAIN_INPUT to override that
//   alias for a model with different tensor names. Sizes must match exactly (or
//   differ by the fp32/fp16 factor 2) or the server stops with a message naming
//   the tensor.
//
// Limits / assumptions
//   * Tensor shapes and dtypes come from the context binaries (via libQnnSystem), nothing is hard-coded here.
//   * Client buffers are plain memory (QNN_TENSORMEMTYPE_RAW), so each pass copies about 25 MB; that is small next to 9 s.
//   * On any QNN error it prints "FATAL <what> err=<code>" and exits 1. A hung NPU call cannot be recovered in-process;
//     the board has to be rebooted (see DIFFRHYTHM_IQ8.md).
//   * The system-context handles are intentionally never freed: the tensor name/dimension pointers we copied point into them.
#include <dlfcn.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <string>
#include <vector>
#include <chrono>
#include "QnnInterface.h"
#include "System/QnnSystemInterface.h"

static void die(const char* m, Qnn_ErrorHandle_t e = 0) { fprintf(stderr, "FATAL %s err=%lu\n", m, (unsigned long)e); exit(1); }

// Qnn_Tensor_t is a versioned union (v1 or v2); these helpers read the fields we need from either.
static const char* tname(Qnn_Tensor_t* t) { return t->version == QNN_TENSOR_VERSION_2 ? t->v2.name : t->v1.name; }
static uint32_t trank(Qnn_Tensor_t* t) { return t->version == QNN_TENSOR_VERSION_2 ? t->v2.rank : t->v1.rank; }
static uint32_t* tdims(Qnn_Tensor_t* t) { return t->version == QNN_TENSOR_VERSION_2 ? t->v2.dimensions : t->v1.dimensions; }
static Qnn_DataType_t tdt(Qnn_Tensor_t* t) { return t->version == QNN_TENSOR_VERSION_2 ? t->v2.dataType : t->v1.dataType; }
static void setbuf(Qnn_Tensor_t* t, void* p, uint32_t n) {
  if (t->version == QNN_TENSOR_VERSION_2) { t->v2.memType = QNN_TENSORMEMTYPE_RAW; t->v2.clientBuf.data = p; t->v2.clientBuf.dataSize = n; }
  else { t->v1.memType = QNN_TENSORMEMTYPE_RAW; t->v1.clientBuf.data = p; t->v1.clientBuf.dataSize = n; }
}
// Tensor size in bytes. The low byte of Qnn_DataType_t is the element width written as decimal digits
// (0x16 -> 16 bits, 0x32 -> 32 bits), so it is decoded digit by digit.
static size_t tbytes(Qnn_Tensor_t* t) {
  unsigned x = (unsigned)tdt(t) & 0xFF; unsigned bits = ((x >> 4) & 0xF) * 10 + (x & 0xF);
  size_t n = 1; for (uint32_t i = 0; i < trank(t); i++) n *= tdims(t)[i];
  return (n * bits + 7) / 8;
}

// One loaded segment: its context and graph handles, working copies of its tensor descriptors, and the byte buffers that
// back them.
struct Seg {
  std::string name; Qnn_ContextHandle_t ctx = nullptr; Qnn_GraphHandle_t graph = nullptr;
  std::vector<Qnn_Tensor_t> in, out;                 // working copies
  std::vector<std::vector<uint8_t>> inbuf, outbuf;
};

// Copy `src` into the input buffer `dst`. Segments built with different I/O widths can sit next to each other (the int8 graphs
// have fp32 I/O, the fp16 graphs fp16 I/O): if the sizes differ by exactly 2x the data is fp32<->fp16 converted. int32 tensors
// (text) never differ in size, so they are copied as they are.
static bool cast_copy(std::vector<uint8_t>& dst, const std::vector<uint8_t>& src) {
  if (src.size() == dst.size()) { memcpy(dst.data(), src.data(), dst.size()); return true; }
  if (src.size() == dst.size() * 2) {          // fp32 -> fp16
    const float* a = (const float*)src.data(); __fp16* b = (__fp16*)dst.data();
    for (size_t i = 0; i < dst.size() / 2; i++) b[i] = (__fp16)a[i];
    return true;
  }
  if (src.size() * 2 == dst.size()) {          // fp16 -> fp32
    const __fp16* a = (const __fp16*)src.data(); float* b = (float*)dst.data();
    for (size_t i = 0; i < src.size() / 2; i++) b[i] = (float)a[i];
    return true;
  }
  return false;
}

int main(int argc, char** argv) {
  if (argc < 4) die("usage");
  void* hb = dlopen(argv[1], RTLD_NOW | RTLD_GLOBAL); if (!hb) die(dlerror());
  void* hs = dlopen(argv[2], RTLD_NOW | RTLD_GLOBAL); if (!hs) die(dlerror());
  auto gp = (decltype(&QnnInterface_getProviders))dlsym(hb, "QnnInterface_getProviders");
  auto gs = (decltype(&QnnSystemInterface_getProviders))dlsym(hs, "QnnSystemInterface_getProviders");
  const QnnInterface_t** pv; uint32_t np;
  if (gp(&pv, &np)) die("getProviders");
  auto& q = pv[0]->QNN_INTERFACE_VER_NAME;
  const QnnSystemInterface_t** sv; uint32_t ns;
  if (gs(&sv, &ns)) die("sysGetProviders");
  auto& sq = sv[0]->QNN_SYSTEM_INTERFACE_VER_NAME;

  Qnn_BackendHandle_t bh; Qnn_ErrorHandle_t e;
  if ((e = q.backendCreate(nullptr, nullptr, &bh))) die("backendCreate", e);
  Qnn_DeviceHandle_t dh = nullptr;
  if (q.deviceCreate && (e = q.deviceCreate(nullptr, nullptr, &dh))) fprintf(stderr, "deviceCreate err=%lu (continuing)\n", (unsigned long)e);

  // Load every context. For each: read the binary, ask libQnnSystem for its graph/tensor metadata, create the context on
  // the device, retrieve the graph, and allocate one buffer per input/output tensor.
  std::vector<Seg> segs;
  auto t0 = std::chrono::steady_clock::now();
  for (int a = 3; a < argc; a++) {
    std::string spec = argv[a]; size_t c = spec.rfind(':');
    std::string path = spec.substr(0, c); Seg s; s.name = spec.substr(c + 1);
    FILE* f = fopen(path.c_str(), "rb"); if (!f) die(("open " + path).c_str());
    fseek(f, 0, SEEK_END); size_t sz = ftell(f); fseek(f, 0, SEEK_SET);
    std::vector<uint8_t> blob(sz); if (fread(blob.data(), 1, sz, f) != sz) die("read"); fclose(f);

    QnnSystemContext_Handle_t sh; if (sq.systemContextCreate(&sh)) die("sysCtxCreate");
    const QnnSystemContext_BinaryInfo_t* bi; Qnn_ContextBinarySize_t bis;
    if ((e = sq.systemContextGetBinaryInfo(sh, blob.data(), sz, &bi, &bis))) die("getBinaryInfo", e);
    QnnSystemContext_GraphInfo_t* gi = nullptr; uint32_t ng = 0;
    if (bi->version == QNN_SYSTEM_CONTEXT_BINARY_INFO_VERSION_1) { gi = bi->contextBinaryInfoV1.graphs; ng = bi->contextBinaryInfoV1.numGraphs; }
    else if (bi->version == QNN_SYSTEM_CONTEXT_BINARY_INFO_VERSION_2) { gi = bi->contextBinaryInfoV2.graphs; ng = bi->contextBinaryInfoV2.numGraphs; }
    else { gi = bi->contextBinaryInfoV3.graphs; ng = bi->contextBinaryInfoV3.numGraphs; }
    if (!ng) die("no graphs");
    uint32_t nin, nout; Qnn_Tensor_t *tin, *tout; const char* gname;
    auto& g0 = gi[0];
    if (g0.version == QNN_SYSTEM_CONTEXT_GRAPH_INFO_VERSION_1) { gname = g0.graphInfoV1.graphName; nin = g0.graphInfoV1.numGraphInputs; tin = g0.graphInfoV1.graphInputs; nout = g0.graphInfoV1.numGraphOutputs; tout = g0.graphInfoV1.graphOutputs; }
    else if (g0.version == QNN_SYSTEM_CONTEXT_GRAPH_INFO_VERSION_2) { gname = g0.graphInfoV2.graphName; nin = g0.graphInfoV2.numGraphInputs; tin = g0.graphInfoV2.graphInputs; nout = g0.graphInfoV2.numGraphOutputs; tout = g0.graphInfoV2.graphOutputs; }
    else { gname = g0.graphInfoV3.graphName; nin = g0.graphInfoV3.numGraphInputs; tin = g0.graphInfoV3.graphInputs; nout = g0.graphInfoV3.numGraphOutputs; tout = g0.graphInfoV3.graphOutputs; }
    // copy tensor descriptors (names/dims pointers stay valid: we deliberately never free the system ctx)
    for (uint32_t i = 0; i < nin; i++) s.in.push_back(tin[i]);
    for (uint32_t i = 0; i < nout; i++) s.out.push_back(tout[i]);

    if ((e = q.contextCreateFromBinary(bh, dh, nullptr, blob.data(), sz, &s.ctx, nullptr))) die("contextCreateFromBinary", e);
    if ((e = q.graphRetrieve(s.ctx, gname, &s.graph))) die("graphRetrieve", e);
    for (auto& t : s.in) { s.inbuf.emplace_back(tbytes(&t)); setbuf(&t, s.inbuf.back().data(), s.inbuf.back().size()); }
    for (auto& t : s.out) { s.outbuf.emplace_back(tbytes(&t)); setbuf(&t, s.outbuf.back().data(), s.outbuf.back().size()); }
    fprintf(stderr, "loaded %s graph=%s in=%u out=%u\n", s.name.c_str(), gname, nin, nout);
    for (auto& t : s.in) fprintf(stderr, "  in  %s dt=0x%x rank=%u bytes=%zu\n", tname(&t), (unsigned)tdt(&t), trank(&t), tbytes(&t));
    for (auto& t : s.out) fprintf(stderr, "  out %s dt=0x%x rank=%u bytes=%zu\n", tname(&t), (unsigned)tdt(&t), trank(&t), tbytes(&t));
    segs.push_back(std::move(s));
  }
  fprintf(stderr, "all contexts loaded in %.2fs\n", std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count());

  Seg& first = segs.front(); Seg& last = segs.back();
  for (size_t i = 0; i < first.in.size(); i++) printf("IN %s %zu\n", tname(&first.in[i]), first.inbuf[i].size());
  printf("OUT %s %zu\n", tname(&last.out[0]), last.outbuf[0].size());
  printf("READY\n"); fflush(stdout);

  // Serve loop. `pool` holds the latest value of every named tensor for the current request (see the chaining note above).
  std::map<std::string, std::vector<uint8_t>> pool;     // latest value per tensor name
  const char* chainOutput = getenv("QNN_CHAIN_OUTPUT");
  const char* chainInput = getenv("QNN_CHAIN_INPUT");
  if (!chainOutput) chainOutput = "h_out";
  if (!chainInput) chainInput = "h";
  fprintf(stderr, "chain alias %s -> %s\n", chainOutput, chainInput);
  while (true) {
    for (size_t i = 0; i < first.in.size(); i++) {
      size_t n = first.inbuf[i].size();
      if (fread(first.inbuf[i].data(), 1, n, stdin) != n) return 0;   // EOF -> clean exit
    }
    auto ts = std::chrono::steady_clock::now();
    pool.clear();
    for (size_t k = 0; k < segs.size(); k++) {
      Seg& s = segs[k];
      if (k) for (size_t i = 0; i < s.in.size(); i++) {
        auto it = pool.find(tname(&s.in[i]));
        if (it == pool.end() || !cast_copy(s.inbuf[i], it->second)) { fprintf(stderr, "missing/size mismatch input %s for %s\n", tname(&s.in[i]), s.name.c_str()); return 2; }
      } else for (size_t i = 0; i < s.in.size(); i++) pool[tname(&s.in[i])] = s.inbuf[i];
      if ((e = q.graphExecute(s.graph, s.in.data(), s.in.size(), s.out.data(), s.out.size(), nullptr, nullptr))) die("graphExecute", e);
      for (size_t i = 0; i < s.out.size(); i++) {
        std::string nm = tname(&s.out[i]); pool[nm] = s.outbuf[i];
        if (nm == chainOutput) pool[chainInput] = s.outbuf[i];
      }
    }
    fwrite(last.outbuf[0].data(), 1, last.outbuf[0].size(), stdout); fflush(stdout);
    fprintf(stderr, "pass %.3fs\n", std::chrono::duration<double>(std::chrono::steady_clock::now() - ts).count());
  }
}
