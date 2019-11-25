import subprocess
import sys
import utils
import os
from multiprocessing import Pool

console = utils.Console()


def single_compile(cmd, filepath, r, totalLength):
  execname = utils.findName(filepath)
  if (os.access(filepath, os.R_OK)):
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
  originalCXX = utils.GET("original_cxx")

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
        cmdline[argnum] = utils.GET("targeted_cxx")
        cmdline.insert(argnum+1, "-emit-llvm")
      elif cmdline[argnum] == "-o":
        filepath = os.path.abspath(utils.GET("object_dir") +
                                   "/" + cmdline[argnum+1].split("/")[-1])
        cmdline[argnum+1] = filepath
        execname = utils.findName(filepath)
      elif cmdline[argnum] == "-c":
        cmdline[argnum] = "-S"
    command = " ".join(cmdline)
    compileTaskPool.apply_async(
        single_compile, args=(command, filepath, r, totalLength), error_callback=console.error)
    finalDepList.append(execname)
  compileTaskPool.close()
  compileTaskPool.join()

  # Construct the graph
  console.info("Linking files")
  graphData = data["scripts"]
  linkStack = utils.Stack()
  dependencyList = {}
  for i in graphData:
    # Initial data
    itemName = i["target"]["name"]
    itemDependencies = i["target"]["dependencies"]
    itemType = i["target"]["target_type"]
    dependencyList[itemName] = {
        "name": itemName,
        "dependencies": utils.pathToValidNames(itemDependencies),
        "type": itemType
    }
    linkStack.push(itemName)

  while not linkStack.empty():
    top = linkStack.top()
    if top in finalDepList:
      linkStack.pop()
      continue
    deps = dependencyList[top]["dependencies"]
    final = True
    for i in deps:
      if i not in finalDepList:
        final = False
        linkStack.push(i)
    if final:
      cmdline = utils.getllvmLinkCmd(top, deps, utils.GET("object_dir"))
      console.debug(cmdline)
      console.info("Linking " + top)
      try:
        subprocess.run(cmdline, shell=True,
                       stdout=subprocess.PIPE, check=True)
      except subprocess.CalledProcessError:
        console.error("Error linking {}".format(top))
        sys.exit(2)
      finalDepList.append(top)
      linkStack.pop()
  console.info("Finished.")
