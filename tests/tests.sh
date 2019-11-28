#!/bin/bash
git submodule init
git submodule update
mkdir dist
cd dist
sed -i 's/VERSION 3.15/VERSION 3.10/' ../repo/CMakeLists.txt 
cmake ../repo
remake -x 2>/dev/null >make.log
wget https://github.com/SchrodingerZhu/cmaker/releases/download/1.1/cmaker -O cmaker
chmod +x cmaker
./cmaker -t make.log -o output.log -w $(realpath .)
cat > settings.json <<EOF
{
    "callpass_library_path": "./libcallpass.so",
    "object_dir": "objects",
    "target_dir": "targets",
    "debug": true,
    "original_cxx_executable": "/usr/bin/c++",
    "original_cc_executable": "/usr/bin/cc",
    "targeted_cxx_executable": "/usr/bin/clang++-7",
    "targeted_cc_executable": "/usr/bin/clang",
    "llvm_link_executable": "/usr/bin/llvm-link-7"
}
EOF
python3 ../../main.py output.log