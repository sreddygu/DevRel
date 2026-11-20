#include "qnn_low_level_probe.h"

#include <windows.h>

#include <stdexcept>
#include <string>
#include <vector>
#include <fstream>
#include <array>
#include <algorithm>
#include <chrono>
#include <thread>

#include <QnnInterface.h>
#include <System/QnnSystemInterface.h>

namespace ace_step {
namespace {

using GetBackendProviders = Qnn_ErrorHandle_t (*)(const QnnInterface_t***, uint32_t*);
using GetSystemProviders = Qnn_ErrorHandle_t (*)(const QnnSystemInterface_t***, uint32_t*);

class Library final {
 public:
  explicit Library(const std::filesystem::path& path) : handle_(LoadLibraryW(path.c_str())) {
    if (handle_ == nullptr) {
      throw std::runtime_error("could not load QNN library: " + path.string());
    }
  }

  ~Library() {
    if (handle_ != nullptr) {
      FreeLibrary(handle_);
    }
  }

  Library(const Library&) = delete;
  Library& operator=(const Library&) = delete;

  template <typename Function>
  Function symbol(const char* name) const {
    const auto result = reinterpret_cast<Function>(GetProcAddress(handle_, name));
    if (result == nullptr) {
      throw std::runtime_error(std::string("missing QNN symbol: ") + name);
    }
    return result;
  }

 private:
  HMODULE handle_;
};

}  // namespace

std::vector<unsigned char> read_raw(const std::filesystem::path& path) {
  std::ifstream file(path, std::ios::binary | std::ios::ate);
  if (!file) throw std::runtime_error("could not read raw input: " + path.string());
  const auto size = file.tellg();
  std::vector<unsigned char> bytes(static_cast<size_t>(size));
  file.seekg(0);
  file.read(reinterpret_cast<char*>(bytes.data()), size);
  if (!file) throw std::runtime_error("could not read complete raw input: " + path.string());
  return bytes;
}

void set_client_buffer(Qnn_Tensor_t& tensor, void* data, uint32_t size) {
  if (tensor.version == QNN_TENSOR_VERSION_1) {
    tensor.v1.clientBuf = {data, size};
    return;
  }
  if (tensor.version == QNN_TENSOR_VERSION_2) {
    tensor.v2.clientBuf = {data, size};
    return;
  }
  throw std::runtime_error("unsupported QNN tensor version");
}

const char* tensor_name(const Qnn_Tensor_t& tensor) {
  if (tensor.version == QNN_TENSOR_VERSION_1) return tensor.v1.name;
  if (tensor.version == QNN_TENSOR_VERSION_2) return tensor.v2.name;
  throw std::runtime_error("unsupported QNN tensor version");
}

QnnLowLevelProbeResult probe_qnn_low_level(const std::filesystem::path& backend_library,
                                           const std::filesystem::path& system_library) {
  Library backend(backend_library);
  Library system(system_library);

  const auto get_backend_providers = backend.symbol<GetBackendProviders>(
      "QnnInterface_getProviders");
  const QnnInterface_t** backend_providers = nullptr;
  uint32_t backend_count = 0;
  if (get_backend_providers(&backend_providers, &backend_count) != QNN_SUCCESS ||
      backend_providers == nullptr || backend_count == 0) {
    throw std::runtime_error("QNN backend did not return interface providers");
  }

  const QnnInterface_t* backend_interface = nullptr;
  for (uint32_t index = 0; index < backend_count; ++index) {
    const auto& candidate = backend_providers[index];
    if (candidate->apiVersion.coreApiVersion.major == QNN_API_VERSION_MAJOR &&
        candidate->apiVersion.coreApiVersion.minor >= QNN_API_VERSION_MINOR) {
      backend_interface = candidate;
      break;
    }
  }
  if (backend_interface == nullptr) {
    throw std::runtime_error("QNN backend has no compatible interface provider");
  }

  const auto get_system_providers = system.symbol<GetSystemProviders>(
      "QnnSystemInterface_getProviders");
  const QnnSystemInterface_t** system_providers = nullptr;
  uint32_t system_count = 0;
  if (get_system_providers(&system_providers, &system_count) != QNN_SUCCESS ||
      system_providers == nullptr || system_count == 0) {
    throw std::runtime_error("QNN system library did not return interface providers");
  }

  const QnnSystemInterface_t* system_interface = nullptr;
  for (uint32_t index = 0; index < system_count; ++index) {
    const auto& candidate = system_providers[index];
    if (candidate->systemApiVersion.major == QNN_SYSTEM_API_VERSION_MAJOR &&
        candidate->systemApiVersion.minor >= QNN_SYSTEM_API_VERSION_MINOR) {
      system_interface = candidate;
      break;
    }
  }
  if (system_interface == nullptr) {
    throw std::runtime_error("QNN system library has no compatible interface provider");
  }

  return {
      backend_interface->apiVersion.coreApiVersion.major,
      backend_interface->apiVersion.coreApiVersion.minor,
      system_interface->systemApiVersion.major,
      system_interface->systemApiVersion.minor,
  };
}

unsigned int compose_qnn_contexts(const std::filesystem::path& case_root,
                                  const std::filesystem::path& backend_library,
                                  const std::filesystem::path& system_library) {
  Library backend_library_handle(backend_library);
  Library system_library_handle(system_library);
  const auto get_backend_providers = backend_library_handle.symbol<GetBackendProviders>(
      "QnnInterface_getProviders");
  const auto get_system_providers = system_library_handle.symbol<GetSystemProviders>(
      "QnnSystemInterface_getProviders");

  const QnnInterface_t** backend_providers = nullptr;
  uint32_t backend_count = 0;
  if (get_backend_providers(&backend_providers, &backend_count) != QNN_SUCCESS || backend_count == 0) {
    throw std::runtime_error("QNN backend did not return interface providers");
  }
  const QnnInterface_t* qnn = backend_providers[0];

  const QnnSystemInterface_t** system_providers = nullptr;
  uint32_t system_count = 0;
  if (get_system_providers(&system_providers, &system_count) != QNN_SUCCESS || system_count == 0) {
    throw std::runtime_error("QNN system library did not return interface providers");
  }
  const QnnSystemInterface_t* system = system_providers[0];

  Qnn_BackendHandle_t backend = nullptr;
  if (qnn->QNN_INTERFACE_VER_NAME.backendCreate(nullptr, nullptr, &backend) != QNN_SUCCESS) {
    throw std::runtime_error("QNN HTP backendCreate failed");
  }

  struct Context final {
    Qnn_ContextHandle_t handle = nullptr;
    QnnSystemDlc_Handle_t dlc = nullptr;
    Qnn_GraphHandle_t graph = nullptr;
  };
  std::vector<Context> contexts;
  contexts.reserve(24);

  try {
    for (int block_index = 0; block_index < 24; ++block_index) {
      const int divisor = block_index <= 7 ? 16 : 32;
      const auto case_directory = case_root / ("block" + std::to_string(block_index) +
          "_10s_fp32_attn_normalization_scaled_" + std::to_string(divisor));
      const auto preserved = case_directory / ("block_fp32_attn_normalization_scaled_" +
          std::to_string(divisor) + "_preserve_layout.dlc");
      const auto base = case_directory / ("block_fp32_attn_normalization_scaled_" +
          std::to_string(divisor) + ".dlc");
      const auto dlc_path = std::filesystem::is_regular_file(preserved) ? preserved : base;

      Context context;
      if (qnn->QNN_INTERFACE_VER_NAME.contextCreate(backend, nullptr, nullptr, &context.handle) != QNN_SUCCESS) {
        throw std::runtime_error("QNN contextCreate failed for block " + std::to_string(block_index));
      }
      if (system->QNN_SYSTEM_INTERFACE_VER_NAME.systemDlcCreateFromFile(
              nullptr, dlc_path.string().c_str(), &context.dlc) != QNN_SUCCESS) {
        throw std::runtime_error("QNN systemDlcCreateFromFile failed for block " + std::to_string(block_index));
      }

      QnnSystemContext_GraphInfo_t* graph_infos = nullptr;
      uint32_t graph_count = 0;
      if (system->QNN_SYSTEM_INTERFACE_VER_NAME.systemDlcComposeGraphs(
              context.dlc, nullptr, 0, backend, context.handle, *qnn,
              QNN_SYSTEM_CONTEXT_GRAPH_INFO_VERSION_1, &graph_infos, &graph_count) != QNN_SUCCESS ||
          graph_count != 1 || graph_infos == nullptr ||
          graph_infos[0].graphInfoV1.numGraphInputs != 9 ||
          graph_infos[0].graphInfoV1.numGraphOutputs != 1) {
        throw std::runtime_error("QNN DLC graph contract failed for block " + std::to_string(block_index));
      }
      if (qnn->QNN_INTERFACE_VER_NAME.graphRetrieve(context.handle,
              graph_infos[0].graphInfoV1.graphName, &context.graph) != QNN_SUCCESS) {
        throw std::runtime_error("QNN graphRetrieve failed for block " + std::to_string(block_index));
      }
      for (uint32_t graph_index = 0; graph_index < graph_count; ++graph_index) {
        free(const_cast<char*>(graph_infos[graph_index].graphInfoV1.graphName));
        free(graph_infos[graph_index].graphInfoV1.graphInputs);
        free(graph_infos[graph_index].graphInfoV1.graphOutputs);
      }
      free(graph_infos);
      contexts.push_back(context);
    }
  } catch (...) {
    for (auto& context : contexts) {
      if (context.dlc != nullptr) system->QNN_SYSTEM_INTERFACE_VER_NAME.systemDlcFree(context.dlc);
      if (context.handle != nullptr) qnn->QNN_INTERFACE_VER_NAME.contextFree(context.handle, nullptr);
    }
    qnn->QNN_INTERFACE_VER_NAME.backendFree(backend);
    throw;
  }

  const unsigned int context_count = static_cast<unsigned int>(contexts.size());
  for (auto& context : contexts) {
    system->QNN_SYSTEM_INTERFACE_VER_NAME.systemDlcFree(context.dlc);
    qnn->QNN_INTERFACE_VER_NAME.contextFree(context.handle, nullptr);
  }
  qnn->QNN_INTERFACE_VER_NAME.backendFree(backend);
  return context_count;
}

void execute_block0(const std::filesystem::path& case_root,
                    const std::filesystem::path& backend_library,
                    const std::filesystem::path& system_library,
                    const std::filesystem::path& output_path) {
  Library backend_library_handle(backend_library);
  Library system_library_handle(system_library);
  const auto get_backend_providers = backend_library_handle.symbol<GetBackendProviders>("QnnInterface_getProviders");
  const auto get_system_providers = system_library_handle.symbol<GetSystemProviders>("QnnSystemInterface_getProviders");
  const QnnInterface_t** backend_providers = nullptr; uint32_t backend_count = 0;
  const QnnSystemInterface_t** system_providers = nullptr; uint32_t system_count = 0;
  if (get_backend_providers(&backend_providers, &backend_count) != QNN_SUCCESS || backend_count == 0 ||
      get_system_providers(&system_providers, &system_count) != QNN_SUCCESS || system_count == 0) {
    throw std::runtime_error("could not obtain QNN providers");
  }
  const auto* qnn = backend_providers[0]; const auto* system = system_providers[0];
  Qnn_BackendHandle_t backend = nullptr; Qnn_ContextHandle_t context = nullptr; QnnSystemDlc_Handle_t dlc = nullptr;
  QnnSystemContext_GraphInfo_t* graph_infos = nullptr;
  try {
    if (qnn->QNN_INTERFACE_VER_NAME.backendCreate(nullptr, nullptr, &backend) != QNN_SUCCESS ||
        qnn->QNN_INTERFACE_VER_NAME.contextCreate(backend, nullptr, nullptr, &context) != QNN_SUCCESS) throw std::runtime_error("could not create HTP backend/context");
    const auto case_dir = case_root / "block0_10s_fp32_attn_normalization_scaled_16";
    const auto dlc_path = case_dir / "block_fp32_attn_normalization_scaled_16.dlc";
    if (system->QNN_SYSTEM_INTERFACE_VER_NAME.systemDlcCreateFromFile(nullptr, dlc_path.string().c_str(), &dlc) != QNN_SUCCESS) throw std::runtime_error("could not load block-0 DLC");
    uint32_t graph_count = 0;
    if (system->QNN_SYSTEM_INTERFACE_VER_NAME.systemDlcComposeGraphs(dlc, nullptr, 0, backend, context, *qnn, QNN_SYSTEM_CONTEXT_GRAPH_INFO_VERSION_1, &graph_infos, &graph_count) != QNN_SUCCESS || graph_count != 1) throw std::runtime_error("could not compose block-0 graph");
    Qnn_GraphHandle_t graph = nullptr;
    auto& info = graph_infos[0].graphInfoV1;
    if (info.numGraphInputs != 9 || info.numGraphOutputs != 1 || qnn->QNN_INTERFACE_VER_NAME.graphRetrieve(context, info.graphName, &graph) != QNN_SUCCESS) throw std::runtime_error("invalid block-0 graph contract");
    if (qnn->QNN_INTERFACE_VER_NAME.graphFinalize(graph, nullptr, nullptr) != QNN_SUCCESS) throw std::runtime_error("could not finalize block-0 graph");
    const std::vector<std::string> names = {"hidden_states.raw","attention_mask.raw","encoder_hidden_states.raw","encoder_attention_mask.raw","temb.raw","self_cos.raw","self_sin.raw","cross_cos.raw","cross_sin.raw"};
    std::vector<std::vector<unsigned char>> buffers; buffers.reserve(names.size());
    std::vector<Qnn_Tensor_t> inputs(info.numGraphInputs);
    for (uint32_t index = 0; index < info.numGraphInputs; ++index) { buffers.push_back(read_raw(case_dir / "raw_inputs" / names[index])); inputs[index] = info.graphInputs[index]; set_client_buffer(inputs[index], buffers.back().data(), static_cast<uint32_t>(buffers.back().size())); }
    std::vector<unsigned char> output(1105920);
    Qnn_Tensor_t result = info.graphOutputs[0]; set_client_buffer(result, output.data(), static_cast<uint32_t>(output.size()));
    if (qnn->QNN_INTERFACE_VER_NAME.graphExecute(graph, inputs.data(), static_cast<uint32_t>(inputs.size()), &result, 1, nullptr, nullptr) != QNN_SUCCESS) throw std::runtime_error("block-0 graphExecute failed");
    std::ofstream file(output_path, std::ios::binary | std::ios::trunc); file.write(reinterpret_cast<const char*>(output.data()), static_cast<std::streamsize>(output.size())); if (!file) throw std::runtime_error("could not write block-0 output");
    free(const_cast<char*>(info.graphName)); free(info.graphInputs); free(info.graphOutputs); free(graph_infos); graph_infos = nullptr;
    system->QNN_SYSTEM_INTERFACE_VER_NAME.systemDlcFree(dlc); dlc = nullptr; qnn->QNN_INTERFACE_VER_NAME.contextFree(context, nullptr); context = nullptr; qnn->QNN_INTERFACE_VER_NAME.backendFree(backend); backend = nullptr;
  } catch (...) {
    if (graph_infos) { free(const_cast<char*>(graph_infos[0].graphInfoV1.graphName)); free(graph_infos[0].graphInfoV1.graphInputs); free(graph_infos[0].graphInfoV1.graphOutputs); free(graph_infos); }
    if (dlc) system->QNN_SYSTEM_INTERFACE_VER_NAME.systemDlcFree(dlc); if (context) qnn->QNN_INTERFACE_VER_NAME.contextFree(context, nullptr); if (backend) qnn->QNN_INTERFACE_VER_NAME.backendFree(backend); throw;
  }
}

unsigned int execute_qualified_blocks(const std::filesystem::path& case_root,
                                      const std::filesystem::path& backend_library,
                                      const std::filesystem::path& system_library,
                                      const std::filesystem::path& output_directory,
                                      bool use_real_shape_cases) {
  constexpr int block_count = 24;
  const std::array<std::string, 9> input_names = {
      "hidden_states.raw", "attention_mask.raw", "encoder_hidden_states.raw",
      "encoder_attention_mask.raw", "temb.raw", "self_cos.raw", "self_sin.raw",
      "cross_cos.raw", "cross_sin.raw"};

  struct LoadedBlock {
    Qnn_ContextHandle_t context = nullptr;
    QnnSystemDlc_Handle_t dlc = nullptr;
    Qnn_GraphHandle_t graph = nullptr;
    QnnSystemContext_GraphInfo_t* graph_infos = nullptr;
    uint32_t graph_count = 0;
    std::vector<Qnn_Tensor_t> inputs;
    Qnn_Tensor_t output{};
  };

  Library backend_library_handle(backend_library);
  Library system_library_handle(system_library);
  const auto get_backend_providers = backend_library_handle.symbol<GetBackendProviders>("QnnInterface_getProviders");
  const auto get_system_providers = system_library_handle.symbol<GetSystemProviders>("QnnSystemInterface_getProviders");
  const QnnInterface_t** backend_providers = nullptr;
  const QnnSystemInterface_t** system_providers = nullptr;
  uint32_t backend_count = 0;
  uint32_t system_count = 0;
  if (get_backend_providers(&backend_providers, &backend_count) != QNN_SUCCESS || backend_count == 0 ||
      get_system_providers(&system_providers, &system_count) != QNN_SUCCESS || system_count == 0) {
    throw std::runtime_error("could not obtain QNN providers");
  }

  const auto* qnn = backend_providers[0];
  const auto* system = system_providers[0];
  Qnn_BackendHandle_t backend = nullptr;
  std::vector<LoadedBlock> blocks;
  constexpr int max_resident_blocks = 8;
  blocks.reserve(max_resident_blocks);
  unsigned int executed_blocks = 0;
  std::filesystem::create_directories(output_directory);

  const auto release_blocks = [&]() {
    for (auto& block : blocks) {
      if (block.graph_infos != nullptr) {
        for (uint32_t graph_index = 0; graph_index < block.graph_count; ++graph_index) {
          free(const_cast<char*>(block.graph_infos[graph_index].graphInfoV1.graphName));
          free(block.graph_infos[graph_index].graphInfoV1.graphInputs);
          free(block.graph_infos[graph_index].graphInfoV1.graphOutputs);
        }
        free(block.graph_infos);
      }
      if (block.dlc != nullptr) system->QNN_SYSTEM_INTERFACE_VER_NAME.systemDlcFree(block.dlc);
      if (block.context != nullptr) qnn->QNN_INTERFACE_VER_NAME.contextFree(block.context, nullptr);
    }
    blocks.clear();
  };

  try {
    if (qnn->QNN_INTERFACE_VER_NAME.backendCreate(nullptr, nullptr, &backend) != QNN_SUCCESS) {
      throw std::runtime_error("could not create HTP backend");
    }

    for (int batch_start = 0; batch_start < block_count; batch_start += max_resident_blocks) {
      const int batch_end = std::min(block_count, batch_start + max_resident_blocks);
      for (int block_index = batch_start; block_index < batch_end; ++block_index) {
        const int divisor = use_real_shape_cases ? 128 : (block_index <= 7 ? 16 : 32);
        const auto case_directory = use_real_shape_cases
            ? case_root / ("real_block" + std::to_string(block_index) + "_108x6_scaled_128")
            : case_root / ("block" + std::to_string(block_index) +
                "_10s_fp32_attn_normalization_scaled_" + std::to_string(divisor));
        const auto stem = use_real_shape_cases
            ? "block_real_108x6_scaled_128"
            : "block_fp32_attn_normalization_scaled_" + std::to_string(divisor);
        const auto base_dlc = case_directory / (stem + ".dlc");
        const auto preserved_dlc = case_directory / (stem + "_preserve_layout.dlc");
        const auto dlc_path = std::filesystem::is_regular_file(preserved_dlc) ? preserved_dlc : base_dlc;
        LoadedBlock block;
        if (qnn->QNN_INTERFACE_VER_NAME.contextCreate(backend, nullptr, nullptr, &block.context) != QNN_SUCCESS) {
          throw std::runtime_error("could not create QNN context for block " + std::to_string(block_index));
        }
        if (system->QNN_SYSTEM_INTERFACE_VER_NAME.systemDlcCreateFromFile(
                nullptr, dlc_path.string().c_str(), &block.dlc) != QNN_SUCCESS) {
          qnn->QNN_INTERFACE_VER_NAME.contextFree(block.context, nullptr);
          throw std::runtime_error("could not load QNN DLC for block " + std::to_string(block_index));
        }
        QnnSystemContext_GraphInfo_t* graph_infos = nullptr;
        uint32_t graph_count = 0;
        const auto compose_result = system->QNN_SYSTEM_INTERFACE_VER_NAME.systemDlcComposeGraphs(
            block.dlc, nullptr, 0, backend, block.context, *qnn,
            QNN_SYSTEM_CONTEXT_GRAPH_INFO_VERSION_1, &graph_infos, &graph_count);
        if (compose_result != QNN_SUCCESS || graph_count != 1 || graph_infos == nullptr ||
            graph_infos[0].graphInfoV1.numGraphInputs != input_names.size() ||
            graph_infos[0].graphInfoV1.numGraphOutputs != 1) {
          throw std::runtime_error("QNN DLC graph contract failed for block " + std::to_string(block_index));
        }
        const auto& graph_info = graph_infos[0].graphInfoV1;
        if (qnn->QNN_INTERFACE_VER_NAME.graphRetrieve(block.context, graph_info.graphName, &block.graph) != QNN_SUCCESS ||
            qnn->QNN_INTERFACE_VER_NAME.graphFinalize(block.graph, nullptr, nullptr) != QNN_SUCCESS) {
          throw std::runtime_error("could not prepare QNN graph for block " + std::to_string(block_index));
        }
        block.inputs.assign(graph_info.graphInputs, graph_info.graphInputs + graph_info.numGraphInputs);
        block.output = graph_info.graphOutputs[0];
        block.graph_infos = graph_infos;
        block.graph_count = graph_count;
        blocks.push_back(std::move(block));
      }

      for (int block_index = batch_start; block_index < batch_end; ++block_index) {
        const int divisor = use_real_shape_cases ? 128 : (block_index <= 7 ? 16 : 32);
        const auto case_directory = use_real_shape_cases
            ? case_root / ("real_block" + std::to_string(block_index) + "_108x6_scaled_128")
            : case_root / ("block" + std::to_string(block_index) +
                "_10s_fp32_attn_normalization_scaled_" + std::to_string(divisor));
        auto& block = blocks[block_index - batch_start];
        std::vector<std::vector<unsigned char>> input_buffers(block.inputs.size());
        for (size_t input_index = 0; input_index < block.inputs.size(); ++input_index) {
          const char* name = tensor_name(block.inputs[input_index]);
          if (name == nullptr || std::find(input_names.begin(), input_names.end(),
              std::string(name) + ".raw") == input_names.end()) {
            throw std::runtime_error("unexpected input tensor name for block " + std::to_string(block_index));
          }
          input_buffers[input_index] = read_raw(case_directory / "raw_inputs" /
                                                (std::string(name) + ".raw"));
        }
        for (size_t input_index = 0; input_index < block.inputs.size(); ++input_index) {
          set_client_buffer(block.inputs[input_index], input_buffers[input_index].data(),
                            static_cast<uint32_t>(input_buffers[input_index].size()));
        }
        std::vector<unsigned char> output(input_buffers.front().size());
        Qnn_Tensor_t result = block.output;
        set_client_buffer(result, output.data(), static_cast<uint32_t>(output.size()));
        if (qnn->QNN_INTERFACE_VER_NAME.graphExecute(block.graph, block.inputs.data(),
                static_cast<uint32_t>(block.inputs.size()), &result, 1, nullptr, nullptr) != QNN_SUCCESS) {
          throw std::runtime_error("QNN graphExecute failed for block " + std::to_string(block_index));
        }
        const auto output_path = output_directory /
            ((use_real_shape_cases ? "real_block" : "block") + std::to_string(block_index) + "_hidden_states_out.raw");
        std::ofstream file(output_path, std::ios::binary | std::ios::trunc);
        file.write(reinterpret_cast<const char*>(output.data()), static_cast<std::streamsize>(output.size()));
        if (!file) throw std::runtime_error("could not write output: " + output_path.string());
        ++executed_blocks;
      }
      release_blocks();
    }
  } catch (...) {
    release_blocks();
    if (backend != nullptr) qnn->QNN_INTERFACE_VER_NAME.backendFree(backend);
    throw;
  }

  qnn->QNN_INTERFACE_VER_NAME.backendFree(backend);
  return executed_blocks;
}

void serve_real_blocks(const std::filesystem::path& case_root,
                       const std::filesystem::path& backend_library,
                       const std::filesystem::path& system_library,
                       const std::filesystem::path& transport_directory) {
  const std::array<std::string, 9> input_names = {
      "hidden_states", "attention_mask", "encoder_hidden_states",
      "encoder_attention_mask", "temb", "self_cos", "self_sin",
      "cross_cos", "cross_sin"};
  const auto requests_directory = transport_directory / "requests";
  std::filesystem::create_directories(requests_directory);
  Library backend_library_handle(backend_library);
  Library system_library_handle(system_library);
  const auto get_backend_providers = backend_library_handle.symbol<GetBackendProviders>("QnnInterface_getProviders");
  const auto get_system_providers = system_library_handle.symbol<GetSystemProviders>("QnnSystemInterface_getProviders");
  const QnnInterface_t** backend_providers = nullptr;
  const QnnSystemInterface_t** system_providers = nullptr;
  uint32_t backend_count = 0;
  uint32_t system_count = 0;
  if (get_backend_providers(&backend_providers, &backend_count) != QNN_SUCCESS || backend_count == 0 ||
      get_system_providers(&system_providers, &system_count) != QNN_SUCCESS || system_count == 0) {
    throw std::runtime_error("could not obtain QNN providers");
  }
  const auto* qnn = backend_providers[0];
  const auto* system = system_providers[0];
  Qnn_BackendHandle_t backend = nullptr;
  if (qnn->QNN_INTERFACE_VER_NAME.backendCreate(nullptr, nullptr, &backend) != QNN_SUCCESS) {
    throw std::runtime_error("could not create HTP backend");
  }
  std::ofstream(transport_directory / "server.ready", std::ios::trunc) << "ready\n";

  const auto release_graph_info = [](QnnSystemContext_GraphInfo_t* graph_infos, uint32_t graph_count) {
    if (graph_infos == nullptr) return;
    for (uint32_t graph_index = 0; graph_index < graph_count; ++graph_index) {
      free(const_cast<char*>(graph_infos[graph_index].graphInfoV1.graphName));
      free(graph_infos[graph_index].graphInfoV1.graphInputs);
      free(graph_infos[graph_index].graphInfoV1.graphOutputs);
    }
    free(graph_infos);
  };

  try {
    while (!std::filesystem::exists(transport_directory / "shutdown")) {
      for (const auto& entry : std::filesystem::directory_iterator(requests_directory)) {
        if (!entry.is_directory()) continue;
        const auto request_directory = entry.path();
        if (!std::filesystem::exists(request_directory / "ready") ||
            std::filesystem::exists(request_directory / "done")) continue;
        std::ofstream(request_directory / "processing", std::ios::trunc) << "processing\n";
        try {
          std::ifstream index_file(request_directory / "block_index.txt");
          int block_index = -1;
          index_file >> block_index;
          if (!index_file || block_index < 0 || block_index >= 24) {
            throw std::runtime_error("request has an invalid block index");
          }
          const auto case_directory = case_root / ("real_block" + std::to_string(block_index) + "_108x6_scaled_128");
          const auto dlc_path = case_directory / "block_real_108x6_scaled_128_preserve_layout.dlc";
          Qnn_ContextHandle_t context = nullptr;
          QnnSystemDlc_Handle_t dlc = nullptr;
          QnnSystemContext_GraphInfo_t* graph_infos = nullptr;
          uint32_t graph_count = 0;
          try {
            if (qnn->QNN_INTERFACE_VER_NAME.contextCreate(backend, nullptr, nullptr, &context) != QNN_SUCCESS ||
                system->QNN_SYSTEM_INTERFACE_VER_NAME.systemDlcCreateFromFile(
                    nullptr, dlc_path.string().c_str(), &dlc) != QNN_SUCCESS) {
              throw std::runtime_error("could not create QNN request context");
            }
            const auto compose_result = system->QNN_SYSTEM_INTERFACE_VER_NAME.systemDlcComposeGraphs(
                dlc, nullptr, 0, backend, context, *qnn, QNN_SYSTEM_CONTEXT_GRAPH_INFO_VERSION_1,
                &graph_infos, &graph_count);
            if (compose_result != QNN_SUCCESS || graph_count != 1 || graph_infos == nullptr ||
                graph_infos[0].graphInfoV1.numGraphInputs != input_names.size() ||
                graph_infos[0].graphInfoV1.numGraphOutputs != 1) {
              throw std::runtime_error("QNN request graph contract failed");
            }
            const auto& graph_info = graph_infos[0].graphInfoV1;
            Qnn_GraphHandle_t graph = nullptr;
            if (qnn->QNN_INTERFACE_VER_NAME.graphRetrieve(context, graph_info.graphName, &graph) != QNN_SUCCESS ||
                qnn->QNN_INTERFACE_VER_NAME.graphFinalize(graph, nullptr, nullptr) != QNN_SUCCESS) {
              throw std::runtime_error("could not prepare QNN request graph");
            }
            std::vector<Qnn_Tensor_t> inputs(graph_info.graphInputs,
                                              graph_info.graphInputs + graph_info.numGraphInputs);
            std::vector<std::vector<unsigned char>> input_buffers(inputs.size());
            size_t output_size = 0;
            for (size_t input_index = 0; input_index < inputs.size(); ++input_index) {
              const char* name = tensor_name(inputs[input_index]);
              if (name == nullptr || std::find(input_names.begin(), input_names.end(), name) == input_names.end()) {
                throw std::runtime_error("request graph has an unexpected input tensor");
              }
              input_buffers[input_index] = read_raw(request_directory / "inputs" / (std::string(name) + ".raw"));
              if (std::string(name) == "hidden_states") output_size = input_buffers[input_index].size();
              set_client_buffer(inputs[input_index], input_buffers[input_index].data(),
                                static_cast<uint32_t>(input_buffers[input_index].size()));
            }
            if (output_size == 0) throw std::runtime_error("request is missing hidden_states");
            std::vector<unsigned char> output(output_size);
            Qnn_Tensor_t result = graph_info.graphOutputs[0];
            set_client_buffer(result, output.data(), static_cast<uint32_t>(output.size()));
            if (qnn->QNN_INTERFACE_VER_NAME.graphExecute(graph, inputs.data(), static_cast<uint32_t>(inputs.size()),
                    &result, 1, nullptr, nullptr) != QNN_SUCCESS) {
              throw std::runtime_error("QNN request graphExecute failed");
            }
            std::filesystem::create_directories(request_directory / "output");
            std::ofstream output_file(request_directory / "output" / "hidden_states_out.raw", std::ios::binary | std::ios::trunc);
            output_file.write(reinterpret_cast<const char*>(output.data()), static_cast<std::streamsize>(output.size()));
            if (!output_file) throw std::runtime_error("could not write request output");
          } catch (...) {
            release_graph_info(graph_infos, graph_count);
            if (dlc != nullptr) system->QNN_SYSTEM_INTERFACE_VER_NAME.systemDlcFree(dlc);
            if (context != nullptr) qnn->QNN_INTERFACE_VER_NAME.contextFree(context, nullptr);
            throw;
          }
          release_graph_info(graph_infos, graph_count);
          system->QNN_SYSTEM_INTERFACE_VER_NAME.systemDlcFree(dlc);
          qnn->QNN_INTERFACE_VER_NAME.contextFree(context, nullptr);
          std::ofstream(request_directory / "done", std::ios::trunc) << "ok\n";
        } catch (const std::exception& error) {
          std::ofstream(request_directory / "error.txt", std::ios::trunc) << error.what() << "\n";
          std::ofstream(request_directory / "done", std::ios::trunc) << "error\n";
        }
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
  } catch (...) {
    qnn->QNN_INTERFACE_VER_NAME.backendFree(backend);
    throw;
  }
  qnn->QNN_INTERFACE_VER_NAME.backendFree(backend);
}

}  // namespace ace_step
