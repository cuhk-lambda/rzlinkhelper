import subprocess
import sys
import utils
import os
from multiprocessing import Pool, Lock, Queue
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
linkingProcPool = ProcessPoolExecutor()
linkingTaskQueue = Queue()


def single_compile(cmd, hashname, execname, r, totalLength):
  if (os.access(utils.GET("object_dir") + "/" + hashname, os.R_OK)):
    console.info(
        "Found {}, skipping. [{}/{}]".format(execname, r+1, totalLength))
    return True
  else:
    console.info("Compiling {} [{}/{}]".format(execname, r+1, totalLength))
    console.debug(cmd)
  try:
    subprocess.run(cmd, shell=True,
                   stdout=subprocess.PIPE, check=True)
  except subprocess.CalledProcessError:
    console.error("Error compiling {}".format(execname))
    sys.exit(2)
    return False
  return True


def single_linking(top):
  print(top)
  if utils.hasNoDependency(sha1Table[top]):
    console.debug(
        "{} ({}) has no dependency. Skipping.".format(sha1Table[top], top))
  else:
    console.debug(
        "{} ({}) has some dependencies.".format(sha1Table[top], top))
    deps = dependencyList[top]["dependencies"]
    cmdline = utils.getllvmLinkCmd(
        realpath(utils.GET("object_dir") + "/" + top), list(map(lambda x: utils.GET("object_dir") + "/" + x, deps)))
    console.debug(cmdline)
    console.info("Linking " + top)
    if (os.access(utils.GET("object_dir") + "/" + top, os.R_OK)):
      console.info("{} found. Skipping".format(top))
    else:
      try:
        subprocess.run(cmdline, shell=True,
                       stdout=subprocess.PIPE, check=True)
      except subprocess.CalledProcessError:
        console.error("Error linking {}".format(top))
        console.error("Related dependcies:")
        for i in deps:
          console.error("{} ({})".format(sha1Table[i], i))
          console.error("cmdline by original filenames: ",
                        utils.getllvmLinkCmd(realpath(utils.GET("object_dir") + "/" + sha1Table[top]),
                                             list(map(lambda x: sha1Table[x], deps))))
        sys.exit(2)
        return False
  finalDepList.append(top)
  for i in dependentList[top]:
    lock_countEdit[i].acquire()
    dependencyList[i]["pendingDepCount"] -= 1
    print(i, "depcnt: ", dependencyList[i]["pendingDepCount"], list(
        map(lambda x: sha1Table[x], dependencyList[i]["dependencies"])))
    lock_countEdit[i].release()
    if dependencyList[i]["pendingDepCount"] <= 1:
      print("Pushing", i)
      linkingTaskQueue.put(i)
  return True


def do_process(data):
  # Preparing directories
  utils.checkDir(utils.GET("object_dir"), "Object")
  utils.checkDir(utils.GET("target_dir"), "Target")
  originalCXX = utils.GET("original_cxx_executable")
  originalCC = utils.GET("original_cc_executable")

  totalLength = len(data["compile"])
  compileTaskPool = Pool()
  console.log("Compiling .o (total: {})".format(totalLength))
  for r in range(totalLength):
    i = data["compile"][r]
    execname = "(unknown)"
    cmdline = list(filter(lambda x: x != "", i.split(" ")))
    for argnum in range(len(cmdline)):
      if cmdline[argnum] == originalCXX:
        cmdline[argnum] = utils.GET("targeted_cxx_executable")
        cmdline[argnum] += " -emit-llvm"
      elif cmdline[argnum] == originalCC:
        cmdline[argnum] = utils.GET("targeted_cc_executable")
        cmdline[argnum] += " -emit-llvm"
      elif cmdline[argnum] == "-o":
        filepath = realpath(cmdline[argnum+1])
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
        single_compile, args=(command, filehashpath, execname, r, totalLength), error_callback=console.error)
    finalDepList.append(filehashpath)
  compileTaskPool.close()
  compileTaskPool.join()

  # Construct the graph
  console.info("Linking files")
  graphData = data["scripts"]

  asPath = set()
  for i in graphData:
    asPath.add(utils.sha1sum(i["target"]["abs_path"]))

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
        "dependencies": utils.deduplicate(utils.pathToValidNames(itemDependencies, sha1Table)),
        "type": itemType
    }
    dependencyList[hashedItemPath]["pendingDepCount"] = 0
    for j in dependencyList[hashedItemPath]["dependencies"]:
      if j in asPath:
        dependencyList[hashedItemPath]["pendingDepCount"] += 1
      dependentList[j].append(hashedItemPath)

  for i in finalDepList:
    for j in dependentList[i]:
      print(j, sha1Table[j])
      # dependencyList[j]["pendingDepCount"] -= 1
      print(j, "depcnt: ", dependencyList[j]["pendingDepCount"], list(
          map(lambda x: sha1Table[x], dependencyList[j]["dependencies"])))
      if dependencyList[j]["pendingDepCount"] <= 1:
        print("Pushing", j)
        linkingTaskQueue.put(j)

  # print(dependencyList)
  # print(dependentList)

  ctr = len(graphData)
  while ctr > 0:
    p = Pool(1)
    while not linkingTaskQueue.empty():
      top = linkingTaskQueue.get()
      ctr -= 1
      p.apply_async(single_linking, args=(top,), error_callback=console.error)
    p.close()
    p.join()

  console.info("Finished.")
