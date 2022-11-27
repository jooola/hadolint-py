from __future__ import annotations

import hashlib
import http
import os
import platform
import shutil
import stat
import sys
import tempfile
import urllib.request
from distutils.command.build import build as orig_build
from os import path

from setuptools import Command, setup
from setuptools.command.install import install as orig_install

REPOSITORY = "hadolint/hadolint"
VERSION = "2.12.0"
LOCAL_VERSION = "0"

ASSETS = {
    "hadolint-Darwin-x86_64": "2a5b7afcab91645c39a7cebefcd835b865f7488e69be24567f433dfc3d41cd27",
    "hadolint-Linux-arm64": "5798551bf19f33951881f15eb238f90aef023f11e7ec7e9f4c37961cb87c5df6",
    "hadolint-Linux-x86_64": "56de6d5e5ec427e17b74fa48d51271c7fc0d61244bf5c90e828aab8362d55010",
    "hadolint-Windows-x86_64.exe": "ed89a156290e15452276b2b4c84efa688a5183d3b578bfaec7cfdf986f0632a8",
}
ASSETS_MAPPING = {
    ("darwin", "x86_64"): "hadolint-Darwin-x86_64",
    ("linux", "arm64"): "hadolint-Linux-arm64",
    ("linux", "x86_64"): "hadolint-Linux-x86_64",
    ("win32", "AMD64"): "hadolint-Windows-x86_64.exe",
}

FILENAME = "hadolint"


def get_download_url() -> tuple[str, str]:
    asset = ASSETS_MAPPING[(sys.platform, platform.machine())]
    sha256 = ASSETS[asset]
    return (
        f"https://github.com/{REPOSITORY}/releases/download/v{VERSION}/{asset}",
        sha256,
    )


def download(url: str, sha256: str) -> str:
    with urllib.request.urlopen(url) as resp:
        code = resp.getcode()
        if code != http.HTTPStatus.OK:
            raise ValueError(f"HTTP failure. Code: {code}")

        hasher = hashlib.sha256()
        block_size = 1024 * 8

        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            while True:
                block = resp.read(block_size)
                if not block:
                    break
                tmp_file.write(block)
                hasher.update(block)

        checksum = hasher.hexdigest()
        if checksum != sha256:
            raise ValueError(f"sha256 mismatch, expected {sha256}, got {checksum}")

    return tmp_file.name


def save_binary(src_path: str, dest_dir: str):
    dest_path = path.join(dest_dir, FILENAME)
    if sys.platform == "win32":
        dest_path += ".exe"

    os.makedirs(dest_dir)
    shutil.move(src_path, dest_path)

    # Mark as executable.
    # https://stackoverflow.com/a/14105527
    mode = os.stat(dest_path).st_mode
    mode |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    os.chmod(dest_path, mode)


class fetch_binary(Command):
    description = "fetch the binary"

    build_temp: str = None

    def initialize_options(self):
        pass

    def finalize_options(self):
        self.set_undefined_options("build", ("build_temp", "build_temp"))

    def run(self):
        url, sha256 = get_download_url()
        tmp_file = download(url, sha256)
        save_binary(tmp_file, self.build_temp)


class build(orig_build):
    sub_commands = orig_build.sub_commands + [("fetch_binary", None)]


class install_binary(Command):
    description = "install the binary"

    outfiles: list = []
    build_temp: str = None
    install_scripts: str = None

    def initialize_options(self):
        pass

    def finalize_options(self):
        self.set_undefined_options("build", ("build_temp", "build_temp"))
        self.set_undefined_options("install", ("install_scripts", "install_scripts"))

    def run(self):
        self.outfiles = self.copy_tree(self.build_temp, self.install_scripts)

    def get_outputs(self):
        return self.outfiles


class install(orig_install):
    sub_commands = orig_install.sub_commands + [("install_binary", None)]


command_overrides = {
    "build": build,
    "fetch_binary": fetch_binary,
    "install": install,
    "install_binary": install_binary,
}

try:
    from wheel.bdist_wheel import bdist_wheel as orig_bdist_wheel

    class bdist_wheel(orig_bdist_wheel):
        root_is_pure: bool

        def finalize_options(self):
            super().finalize_options()
            self.root_is_pure = False

        def get_tag(self) -> tuple[str, str, str]:
            # (impl, abi_tag, plat_name)
            _, _, plat = super().get_tag()
            return "py2.py3", "none", plat

    command_overrides["bdist_wheel"] = bdist_wheel
except ImportError:
    pass

setup(
    name="hadolint-py",
    version=f"{VERSION}.{LOCAL_VERSION}",
    description="Python wrapper around invoking hadolint (https://github.com/hadolint/hadolint)",
    author="Joola",
    url="https://github.com/jooola/hadolint-py",
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
    ],
    python_requires=">=3.7",
    cmdclass=command_overrides,
)
