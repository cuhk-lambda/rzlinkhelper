import json
import os
import sys
from termcolor import colored
from multiprocessing import Lock
from hashlib import sha1
from copy import deepcopy

settings = {
    "callpass_library_path": "./libcallpass.so",
    "object_dir": "objects",
    "debug": True,
    "original_cxx_executable": "/usr/bin/c++",
    "original_cc_executable": "/usr/bin/cc",
    "targeted_cxx_executable": "/usr/bin/clang++",
    "targeted_cc_executable": "/usr/bin/clang",
    "llvm_link_executable": "/usr/bin/llvm-link",
    "preserve_process": "sha1.json"
}

iolock = Lock()

def loadSettings(fp):
    custSettings = json.load(fp)
    for i in custSettings.keys():
        settings[i] = custSettings[i]

def GET(name):
    if name in settings:
        return settings[name]
    return None


class Console():
    @staticmethod
    def info(*st):
        with iolock:
            print(colored("[INFO]", "blue"), *st)

    @staticmethod
    def warn(*st):
        with iolock:
            print(colored("[WARN]", "yellow"), *st)

    @staticmethod
    def error(*st):
        with iolock:
            print(colored("[ERRR]", "red"), *st)

    @staticmethod
    def log(*st):
        Console.info(*st)

    @staticmethod
    def success(*st):
        with iolock:
            print(colored("[SUCC]", "green"), *st)

    @staticmethod
    def debug(*st):
        if GET("debug"):
            with iolock:
                print("[DEBG]", *st)


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


def findName(path):
    return path.split("/")[-1]


def findNames(path):
    return list(map(findName, path))


def pathToSha1(path, table):
    names = []
    for i in path:
        if i[-2:] == ".a" or \
                i[-2:] == ".o" or \
                i[-3:] == ".so":
            hashName = sha1sum(i)
            table[hashName] = i
            names.append(hashName)
    return names


def getllvmLinkCmd(destPath, deps):
    return GET("llvm_link_executable") + " " + " ".join(deps) + " -S -o " + destPath


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


def topoSort(targets, excludes):
    dup = deepcopy(targets)
    seq = []
    for idx, key in enumerate(dup):
        dup[key] = [r for r in dup[key] if r not in excludes]
    keyLen = len(dup.keys())
    while len(seq) < keyLen:
        removePending = []
        for i in dup.copy():
            if len(dup[i]) == 0:
                seq.append(i)
                removePending.append(i)
                del dup[i]
        if len(removePending) == 0:
            raise ValueError
        for idx, key in enumerate(dup):
            dup[key] = [r for r in dup[key] if r not in removePending]
    return seq
