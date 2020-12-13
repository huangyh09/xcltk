# cmdline options
# Author: Xianjie Huang <hxj5@hku.hk>

import sys
from .config import PROGRAM, VERSION
from .baf.phase_snp import phase_snp as baf_phase_snp
from .region.convert import convert as reg_convert

def __usage(fp = sys.stderr):
    msg =  "\n"
    msg += "Program: %s (Toolkit for XClone)\n" % PROGRAM
    msg += "Version: %s\n" % VERSION
    msg += "\n"
    msg += "Usage:   %s <command> [options]\n" % PROGRAM
    msg += "\n"                                          \
           "Commands:\n"                                  \
           "  -- BAF calculation\n"                                        \
           "     phase_snp        Aggregate SNPs into haplotype blocks\n"    \
           "\n"                                                              \
           "  -- RDR calculation\n"                                          \
           "\n"                                                              \
           "  -- Region operations\n"                                        \
           "     convert          Convert different region file formats\n"   \
           "\n"                                                              \
           "  -- Others\n"                                                   \
           "     -h, --help       Print this message\n"                       \
           "     -V, --version    Print version\n"                            \
           "\n"
    fp.write(msg)

def main():
    argc = len(sys.argv)
    if argc < 2:
        __usage()
        sys.exit(1)

    command = sys.argv[1]
    if command == "phase_snp": baf_phase_snp(argc, sys.argv)
    elif command == "convert": reg_convert()
    elif command in ("-h", "--help"): __usage(); sys.exit(3)
    elif command in ("-V", "--version"): sys.stderr.write("%s\n" % VERSION); sys.exit(3)
    else: sys.stderr.write("Error: wrong command '%s'\n" % command); sys.exit(5)

if __name__ == "__main__":
    main()
