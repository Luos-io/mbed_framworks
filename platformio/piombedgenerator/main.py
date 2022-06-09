# from copy import deepcopy, copy
from os.path import basename, isdir, join
import os

import json
from sys import exit as sys_exit
from string import Template

import sys
sys.path.insert(0, '..')

import tools.build_api
from tools.export import EXPORTERS
from tools.settings import ROOT
from tools.targets import TARGET_MAP

MBED_LIBS = [
    join(ROOT, "rtos"),
    join(ROOT, "events"),
    join(ROOT, "features", "mbedtls"),
    join(ROOT, "features", "netsocket"),
    join(ROOT, "features", "filesystem"),
    join(ROOT, "features", "unsupported", "dsp"),
    join(ROOT, "features", "unsupported", "rpc"),
    join(ROOT, "features", "unsupported", "USBDevice"),
    join(ROOT, "features", "unsupported", "USBHost")
]


def log_message(msg):
    print msg


def fix_paths(base_path, paths):

    if isinstance(paths, list):
        result = []
        for path in paths:
            fixed = path.replace(base_path, "")[1:].replace("\\", "/")
            result.append(fixed if fixed != "" else ".")
    else:
        result = paths.replace(base_path, "")[1:].replace("\\", "/")
        if result == "":
            result = "."

    return result


def merge_macro(macro):
    result = ""
    if isinstance(macro, tools.config.ConfigMacro):
        if macro.macro_value:
            result = macro.macro_name + macro.macro_value
        else:
            result = macro.macro_name
    elif macro.value is not None:
        result = macro.macro_name + " (" + str(macro.value) + ")"
    else:
        result = macro.macro_name

    return result


def get_config_data(target, path, exclude_paths=[]):
    config_toolchain = tools.build_api.prepare_toolchain(
        [path], "", target, 'GCC_ARM', silent=True)
    config_resources = config_toolchain.scan_resources(
        path, exclude_paths=exclude_paths)
    config_toolchain.config.load_resources(config_resources)
    return config_toolchain.config.get_config_data()


def create_target_dir(target):
    target_dir = join(ROOT, "platformio", "variants", target)
    if not isdir(target_dir):
        os.makedirs(target_dir)


def save_config(target, data):
    config_dir = join(ROOT, "platformio", "variants", target)
    if not isdir(config_dir):
        os.makedirs(config_dir)
    """ Saves dict with configuration for specified board to json file"""
    with open(join(config_dir, target + ".json"), 'w') as config_file:
        json.dump(data, config_file, sort_keys=True, indent=4)


def get_ldscript(resources):
    if resources.linker_script:
        return resources.linker_script.replace(ROOT, "")[1:].replace("\\", "/")


def get_softdevice(toolchain, resources):
    softdevice_hex = ""
    try:
        softdevice_hex = fix_paths(ROOT, resources.hex_files)[0]
    except:
        pass

    # try:
    #     softdevice_hex = toolchain.target.EXPECTED_SOFTDEVICES_WITH_OFFSETS[
    #         0]['name']
    # except:
    #     pass

    return softdevice_hex


def get_bootloader(toolchain):
    bootloader_hex = None

    try:
        bootloader_hex = toolchain.target.EXPECTED_SOFTDEVICES_WITH_OFFSETS[
            0]['boot']
    except:
        pass

    return bootloader_hex


def get_toolchain_flags(profile, toolchain="GCC_ARM"):
    if profile not in ("release", "debug", "develop"):
        print "Unknown toolchain profile"

    with open(join(ROOT, "tools", "profiles", "%s.json" % profile)) as fp:
        toolchain_configs = json.load(fp)

    return toolchain_configs.get(toolchain, dict())


def get_component_parameters(base_path, resources):

    parameters = {
        "inc_dirs": fix_paths(base_path, resources.inc_dirs),
        "s_sources": fix_paths(base_path, resources.s_sources),
        "c_sources": fix_paths(base_path, resources.c_sources),
        "cpp_sources": fix_paths(base_path, resources.cpp_sources),
        "libraries": fix_paths(base_path, resources.libraries)
    }

    return parameters


def create_config_include(target, toolchain):
    TMPL = """
// Automatically generated configuration file.

# ifndef __MBED_CONFIG_DATA__
# define __MBED_CONFIG_DATA__

// Configuration parameters

$config_str

# endif
"""

    symbols = list()
    for config in toolchain.config.get_config_data():
        for _, val in config.items():
            if "PRESENT" not in val.macro_name:
                symbols.append(merge_macro(val))

    data = ""
    for symbol in symbols:
        data += "#if !defined(%s)\n" % symbol.split(" ")[0]
        data += "\t#define " + symbol + "\n"
        data += "#endif\n"

    config = Template(TMPL)
    config_file = join(ROOT, "platformio", "variants",
                       target, "mbed_config.h")

    with open(config_file, "w") as fp:
        fp.write(config.substitute(config_str=data))


def main():

    log_message("Targets count %d" % len(EXPORTERS['gcc_arm'].TARGETS))
    exporter = EXPORTERS['gcc_arm']
    for target in TARGET_MAP:
        if not exporter.is_target_supported(target) and "mts" not in target.lower():
            log_message("* Skipped target %s" % target)
            continue

        log_message("Current target %s" % target)
        create_target_dir(target)

        toolchain = tools.build_api.prepare_toolchain(
            [ROOT], "", target, 'GCC_ARM', silent=True)

        framework_resources = toolchain.scan_resources(ROOT)
        toolchain.config.load_resources(framework_resources)

        mbed_parameters = {
            "symbols": toolchain.get_symbols(),
            "build_flags": toolchain.flags,
            "syslibs": toolchain.sys_libs,
            "ldscript": get_ldscript(framework_resources),
            "softdevice_hex": get_softdevice(toolchain, framework_resources)
        }

        # add default toolchain flags
        for key, value in get_toolchain_flags("release").iteritems():
            mbed_parameters['build_flags'][key].extend(value)

        # Add include with configuration file
        create_config_include(target, toolchain)

        mbed_parameters['build_flags']['common'].extend(
            ["-include", "mbed_config.h"])

        # mbed_parameters['symbols'] // MBED_CONF_*

        # Add to core everything except from libraries, features and platformio
        # folder
        excludes = MBED_LIBS + \
            [join(ROOT, "features"), join(ROOT, "platformio")]

        core_resources = toolchain.scan_resources(ROOT, exclude_paths=excludes)
        mbed_parameters['core'] = get_component_parameters(
            core_resources.base_path, core_resources)

        feature_parameters = dict()
        feature_set = [f for f in framework_resources.features]
        for feature in feature_set:
            # feature_toolchain = deepcopy(toolchain)
            feature_recources = framework_resources.features[feature]
            # feature_toolchain.config.load_resources(feature_recources)

            feature_parameters[feature] = get_component_parameters(
                framework_resources.features[feature].inc_dirs[0], feature_recources)

            feature_parameters[feature]['dir'] = fix_paths(
                ROOT, framework_resources.features[feature].inc_dirs[0])

        mbed_parameters['features'] = feature_parameters

        library_parameters = dict()
        lib_set = [l for l in MBED_LIBS]
        for lib in lib_set:
            lib_resources = toolchain.scan_resources(lib)
            lib_name = basename(lib)

            library_parameters[lib_name] = get_component_parameters(
                lib, lib_resources)

            library_parameters[lib_name]['dir'] = fix_paths(ROOT, lib)

        mbed_parameters['libs'] = library_parameters

        save_config(target, mbed_parameters)


if __name__ == "__main__":
    sys_exit(main())
