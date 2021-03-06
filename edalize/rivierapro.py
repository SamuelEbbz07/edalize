# Copyright edalize contributors
# Licensed under the 2-Clause BSD License, see LICENSE for details.
# SPDX-License-Identifier: BSD-2-Clause

import os
import logging
import sys
from edalize.edatool import Edatool

logger = logging.getLogger(__name__)

RUN_DO = """#Generated by Edalize
run -all
exit
"""


class Rivierapro(Edatool):

    argtypes = ["plusarg", "vlogdefine", "vlogparam"]

    @classmethod
    def get_doc(cls, api_ver):
        if api_ver == 0:
            return {
                "description": "Riviera Pro simulator from Aldec",
                "members": [
                    {
                        "name": "compilation_mode",
                        "type": "String",
                        "desc": "Common or separate compilation, sep - for separate compilation, common - for common compilation",
                    }
                ],
                "lists": [
                    {
                        "name": "vlog_options",
                        "type": "String",
                        "desc": "Additional options for compilation with vlog",
                    },
                    {
                        "name": "vsim_options",
                        "type": "String",
                        "desc": "Additional run options for vsim",
                    },
                ],
            }

    def _write_build_rtl_tcl_file(self, tcl_main):
        tcl_build_rtl = open(os.path.join(self.work_root, "edalize_build_rtl.tcl"), "w")

        (src_files, incdirs) = self._get_fileset_files(force_slash=True)
        vlog_include_dirs = ["+incdir+" + d.replace("\\", "/") for d in incdirs]

        libs = []
        common_compilation_sv = []
        common_compilation_vhdl = []
        for f in src_files:
            if not f.logical_name:
                f.logical_name = "work"
            if not f.logical_name in libs:
                tcl_build_rtl.write("vlib {}\n".format(f.logical_name))
                libs.append(f.logical_name)
            if f.file_type.startswith("verilogSource") or f.file_type.startswith(
                "systemVerilogSource"
            ):
                cmd = "vlog"
                args = []
                args += self.tool_options.get("vlog_options", [])
                if f.file_type.startswith("verilogSource"):
                    if f.file_type.endswith("95"):
                        args.append("-v95")
                    elif f.file_type.endswith("2001"):
                        args.append("-v2k")
                    elif f.file_type.endswith("2005"):
                        args.append("-v2k5")
                else:
                    args += ["-sv"]

                for k, v in self.vlogdefine.items():
                    args += ["+define+{}={}".format(k, self._param_value_str(v))]

                args += vlog_include_dirs
            elif f.file_type.startswith("vhdlSource"):
                cmd = "vcom"
                if f.file_type.endswith("-87"):
                    args = ["-87"]
                if f.file_type.endswith("-93"):
                    args = ["-93"]
                if f.file_type.endswith("-2008"):
                    args = ["-2008"]
                else:
                    args = []
            elif f.file_type == "tclSource":
                cmd = None
                tcl_main.write("do {}\n".format(f.name))
            elif f.file_type == "user":
                cmd = None
            else:
                _s = "{} has unknown file type '{}'"
                logger.warning(_s.format(f.name, f.file_type))
                cmd = None
            if cmd:
                args += ["-quiet"]
                args += ["-work", f.logical_name]
                args += [f.name]
                if cmd == "vlog":
                    if not common_compilation_sv:
                        common_compilation_sv += ["vlog"]
                        for k, v in self.vlogdefine.items():
                            common_compilation_sv += [
                                "+define+{}={}".format(k, self._param_value_str(v))
                            ]
                        common_compilation_sv += self.tool_options.get(
                            "vlog_options", []
                        )
                        common_compilation_sv += vlog_include_dirs
                        common_compilation_sv += ["-quiet"]
                        common_compilation_sv += ["-work", f.logical_name]
                        common_compilation_sv += [f.name, "\\\n"]
                    else:
                        common_compilation_sv += [f.name, "\\\n"]
                elif cmd == "vcom":
                    if not common_compilation_vhdl:
                        common_compilation_vhdl += ["vcom"]
                        common_compilation_vhdl += [f.name, "\\\n"]
                    else:
                        common_compilation_vhdl += [f.name, "\\\n"]
                if (self.tool_options.get("compilation_mode")) == "sep" or (
                    self.tool_options.get("compilation_mode") == None
                ):
                    tcl_build_rtl.write("{} {}\n".format(cmd, " ".join(args)))

        if self.tool_options.get("compilation_mode") == "common":
            if common_compilation_sv:
                tcl_build_rtl.write("{} \n".format(" ".join(common_compilation_sv)))
            if common_compilation_vhdl:
                tcl_build_rtl.write("{} \n".format(" ".join(common_compilation_vhdl)))

        if not (
            self.tool_options.get("compilation_mode") == "common"
            or self.tool_options.get("compilation_mode") == None
            or self.tool_options.get("compilation_mode") == "sep"
        ):
            raise RuntimeError(
                "wrong compilation mode, use --compilation_mode=common for common compilation or --compilation_mode=sep for separate compilation"
            )

    def _write_run_tcl_file(self):
        tcl_launch = open(os.path.join(self.work_root, "edalize_launch.tcl"), "w")

        # FIXME: Handle failures. Save stdout/stderr
        vpi_options = []
        for vpi_module in self.vpi_modules:
            vpi_options += ["-pli", vpi_module["name"]]

        args = ["vsim"]
        args += self.tool_options.get("vsim_options", [])
        args += vpi_options
        args += self.toplevel.split()

        # Plusargs
        for key, value in self.plusarg.items():
            args += ["+{}={}".format(key, self._param_value_str(value))]
        # Top-level parameters
        for key, value in self.vlogparam.items():
            args += ["-g{}={}".format(key, self._param_value_str(value))]
        tcl_launch.write(" ".join(args) + "\n")
        tcl_launch.close()

        tcl_run = open(os.path.join(self.work_root, "edalize_run.tcl"), "w")
        tcl_run.write("do edalize_launch.tcl\n")
        tcl_run.write("run -all\n")
        tcl_run.write("exit\n")
        tcl_run.close()

    def _write_build_vpi_tcl_file(self):
        tcl_build_vpi = open(os.path.join(self.work_root, "edalize_build_vpi.tcl"), "w")
        for vpi_module in self.vpi_modules:
            _name = vpi_module["name"]
            _incs = " ".join(["-I" + d for d in vpi_module["include_dirs"]])
            _libs = " ".join(["-l" + l for l in vpi_module["libs"]])
            _options = "-std=c99"
            _srcs = " ".join(vpi_module["src_files"])
            _s = "ccomp -pli -o {}.so {} {} {} {}\n".format(
                vpi_module["name"], _incs, _libs, _options, _srcs
            )

            tcl_build_vpi.write(_s)
        tcl_build_vpi.close()

    def configure_main(self):
        tcl_main = open(os.path.join(self.work_root, "edalize_main.tcl"), "w")
        tcl_main.write("do edalize_build_rtl.tcl\n")

        self._write_build_rtl_tcl_file(tcl_main)
        if self.vpi_modules:
            self._write_build_vpi_tcl_file()
            tcl_main.write("do edalize_build_vpi.tcl\n")
        tcl_main.close()
        self._write_run_tcl_file()

    def build_pre(self):
        if not os.getenv("ALDEC_PATH"):
            raise RuntimeError(
                "Environment variable ALDEC_PATH was not found. It should be set to Riviera Pro install path. Please source <Riviera Pro install path>/etc/setenv to set it"
            )
        super(Rivierapro, self).build_pre()

    def build_main(self):
        args = ["-c", "-do", "do edalize_main.tcl; exit"]
        self._run_tool("vsim", args, quiet=True)

    def run_main(self):
        if not os.getenv("ALDEC_PATH"):
            raise RuntimeError(
                "Environment variable ALDEC_PATH was not found. It should be set to Riviera Pro install path. Please source <Riviera Pro install path>/etc/setenv to set it"
            )

        args = ["-c", "-quiet", "-do", "edalize_run.tcl"]
        self._run_tool("vsim", args)
