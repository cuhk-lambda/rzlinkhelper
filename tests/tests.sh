#!/bin/bash
git submodule init
git submodule update
mkdir dist
cd dist
cmake ../repo
make --trace 2>/dev/null 1>make.log
wget https://github.com/SchrodingerZhu/cmaker/releases/download/1.1/cmaker -O cmaker
chmod +x cmaker
./cmaker -t make.log -o output.log -w $(realpath .)
python3 ../../main.py output.log
