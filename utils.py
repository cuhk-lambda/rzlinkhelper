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
    "preserve_process": "sha1.json",
    "toposort_verbose_logging_dir": ""
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


def topoSort(targets, excludes, table):
    dup = deepcopy(targets)
    seq = []
    for idx, key in enumerate(dup):
        dup[key] = [r for r in dup[key] if r not in excludes]
    keyLen = len(dup.keys())
    rnd = 0
    logDir = GET("toposort_verbose_logging_dir")
    logging = True if logDir != "" and logDir != None else False
    if logging:
        Console.warn("Toposort verbose logging is on. Logs will be saved to {}/. Be cautious since it will be a lot of data.".format(logDir))
    while len(seq) < keyLen:
        if logging:
            json.dump(unravel(dup, table), open(logDir + "/" + str(rnd) + ".rest","w"))
            json.dump(list(map(lambda x:table[x], seq)), open(logDir + "/" + str(rnd) + ".curr","w"))
        removePending = []
        for i in dup.copy():
            if len(dup[i]) == 0:
                seq.append(i)
                removePending.append(i)
                del dup[i]
        if len(removePending) == 0:
            Console.debug("Current queue:", seq)
            raise ValueError
        for idx, key in enumerate(dup):
            dup[key] = [r for r in dup[key] if r not in removePending]
        rnd += 1
    return seq

def unravel(obj, table):
    newobj = {}
    for i in obj.keys():
        newobj[table[i]] = list(map(lambda x:table[x], obj[i]))
    return newobj
