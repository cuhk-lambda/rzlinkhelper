import json
import os
import sys
from termcolor import colored
from multiprocessing import Lock
from hashlib import sha1
from os.path import realpath

settings = {
    "callpass_library_path": "./libcallpass.so",
    "object_dir": "objects",
    "target_dir": "targets",
    "debug": True,
    "original_cxx_executable": "/usr/bin/c++",
    "original_cc_executable": "/usr/bin/cc",
    "targeted_cxx_executable": "/usr/bin/clang++",
    "targeted_cc_executable": "/usr/bin/clang",
    "llvm_link_executable": "/usr/bin/llvm-link"
}


iolock = Lock()

try:
  custSettings = json.load(open("settings.json"))
  for i in custSettings.items():
    settings[i[0]] = i[1]
except:
  pass


def GET(name):
  if name in settings:
    return settings[name]
  return None


class Console():
  @staticmethod
  def info(*st):
    iolock.acquire()
    print(colored("[INFO]", "blue"), *st)
    iolock.release()

  @staticmethod
  def warn(*st):
    iolock.acquire()
    print(colored("[WARN]", "yellow"), *st)
    iolock.release()

  @staticmethod
  def error(*st):
    iolock.acquire()
    print(colored("[ERRR]", "red"), *st)
    iolock.release()

  @staticmethod
  def log(*st):
    Console.info(*st)

  @staticmethod
  def debug(*st):
    if GET("debug"):
      iolock.acquire()
      print("[DEBG]", *st)
      iolock.release()


def checkDir(subdir, name):
  if not os.access(subdir, os.W_OK):
    Console.warn(name + " directory unreadable. Trying to create.")
    try:
      os.mkdir(subdir)
      if not os.access(subdir, os.W_OK):
        raise IOError
    except:
      Console.error(name + " directory unwritable")
      sys.exit(1)
  if len(os.listdir(subdir)) != 0:
    Console.warn(name + " directory is not empty!")


def hasNoIndirectDependcies(deps):
  for i in deps:
    if len(i) > 2 and i[-2:] == ".o":
      continue
    else:
      return False
  return True


class Stack():
  def __init__(self):
    self.items = []

  def push(self, obj):
    self.items.append(obj)

  def top(self):
    if (len(self.items) > 0):
      return self.items[-1]
    return None

  def pop(self):
    if (len(self.items) > 0):
      del self.items[-1]

  def size(self):
    return len(self.items)

  def empty(self):
    return self.size() == 0


def findName(path):
  return path.split("/")[-1]


def findNames(path):
  return list(map(findName, path))


def pathToValidNames(path, table):
  names = []
  for i in path:
    if i[-2:] == ".a" or \
       i[-2:] == ".o" or \
       i[-3:] == ".so":
      hashName = sha1sum(i)
      table[hashName] = i
      names.append(hashName)
  return names


def getllvmLinkCmd(fhash, deps, dstdir):
  return GET("llvm_link_executable") + " " + " ".join(list(map(lambda x: dstdir + "/" + x, deps))) + " -S -o " + realpath(dstdir + "/" + fhash)


def sha1sum(text):
  return sha1(text.encode()).hexdigest()

def deduplicate(items):
  ret = []
  for i in items:
    if i not in ret:
      ret.append(i)
  return ret

def hasNoDependency(fullpath):
  return fullpath[-2:] == ".o"