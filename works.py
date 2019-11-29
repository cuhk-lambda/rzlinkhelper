import subprocess
import sys
import utils
import os
import json
from multiprocessing import Pool, Lock, Queue
from queue import Empty
from os.path import realpath
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

console = utils.Console()

sha1Table = {}
lock_countEdit = defaultdict(Lock)
globalStop = False
dependencyList = {}
dependentList = defaultdict(list)
finalDepList = []
finalDepListEditLock = Lock()
linkingProcPool = ProcessPoolExecutor()
linkingTaskQueue = Queue()


def single_compile(cmd, hashname, execname, r, totalLength):
    if (os.access(utils.GET("object_dir") + "/" + hashname, os.R_OK)):
        console.info(
            "Found {}, skipping. [{}/{}]".format(execname, r + 1, totalLength))
        return True
    else:
        console.info("Compiling {} [{}/{}]".format(execname, r + 1, totalLength))
        console.debug(cmd)
    try:
        subprocess.run(cmd, shell=True,
                       stdout=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError:
        console.error("Error compiling {}".format(execname))
        return False
    return True


def single_linking(top):
    if utils.hasNoDependency(sha1Table[top]):
        console.debug(
            "{} ({}) has no dependency. Skipping.".format(sha1Table[top], top))
    else:
        deps = dependencyList[top]["dependencies"]
        cmdline = utils.getllvmLinkCmd(
            realpath(utils.GET("object_dir") + "/" + top), list(map(lambda x: utils.GET("object_dir") + "/" + x, deps)))
        console.debug(cmdline)
        console.info("Linking {} ({})".format(sha1Table[top], top))
        if (os.access(utils.GET("object_dir") + "/" + top, os.R_OK)):
            console.info("{} ({}) is found. Skipping.".format(sha1Table[top], top))
        else:
            console.debug("{} ({}) is not found. Linking.".format(sha1Table[top], top))
            try:
                subprocess.run(cmdline, shell=True,
                               stdout=subprocess.PIPE, check=True)
            except subprocess.CalledProcessError:
                console.error("Error linking {} ({})".format(sha1Table[top], top))
                console.error("Related dependcies:")
                for i in deps:
                    console.error("{} ({})".format(sha1Table[i], i))
                    console.error("cmdline by original filenames: ",
                                  utils.getllvmLinkCmd(realpath(utils.GET("object_dir") + "/" + sha1Table[top]),
                                                       list(map(lambda x: sha1Table[x], deps))))
                return False
    finalDepListEditLock.acquire()
    finalDepList.append(top)
    finalDepListEditLock.release()
    updateDepQueue(top)
    return True


def updateDepQueue(top, asyncio=True):
    for i in dependentList[top]:
        if asyncio:
            lock_countEdit[i].acquire()
        dependencyList[i]["pendingDepCount"] -= 1
        if asyncio:
            lock_countEdit[i].release()
        if dependencyList[i]["pendingDepCount"] == 0:
            console.debug("Pushing {} ({}) into linking queue".format(sha1Table[i], i))
            linkingTaskQueue.put(i)


def console_error_and_exit(st):
    console.error(st)
    sys.exit(1)


def do_process(data):
    # Preparing directories
    utils.checkDir(utils.GET("object_dir"), "Object")
    originalCXX = utils.GET("original_cxx_executable")
    originalCC = utils.GET("original_cc_executable")

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
            single_compile, args=(command, filehashpath, execname, r, totalLength),
            error_callback=console_error_and_exit)
        finalDepList.append(filehashpath)
    compileTaskPool.close()
    compileTaskPool.join()

    # Construct the graph
    console.success("All object files are compiled.")
    console.info("Linking files")
    graphData = data["scripts"]

    asPath = set()
    for i in graphData:
        asPath.add(utils.sha1sum(i["target"]["abs_path"]))
    for i in finalDepList:
        asPath.add(i)

    for i in graphData:
        # Initial data
        itemPath = i["target"]["abs_path"]
        hashedItemPath = utils.sha1sum(itemPath)
        sha1Table[hashedItemPath] = itemPath
        itemDependencies = i["target"]["dependencies"]
        itemType = i["target"]["target_type"]
        dependencyList[hashedItemPath] = {
            "path": itemPath,
            "hashed": hashedItemPath,
            "dependencies": utils.deduplicate(utils.pathToSha1(itemDependencies, sha1Table)),
            "type": itemType
        }
        dependencyList[hashedItemPath]["pendingDepCount"] = 0
        for j in dependencyList[hashedItemPath]["dependencies"]:
            if j in asPath:
                dependencyList[hashedItemPath]["pendingDepCount"] += 1
            dependentList[j].append(hashedItemPath)
        if dependencyList[hashedItemPath]["pendingDepCount"] == 0:
            console.warn("Pushing {} ({}) unnaturally into linking queue".format(itemPath, hashedItemPath))
            linkingTaskQueue.put(hashedItemPath)

    for i in finalDepList:
        updateDepQueue(i, asyncio=False)

    ctr = len(graphData)
    ctrAll = ctr
    p = Pool()
    while ctr > 0:
            top = None
            try:
             top = linkingTaskQueue.get_nowait()
            except Empty:
               for s in graphData:
                 i = utils.sha1sum(s["target"]["abs_path"])
                 if i not in finalDepList and dependencyList[i]["pendingDepCount"] == 0:
                    console.debug("Successfully recovered from an empty queue")
                    updateDepQueue(i)
                    finalDepList.append(i)
               continue
            ctr -= 1
            console.info("Link in progress: [{}/{}]".format(ctrAll - ctr, ctrAll))
            p.apply_async(single_linking, args=(top,), error_callback=console_error_and_exit)
    p.close()
    p.join()

    console.success("All targets are linked.")
    console.info("Renaming")
    preserveProcess = utils.GET("preserve_process")
    for sha1str in os.listdir(utils.GET("object_dir")):
        if sha1str in sha1Table:
            os.rename(utils.GET("object_dir") + "/" + sha1str,
                      utils.GET("object_dir") + "/" + utils.findName(sha1Table[sha1str]))
    if preserveProcess != None and preserveProcess != "":
        sha1FilePath = utils.GET("object_dir") + "/" + preserveProcess
        try:
            json.dump(sha1Table, open(utils.GET("object_dir") + "/" + preserveProcess, "w"))
        except PermissionError:
            console.warn("Process file {} is not writable, while preseve_process is on.".format(sha1FilePath))

    console.success("Finished.")
