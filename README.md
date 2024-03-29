# rzlinkhelper

[![CircleCI](https://circleci.com/gh/cuhk-lambda/rzlinkhelper/tree/master.svg?style=svg)](https://circleci.com/gh/cuhk-lambda/rzlinkhelper/tree/master)

Reasonable link helper, good for you to analyze.

Features:

- [x] Works with [cmaker](https://github.com/SchrodingerZhu/cmaker) for CMake projects.
- [ ] Works with [libcallpass](https://github.com/cuhk-lambda/callgraph-generator) to show the function call statistics.


## Usage

``` shell
python3 main.py <JSON generated by cmaker>
```

or if the CLI is available on PyPi (not yet)

``` shell
pip install rzlinkhelper
rzlinkhelper <JSON generated by cmaker>
```

## Arguments

* `-c`, `--clean`: Clean compiling and linking results before building
* `--clean-linking`: Clean linking results before building

## Configurations

You can configure options on settings.json of your WORKDIR. Available options:
* `callpass_library_path`: Callpass library (libcallpass.so) path
* `object_dir`: Destination directory
* `debug`: Debug mode
* `original_cxx_executable`: Original CXX executable name 
* `original_cc_executable`: Original CC excutable name
* `targeted_cxx_executable`: CXX executable name
* `targeted_cc_executable`: CC executable name
* `llvm_link_executable`: LLVM linking executable name
* `preserve_process`: The file name for saving SHA-1 relationship for the sake of debugging. Disable this with an empty string.
* `toposort_verbose_logging_dir`: Log topo sort intermediate processes. Disable this with an empty string.


``` jsonc
{
    "callpass_library_path": "./libcallpass.so",
    "object_dir": "objects",
    "debug": false,
    "original_cxx_executable": "/usr/bin/c++",
    "original_cc_executable": "/usr/bin/cc",
    "targeted_cxx_executable": "/usr/bin/clang++",
    "targeted_cc_executable": "/usr/bin/clang",
    "llvm_link_executable": "/usr/bin/llvm-link",
    "preserve_process": "sha1.json",
    "toposort_verbose_logging_dir": ""
}
```
