import os
import subprocess

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def hidden_creationflags() -> int:
    if os.name == "nt":
        return CREATE_NO_WINDOW
    return 0


def run_hidden(*args, **kwargs):
    if os.name == "nt":
        flags = kwargs.pop("creationflags", 0)
        kwargs["creationflags"] = flags | CREATE_NO_WINDOW
    return subprocess.run(*args, **kwargs)


def popen_hidden(*args, **kwargs):
    if os.name == "nt":
        flags = kwargs.pop("creationflags", 0)
        kwargs["creationflags"] = flags | CREATE_NO_WINDOW
    return subprocess.Popen(*args, **kwargs)
