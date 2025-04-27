import abc
import json

from . import error


class Dobj(abc.ABC):
    @abc.abstractmethod
    def to_dict(self):
        pass

    @classmethod
    @abc.abstractmethod
    def from_dict(cls, d):
        pass

def dobjs_to_dicts(dobjs):
    dicts = []
    for dobj in dobjs:
        d = dobj.to_dict()
        dicts.append(d)
    return dicts

def dicts_to_dobjs(dicts, cls):
    dobjs = []
    for d in dicts:
        dobj = cls.from_dict(d)
        dobjs.append(dobj)
    return dobjs

def dobj_dict_to_dict_dict(dobj_dict):
    dict_dict = {}
    for key, val in dobj_dict.items():
        dict_dict[key] = val.to_dict()
    return dict_dict

def dict_dict_to_dobj_dict(dict_dict, cls):
    dobj_dict = {}
    for key, val in dict_dict.items():
        dobj_dict[key] = cls.from_dict(val)
    return dobj_dict

def write_dobj(dobj, file_path):
    try:
        d = dobj.to_dict()
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(d, file, indent=4)
    except:
        return error.Error("An error occurred while writing to the file.")

    return None

def read_dobj(file_path, cls):
    try:
        d = {}
        with open(file_path, "r", encoding="utf-8") as file:
            d = json.load(file)
        dobj = cls.from_dict(d)
        return dobj, None
    except:
        return None, error.Error("An error occurred while reading from the file.")

    return None, error.Error("Unknown Error")
