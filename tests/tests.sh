#!/bin/bash

CMAKER_UPSTREAM="cuhk-lambda/cmaker"

git submodule init
git submodule update
mkdir dist
cd dist
sed -i 's/VERSION 3.15/VERSION 3.10/' ../repo/CMakeLists.txt  # Since we only have 3.10/3.13
cmake ../repo
remake -x 2>/dev/null >make.log
curl https://api.github.com/repos/$CMAKER_UPSTREAM/releases/latest | jq .assets_url | xargs curl | jq .[0].browser_download_url | xargs -IX -- curl X -L -o cmaker
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
