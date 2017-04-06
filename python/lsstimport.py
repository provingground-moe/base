#! env python

#
# LSST Data Management System
# Copyright 2008, 2009, 2010 LSST Corporation.
# Copyright 2015 AURA/LSST.
#
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the LSST License Statement and
# the GNU General Public License along with this program.  If not,
# see <http://www.lsstcorp.org/LegalNotices/>.
#

from __future__ import absolute_import, division, print_function
import sys
import imp
import functools
import importlib
import os.path

# List of extensions to set global flags.  May need to be extended
# for systems other than *nix and OSX.
SHARED_LIB_EXTENSION_LIST = ('.so', '.dylib')
LIB_EXCEPTION_LIST = ('_lsstcppimport.so',)

# Ensure that duplicate allocations--particularly those related to RTTI--are
# resolved by setting dynamical library loading flags.
RTLD_GLOBAL = None
RTLD_NOW = None

# For portability we try a number of different options for determining RTLD constants
options = ('os', 'DLFCN', 'ctypes')
for mod in options:
    try:
        m = importlib.import_module(mod)
        if RTLD_GLOBAL is None and hasattr(m, "RTLD_GLOBAL"):
            RTLD_GLOBAL = m.RTLD_GLOBAL
        if RTLD_NOW is None and hasattr(m, "RTLD_NOW"):
            RTLD_NOW = m.RTLD_NOW
    except ImportError:
        pass
    if RTLD_GLOBAL is not None and RTLD_NOW is not None:
        break

# Failing to find RTLD_GLOBAL is definitely unexpected and needs investigation.
if RTLD_GLOBAL is None:
    raise NameError("RTLD_GLOBAL constant can not be determined")

# RTLD_NOW will be missing on Python 2 with OS X.
# The value is defined in dlfcn.h and on Mac and Linux has the same value:
#    #define RTLD_NOW	0x2
# Do not issue a warning message as this will happen on every single import.
if RTLD_NOW is None:
    RTLD_NOW = 2

DLFLAGS = RTLD_GLOBAL | RTLD_NOW

# Note: Unsure if the following is still needed with pybind11

# Swigged python libraries that import other swigged python libraries
# need to import with RTLD_GLOBAL and RTLD_NOW set.  This causes
# problems with symbol collisions in third party packages (notably
# scipy).  This cannot be fixed by using import hooks because python
# code generated by swig uses imp.load_module rather than import.
# This makes it necessary to over ride imp.load_module.  This was
# handled in ticket #3055: https://dev.lsstcorp.org/trac/ticket/3055

# Don't redefine if it's already been defined.
if 'orig_imp_load_module' not in locals():
    orig_imp_load_module = imp.load_module

    @functools.wraps(orig_imp_load_module)
    def imp_load_module(name, *args):
        pathParts = args[1].split(os.path.sep)
        extension = os.path.splitext(pathParts[-1])[-1]
        # Find all swigged LSST libs.  Load _lsstcppimport.so by
        # adding it to the EXCEPTIONLIST since it may not have lsst in
        # the path (it's in $BASE_DIR/python, not
        # $BASE_DIR/python/lsst).  Also, look for paths that look like
        # python/lsst as that is how to know if you are in an LSST
        # package.
        lsstIdx = [i for i, el in enumerate(pathParts) if el == 'python']
        if pathParts[-1] in LIB_EXCEPTION_LIST or (extension in SHARED_LIB_EXTENSION_LIST and
                                                   pathParts[-1].startswith('_') and
                                                   'lsst' in [pathParts[i+1] for i in lsstIdx]):
            # Get currently set flags
            originalDLFlags = sys.getdlopenflags()
            # Set flags
            sys.setdlopenflags(DLFLAGS)
            try:
                module = orig_imp_load_module(name, *args)
            finally:
                # Set original flags
                sys.setdlopenflags(originalDLFlags)
        else:
            module = orig_imp_load_module(name, *args)
        return module
    imp.load_module = imp_load_module

try:
    import lsstcppimport
except ImportError:
    print(
        "Could not import lsstcppimport; please ensure the base package has been built (not just setup).\n",
        file=sys.stderr)
