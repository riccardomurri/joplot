#!/usr/bin/env python

# See http://packages.python.org/distribute/setuptools.html for details
from distribute_setup import use_setuptools
use_setuptools()


# XXX: `./setup.py` fails with "error: invalid command 'develop'" when
# package `distribute` is first downloaded by `distribute_setup`;
# subsequent invocations of it (when the `distribute-*.egg` file is
# already there run fine, apparently.  So, let us re-exec ourselves
# to ensure that `distribute` is loaded properly.
REINVOKE = "__SETUP_REINVOKE"
import sys
import os
if not os.environ.has_key(REINVOKE):
    # mutating os.environ doesn't work in old Pythons
    os.putenv(REINVOKE, "1")
    try:
        os.execvp(sys.executable, [sys.executable] + sys.argv)
    except OSError, x:
        sys.stderr.write("Failed to re-exec '%s' (got error '%s');"
                         " continuing anyway, keep fingers crossed.\n"
                         % (str.join(' ', sys.argv), str(x)))
if hasattr(os, "unsetenv"):
    os.unsetenv(REINVOKE)


def read_whole_file(path):
    stream = open(path, 'r')
    text = stream.read()
    stream.close
    return text


# see http://peak.telecommunity.com/DevCenter/setuptools
# for an explanation of the keywords and syntax of this file.
#
import setuptools
import setuptools.dist
setuptools.setup(
    name = "joplot",
    version = "1.0rc1",

    packages = setuptools.find_packages(exclude=['ez_setup']),

    # metadata for upload to PyPI
    description = "A Python webapp for graphing batch cluster usage and accounting data.",
    long_description = read_whole_file('README.rst'),
    author = "Riccardo Murri",
    author_email = "riccardo.murri@gmail.com",
    license = "GPL",
    keywords = "pbs batch job web accounting",
    url = "http://github.com/riccardomurri/joplot", # project home page

    # see http://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers = [
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
        "License :: DFSG approved",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.4",
        "Programming Language :: Python :: 2.5",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        ],

    # entry_points = {
    #     'console_scripts': [
    #         ],
    #    },

    # run-time dependencies
    install_requires = [
        'tempita',
        ],

    # additional non-Python files to be bundled in the package
    # package_data = {
    #     'joplot': [
    #         'etc/joplot.ini.example',
    #         ],
    #     },

    # `zip_safe` can ease deployment, but is only allowed if the package
    # do *not* do any __file__/__path__ magic nor do they access package data
    # files by file name (use `pkg_resources` instead).
    zip_safe = True,
)
