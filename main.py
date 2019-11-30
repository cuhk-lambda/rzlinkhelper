#!/usr/bin/env python3
import sys
import os
import json
import works

import utils

console = utils.Console()


def main():
    if len(sys.argv) >= 2 and os.access(sys.argv[1], os.R_OK):
        console.log("Cmaker result found:", sys.argv[1])
    else:
        console.error("Cmaker result not found or unreadable.")
        sys.exit(1)

    try:
        json_data = json.load(open(sys.argv[1]))
        assert json_data["scripts"]
        assert json_data["compile"]
    except:
        console.error("Failed to parse Cmaker file")
        sys.exit(1)
    try:
        utils.loadSettings(open("settings.json"))
        console.success("Settings loaded.")
    except Exception as e:
        console.warn("Settings not loaded, because of:", e)
    console.debug("Settings", utils.settings)
    works.do_process(json_data)


if __name__ == "__main__":
    main()
