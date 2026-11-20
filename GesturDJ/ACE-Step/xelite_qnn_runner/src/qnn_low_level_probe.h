#pragma once

#include <filesystem>

namespace ace_step {

struct QnnLowLevelProbeResult {
  unsigned int backend_api_major;
  unsigned int backend_api_minor;
  unsigned int system_api_major;
  unsigned int system_api_minor;
};

QnnLowLevelProbeResult probe_qnn_low_level(const std::filesystem::path& backend_library,
                                           const std::filesystem::path& system_library);

unsigned int compose_qnn_contexts(const std::filesystem::path& case_root,
                                  const std::filesystem::path& backend_library,
                                  const std::filesystem::path& system_library);

void execute_block0(const std::filesystem::path& case_root,
                    const std::filesystem::path& backend_library,
                    const std::filesystem::path& system_library,
                    const std::filesystem::path& output_path);

unsigned int execute_qualified_blocks(const std::filesystem::path& case_root,
                                      const std::filesystem::path& backend_library,
                                      const std::filesystem::path& system_library,
                                      const std::filesystem::path& output_directory,
                                      bool use_real_shape_cases);

void serve_real_blocks(const std::filesystem::path& case_root,
                       const std::filesystem::path& backend_library,
                       const std::filesystem::path& system_library,
                       const std::filesystem::path& transport_directory);

}  // namespace ace_step
