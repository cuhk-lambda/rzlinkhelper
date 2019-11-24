import subprocess
import sys
import utils

console = utils.Console()


def do_process(data):
  # Preparing directories
  utils.checkDir(utils.GET("object_dir"), "Object")
  utils.checkDir(utils.GET("target_dir"), "Target")

  finalDepList = []
  console.log("Compiling .o (total: {})".format(len(data["compile"])))
  for i in data["compile"]:
    execname = "(unknown)"
    cmdline = list(filter(lambda x: x != "", i.split(" ")))
    cmdline[0] = "/usr/bin/clang++"
    cmdline.insert(1, "-emit-llvm")
    for argnum in range(2, len(cmdline)):
      if cmdline[argnum] == "-o":
        cmdline[argnum+1] = utils.GET("object_dir") + \
            "/" + cmdline[argnum+1].split("/")[-1]
        execname = cmdline[argnum+1].split("/")[-1]
      elif cmdline[argnum] == "-c":
        cmdline[argnum] = "-S"
    command = " ".join(cmdline)
    console.debug(command)
    console.info("Compiling {}".format(execname))
    finalDepList.append(execname)
    try:
      subprocess.run(command, shell=True,
                     stdout=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError:
      console.error("Error compiling {}".format(execname))
      sys.exit(2)

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
