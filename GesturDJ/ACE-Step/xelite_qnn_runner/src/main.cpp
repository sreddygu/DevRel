#include <filesystem>
#include <iostream>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include <QairtCpp/QairtApi.hpp>
#include <QairtCpp/QairtInfo.hpp>
#include <QairtCpp/QairtLog.hpp>
#include <QairtCpp/System/Qairt.hpp>
#include <QairtCpp/System/QairtSystemApi.hpp>
#include <QairtCpp/System/QairtSystemBuilder.hpp>
#include <QairtCpp/System/QairtSystemDlc.hpp>
#include <QairtCpp/System/QairtSystemLog.hpp>

#include "qnn_low_level_probe.h"

namespace {

constexpr int kBlockCount = 24;

std::filesystem::path case_directory(const std::filesystem::path& case_root, int block_index) {
  const int divisor = block_index <= 7 ? 16 : 32;
  return case_root / ("block" + std::to_string(block_index) +
                      "_10s_fp32_attn_normalization_scaled_" + std::to_string(divisor));
}

std::filesystem::path dlc_path(const std::filesystem::path& case_directory, int block_index) {
  const int divisor = block_index <= 7 ? 16 : 32;
  const std::string stem = "block_fp32_attn_normalization_scaled_" + std::to_string(divisor);
  const std::vector<std::filesystem::path> candidates = {
      case_directory / (stem + "_preserve_layout.dlc"),
      case_directory / (stem + ".dlc"),
  };
  for (const auto& candidate : candidates) {
    if (std::filesystem::is_regular_file(candidate)) {
      return candidate;
    }
  }
  return candidates.front();
}

void require_regular_file(const std::filesystem::path& path) {
  if (!std::filesystem::is_regular_file(path)) {
    throw std::runtime_error("required file is missing: " + path.string());
  }
}

void validate_case(const std::filesystem::path& case_root, int block_index) {
  const auto case_path = case_directory(case_root, block_index);
  require_regular_file(case_path / "manifest.json");
  require_regular_file(case_path / "reference_output.npy");
  require_regular_file(case_path / "inputs.npz");
  require_regular_file(dlc_path(case_path, block_index));
}

std::filesystem::path parse_case_root(int argc, char* argv[]) {
  if (argc < 3 || std::string(argv[1]) != "--case-root") {
    throw std::runtime_error(
        "usage: ace_step_qnn_runner --case-root <data/iq8> [--load-contexts --qairt-system <QairtSystem.dll>]");
  }
  const std::filesystem::path case_root(argv[2]);
  if (!std::filesystem::is_directory(case_root)) {
    throw std::runtime_error("case root is not a directory: " + case_root.string());
  }
  return case_root;
}

struct Options {
  std::filesystem::path case_root;
  bool load_contexts = false;
  bool probe_qnn_low_level = false;
  bool compose_qnn_contexts = false;
  bool execute_block0 = false;
  bool execute_qualified_blocks = false;
  bool execute_real_blocks = false;
  bool serve_real_blocks = false;
  std::filesystem::path output;
  std::filesystem::path output_directory;
  std::filesystem::path transport_directory;
  std::filesystem::path qairt_system;
  std::filesystem::path qnn_backend;
  std::filesystem::path qnn_system;
};

Options parse_options(int argc, char* argv[]) {
  Options options{parse_case_root(argc, argv)};
  for (int index = 3; index < argc; ++index) {
    const std::string argument(argv[index]);
    if (argument == "--load-contexts") {
      options.load_contexts = true;
      continue;
    }
    if (argument == "--probe-qnn-low-level") {
      options.probe_qnn_low_level = true;
      continue;
    }
    if (argument == "--compose-qnn-contexts") {
      options.compose_qnn_contexts = true;
      continue;
    }
    if (argument == "--execute-block0") { options.execute_block0 = true; continue; }
    if (argument == "--execute-qualified-blocks") {
      options.execute_qualified_blocks = true;
      continue;
    }
    if (argument == "--execute-real-blocks") {
      options.execute_real_blocks = true;
      continue;
    }
    if (argument == "--serve-real-blocks") {
      options.serve_real_blocks = true;
      continue;
    }
    if (argument == "--output" && index + 1 < argc) { options.output = argv[++index]; continue; }
    if (argument == "--output-dir" && index + 1 < argc) {
      options.output_directory = argv[++index];
      continue;
    }
    if (argument == "--transport-dir" && index + 1 < argc) {
      options.transport_directory = argv[++index];
      continue;
    }
    if (argument == "--qairt-system" && index + 1 < argc) {
      options.qairt_system = argv[++index];
      continue;
    }
    if (argument == "--qnn-backend" && index + 1 < argc) {
      options.qnn_backend = argv[++index];
      continue;
    }
    if (argument == "--qnn-system" && index + 1 < argc) {
      options.qnn_system = argv[++index];
      continue;
    }
    throw std::runtime_error("unrecognized argument: " + argument);
  }
  if (options.load_contexts && options.qairt_system.empty()) {
    throw std::runtime_error("--load-contexts requires --qairt-system <QairtSystem.dll>");
  }
  if (!options.qairt_system.empty() && !std::filesystem::is_regular_file(options.qairt_system)) {
    throw std::runtime_error("QAIRT System library is missing: " + options.qairt_system.string());
  }
  if ((options.probe_qnn_low_level || options.compose_qnn_contexts ||
       options.execute_block0 || options.execute_qualified_blocks || options.execute_real_blocks ||
       options.serve_real_blocks) &&
      (options.qnn_backend.empty() || options.qnn_system.empty())) {
    throw std::runtime_error(
        "QNN execution requires --qnn-backend <QnnHtp.dll> and --qnn-system <QnnSystem.dll>");
  }
  for (const auto& library : {options.qnn_backend, options.qnn_system}) {
    if (!library.empty() && !std::filesystem::is_regular_file(library)) {
      throw std::runtime_error("QNN library is missing: " + library.string());
    }
  }
  if (options.execute_block0 && options.output.empty()) throw std::runtime_error("--execute-block0 requires --output <raw>");
  if ((options.execute_qualified_blocks || options.execute_real_blocks) && options.output_directory.empty()) {
    throw std::runtime_error("block execution requires --output-dir <directory>");
  }
  if (options.serve_real_blocks && options.transport_directory.empty()) {
    throw std::runtime_error("--serve-real-blocks requires --transport-dir <directory>");
  }
  return options;
}

template <typename Tensor>
void validate_tensor_count(const std::vector<Tensor>& tensors,
                           size_t expected_count,
                           const std::string& kind,
                           int block_index) {
  if (tensors.size() != expected_count) {
    throw std::runtime_error("block " + std::to_string(block_index) + " exposes " +
                             std::to_string(tensors.size()) + " " + kind + " tensors; expected " +
                             std::to_string(expected_count));
  }
}

struct LoadedBlock {
  std::shared_ptr<qairt::SystemDlc> dlc;
  std::unique_ptr<qairt::Qairt> runtime;
};

struct LoadedRunner {
  std::shared_ptr<qairt::SystemApi> system_api;
  std::shared_ptr<qairt::SystemLog> system_log;
  std::vector<LoadedBlock> blocks;
};

LoadedRunner load_contexts(const std::filesystem::path& case_root,
                           const std::filesystem::path& qairt_system) {
  LoadedRunner loaded;
  const std::string qairt_system_path = qairt_system.string();
  loaded.system_api = std::make_shared<qairt::SystemApi>(qairt_system_path.c_str());
  loaded.system_log = loaded.system_api->makeShared<qairt::SystemLog>(
      std::nullopt, qairt::LogLevel::Error);
  loaded.blocks.reserve(kBlockCount);

  for (int block_index = 0; block_index < kBlockCount; ++block_index) {
    const auto case_path = case_directory(case_root, block_index);
    auto dlc = loaded.system_api->makeShared<qairt::SystemDlc>(
        qairt::ApiTypeRef<qairt::SystemLog>(*loaded.system_log),
        dlc_path(case_path, block_index).string());
    auto builder = loaded.system_api->make<qairt::QairtSystemBuilder>();
    builder.setDlc(dlc).setBackendType(qairt::BackendType::Htp);

    std::string validation_error;
    if (!builder.validate(validation_error)) {
      throw std::runtime_error("block " + std::to_string(block_index) +
                               " QAIRT configuration failed: " + validation_error);
    }

    auto runtime = std::make_unique<qairt::Qairt>(builder.build());
    if (runtime->getNumGraphInfos() != 1) {
      throw std::runtime_error("block " + std::to_string(block_index) + " exposes " +
                               std::to_string(runtime->getNumGraphInfos()) + " graphs; expected 1");
    }
    auto& graph = runtime->getGraphInfoAt(0);
    validate_tensor_count(graph.getGraphInputs(), 9, "input", block_index);
    validate_tensor_count(graph.getGraphOutputs(), 1, "output", block_index);
    loaded.blocks.push_back({std::move(dlc), std::move(runtime)});
  }
  return loaded;
}

std::string json_escape(const std::string& value) {
  std::ostringstream escaped;
  for (const char character : value) {
    switch (character) {
      case '\\': escaped << "\\\\"; break;
      case '"': escaped << "\\\""; break;
      case '\n': escaped << "\\n"; break;
      case '\r': escaped << "\\r"; break;
      case '\t': escaped << "\\t"; break;
      default: escaped << character; break;
    }
  }
  return escaped.str();
}

}

int main(int argc, char* argv[]) {
  try {
    const auto options = parse_options(argc, argv);
    for (int block_index = 0; block_index < kBlockCount; ++block_index) {
      validate_case(options.case_root, block_index);
    }
    if (options.probe_qnn_low_level) {
      const auto probe = ace_step::probe_qnn_low_level(options.qnn_backend, options.qnn_system);
      std::cout << "{\"status\":\"qnn_low_level_probe_passed\",\"backend_api\":\""
                << probe.backend_api_major << "." << probe.backend_api_minor
                << "\",\"system_api\":\"" << probe.system_api_major << "."
                << probe.system_api_minor << "\",\"execution_enabled\":false}" << std::endl;
      return 0;
    }
    if (options.compose_qnn_contexts) {
      const auto contexts = ace_step::compose_qnn_contexts(
          options.case_root, options.qnn_backend, options.qnn_system);
      std::cout << "{\"status\":\"qnn_contexts_composed\",\"backend\":\"htp\",\"blocks\":"
                << contexts << ",\"execution_enabled\":false}" << std::endl;
      return 0;
    }
    if (options.execute_block0) {
      ace_step::execute_block0(options.case_root, options.qnn_backend, options.qnn_system, options.output);
      std::cout << "{\"status\":\"block0_executed\",\"output\":\"" << json_escape(options.output.string())
                << "\",\"execution_enabled\":true,\"scope\":\"single_saved_block\"}" << std::endl;
      return 0;
    }
    if (options.execute_qualified_blocks || options.execute_real_blocks) {
      const auto blocks = ace_step::execute_qualified_blocks(
          options.case_root, options.qnn_backend, options.qnn_system, options.output_directory,
          options.execute_real_blocks);
      std::cout << "{\"status\":\"" << (options.execute_real_blocks ? "real_blocks_executed" : "qualified_blocks_executed")
                << "\",\"backend\":\"htp\",\"blocks\":"
                << blocks << ",\"output_dir\":\"" << json_escape(options.output_directory.string())
                << "\",\"execution_enabled\":true,\"scope\":\""
                << (options.execute_real_blocks ? "live_108x6_saved_inputs" : "saved_block_inputs")
                << "\"}" << std::endl;
      return 0;
    }
    if (options.serve_real_blocks) {
      ace_step::serve_real_blocks(
          options.case_root, options.qnn_backend, options.qnn_system, options.transport_directory);
      return 0;
    }
    if (options.load_contexts) {
      const auto blocks = load_contexts(options.case_root, options.qairt_system);
      std::cout << "{\"status\":\"contexts_loaded\",\"backend\":\"htp\",\"blocks\":"
                << blocks.blocks.size() << ",\"execution_enabled\":false}" << std::endl;
      return 0;
    }
    std::cout << "{\"status\":\"preflight_passed\",\"blocks\":" << kBlockCount
              << ",\"case_root\":\"" << json_escape(options.case_root.string())
              << "\",\"execution_enabled\":false}" << std::endl;
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "{\"status\":\"preflight_failed\",\"error\":\"" << json_escape(error.what())
              << "\"}" << std::endl;
    return 2;
  }
}
