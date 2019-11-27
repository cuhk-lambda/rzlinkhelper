import subprocess
import sys
import utils
import os
from multiprocessing import Pool
from os.path import realpath

console = utils.Console()

sha1Table = {}


def single_compile(cmd, hashname, execname, r, totalLength):
  if (os.access(utils.GET("object_dir") + "/" + hashname, os.R_OK)):
    console.info(
        "Found {}m, skipping. [{}/{}]".format(execname, r+1, totalLength))
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


def do_process(data):
  # Preparing directories
  utils.checkDir(utils.GET("object_dir"), "Object")
  utils.checkDir(utils.GET("target_dir"), "Target")
  originalCXX = utils.GET("original_cxx_executable")
  originalCC = utils.GET("original_cc_executable")

  totalLength = len(data["compile"])
  finalDepList = []
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
  linkStack = utils.Stack()
  dependencyList = {}
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
    linkStack.push(hashedItemPath)

  while not linkStack.empty():
    top = linkStack.top()
    console.debug("Analyzing {} ({}) [depth={}]".format(
        sha1Table[top], top, linkStack.size()))
    if top in finalDepList:
      linkStack.pop()
      continue
    if utils.hasNoDependency(sha1Table[top]):
      console.debug("{} has no dependency. Skipping.".format(sha1Table[top]))
      finalDepList.append(top)
      linkStack.pop()
      continue
    deps = dependencyList[top]["dependencies"]
    final = True
    for i in deps:
      if i not in finalDepList:
        if i == top:
          console.error(
              "Self-circle for {} ({}) found. Exiting.".format(sha1Table[i], i))
          sys.exit(255)
        final = False
        linkStack.push(i)
    if final:
      cmdline = utils.getllvmLinkCmd(top, deps, utils.GET("object_dir"))
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
                          utils.getllvmLinkCmd(sha1Table[top], list(map(lambda x: sha1Table[x], deps)), utils.GET("object_dir")))
          sys.exit(2)
      finalDepList.append(top)
      linkStack.pop()
  console.info("Finished.")
