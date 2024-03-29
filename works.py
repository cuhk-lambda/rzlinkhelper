import subprocess
import sys
import utils
import os
import json
from multiprocessing import Pool, Manager
from os.path import realpath

console = utils.Console()

sha1Table = {}
dependencyList = {}


def single_compile(cmd, hashname, execname, r, totalLength, finishedList, clean=False):
    if clean and os.access(utils.GET("object_dir") + "/" + hashname, os.W_OK):
        console.info(
            "Found {}, cleaning before rebuild.".format(execname))
        os.unlink(utils.GET("object_dir") + "/" + hashname)
    if os.access(utils.GET("object_dir") + "/" + hashname, os.R_OK):
        console.info(
            "Found {}, skipping. [{}/{}]".format(execname, r + 1, totalLength))
    else:
        console.info("Compiling {} [{}/{}]".format(execname, r + 1, totalLength))
        console.debug(cmd)
        try:
            subprocess.run(cmd, shell=True,
                           stdout=subprocess.PIPE, check=True)
        except subprocess.CalledProcessError:
            console.error("Error compiling {}".format(execname))
            return False
    finishedList.append(hashname)
    return True


def single_linking(top, finishedList, clean=False):
    if utils.hasNoDependency(sha1Table[top]):
        console.debug(
            "{} ({}) has no dependency. Skipping.".format(sha1Table[top], top))
    elif os.access(utils.GET("object_dir") + "/" + top, os.R_OK):
        console.info("{} ({}) is found. Skipping.".format(sha1Table[top], top))
    else:
        deps = dependencyList[top]
        cmdline = utils.getllvmLinkCmd(
            realpath(utils.GET("object_dir") + "/" + top),
            list(map(lambda x: utils.GET("object_dir") + "/" + x, deps)))
        console.debug(cmdline)
        console.info("Waiting for prequisites of {} ({})...".format(sha1Table[top], top))
        files = deps.copy()
        while True:
            for i in files:
                if i in finishedList:
                    files.remove(i)
            if len(files) == 0:
                break
        console.info("Linking {} ({})".format(sha1Table[top], top))
        try:
            subprocess.run(cmdline, shell=True,
                           stdout=subprocess.PIPE, check=True)
        except subprocess.CalledProcessError:
            console.error("Error linking {} ({})".format(sha1Table[top], top))
            console.error("Related dependencies:")
            for i in deps:
                console.error("{} ({})".format(sha1Table[i], i))
                console.error("cmdline by original filenames: ",
                              utils.getllvmLinkCmd(realpath(utils.GET("object_dir") + "/" + sha1Table[top]),
                                                   list(map(lambda x: sha1Table[x], deps))))
            return False
    finishedList.append(top)
    return True


def console_error_and_exit(st):
    console.error(st)
    sys.exit(1)


def do_process(data, settings):
    # Preparing directories
    utils.checkDir(utils.GET("object_dir"), "Object")
    if utils.GET("toposort_verbose_logging_dir") is not None and utils.GET("toposort_verbose_logging_dir") != "":
        utils.checkDir(utils.GET("toposort_verbose_logging_dir"), "Toposort verbose logging")
    originalCXX = utils.GET("original_cxx_executable")
    originalCC = utils.GET("original_cc_executable")

    finishedList = Manager().list()

    totalLength = len(data["compile"])
    compileTaskPool = Pool()
    console.log("Compiling .o (total: {})".format(totalLength))
    for r in range(totalLength):
        i = data["compile"][r]
        execname = "(unknown)"
        cmdline = list(filter(lambda x: x != "", i.split(" ")))
        filehashpath = ["0" for i in range(0, 40)]
        for argnum in range(len(cmdline)):
            if cmdline[argnum] == originalCXX:
                cmdline[argnum] = utils.GET("targeted_cxx_executable")
                cmdline[argnum] += " -emit-llvm"
            elif cmdline[argnum] == originalCC:
                cmdline[argnum] = utils.GET("targeted_cc_executable")
                cmdline[argnum] += " -emit-llvm"
            elif cmdline[argnum] == "-o":
                filepath = realpath(cmdline[argnum + 1])
                filehashpath = utils.sha1sum(filepath)
                sha1Table[filehashpath] = filepath
                cmdline[argnum +
                        1] = realpath(utils.GET("object_dir") + "/" + filehashpath)
                execname = utils.findName(filepath)
            elif cmdline[argnum] == "-c":
                cmdline[argnum] = "-S"
            elif cmdline[argnum] == "-g":
                cmdline[argnum] = ""
        command = " ".join(cmdline)
        compileTaskPool.apply_async(
            single_compile, args=(command, filehashpath, execname, r, totalLength, finishedList, settings.clean),
            error_callback=console_error_and_exit)
    compileTaskPool.close()
    compileTaskPool.join()

    # Construct the graph
    console.success("All object files are compiled.")

    console.info("Preparing linking relationships")
    graphData = data["scripts"]

    for i in graphData:
        itemPath = i["target"]["abs_path"]
        hashedItemPath = utils.sha1sum(itemPath)
        sha1Table[hashedItemPath] = itemPath
        itemDependencies = i["target"]["dependencies"]
        dependencyList[hashedItemPath] = utils.deduplicate(utils.pathToSha1(itemDependencies, sha1Table))
        if hashedItemPath in dependencyList[hashedItemPath]:
            console.warn("Self-circle found. Ignoring.")
            dependencyList[hashedItemPath].remove(hashedItemPath)

    preserveProcess = utils.GET("preserve_process")
    if preserveProcess != None and preserveProcess != "":
        console.info("Saving metadata")
        sha1FilePath = utils.GET("object_dir") + "/" + preserveProcess
        try:
            json.dump(sha1Table, open(utils.GET("object_dir") + "/" + preserveProcess, "w"))
            console.success("Metadata saved.")
        except PermissionError:
            console.warn("Process file {} is not writable, while preseve_process is on.".format(sha1FilePath))

    console.info("Calculating linking sequence")
    try:
        currList = utils.topoSort(dependencyList, finishedList, sha1Table)
    except ValueError:
        console.error("Topo sort failed to complete. Please check your data.")
        sys.exit(1)
    console.success("Linking sequence calculated.")

    if settings.clean or settings.clean_linking:
        console.info("Cleaning linking targets")
        for i in dependencyList.keys():
            if os.access(utils.GET("object_dir") + "/" + i, os.W_OK):
                os.unlink(utils.GET("object_dir") + "/" + i)
        console.success("Linking targets cleaned.")

    if len(currList) != len(graphData):
        console.warn("Bad consistance on linking recipe")
    console.debug("Linking sequence:", currList, "or", list(map(lambda x: sha1Table[x], currList)))
    console.info("Start linking")
    ctrLen = len(currList)
    p = Pool()
    for idx, obj in enumerate(currList):
        console.info("Linking {} ({})  [{}/{}]".format(sha1Table[obj], obj, idx + 1, ctrLen))
        p.apply_async(single_linking, args=(obj, finishedList), error_callback=console_error_and_exit)
    p.close()
    p.join()
    console.success("All targets are linked.")
    console.success("Finished.")
