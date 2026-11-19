# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
setup_assets.py
---------------
Cython build script for compiling assets.pyx into a native .so extension.

Usage (during Docker build):
    python setup_assets.py build_ext --inplace

The resulting assets.cpython-3X-*.so file embeds the IP text assets
as compiled binary constants. The .pyx source and original .txt files
are NOT included in the final Docker image.
"""

from Cython.Build import cythonize
from setuptools import setup

setup(
    name="assets",
    ext_modules=cythonize(
        "assets.pyx",
        compiler_directives={
            "language_level": "3",
            "embedsignature": False,
            "optimize.use_switch": True,
        },
    ),
)
