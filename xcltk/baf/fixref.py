#!/usr/bin/env python
#this script is aimed to make sure REFs match certain genome reference build.
#it would change corresponding ALT & GT while delete other fields in FORMAT
#Author: Xianjie Huang 

import sys
import getopt
import time
import gzip
import pysam
from .config import APP

COMMAND = "fixref"

def __load_ref(fn):
    """
    @abstract    Load ref fasta file and extract ref alleles
    @param fn    Path to ref fasta file [str]
    @return      List of ref alleles [list<str>]
    @note        The extracted ref allele will be "" if the corresponding 
                 fasta record is empty.
    """
    def __fmt_ref(i, r, n):
        if r != ">": return(r)
        elif i + 1 >= n or ref_alleles[i + 1] == ">": return("")
        else: return(None)
    fp = gzip.open(fn, "rt") if fn.endswith(".gz") else open(fn, "r")
    ref_alleles = [line[0] for line in fp]
    fp.close()
    n = len(ref_alleles)
    ref_alleles = [__fmt_ref(i, r, n) for i, r in enumerate(ref_alleles)]
    ref_alleles = [r for r in ref_alleles if r is not None]
    return(ref_alleles)

def __fix_rec(nr, ref0, line):
    """
    @abstract      Check & fix ref and corresponding alt & GT for one vcf record
    @param nr      Index of the vcf record, 1-based [int]
    @param ref0    Real REF from fasta [chr]
    @param line    The vcf record whose ref is to be checked, ends with '\n' [str]
    @return        A tuple of two elements: the running state and the checked line [tuple<int, str>]
                   The running state: 
                     -1, if error;
                     0, if ref == ref0, i.e., no fix is needed
                     1, if vcf record is successfully fixref-ed.
    """
    parts = line[:-1].split("\t")
    try:
        chrom, pos, ref, alt, fmt, fval = parts[0], parts[1], parts[3], parts[4], parts[8], parts[9] 
    except:
        sys.stderr.write("[W::fix_rec] skip No.%d line for failing to parse vcf line.\n" % nr)
        return((-1, None))
    
    # No fix is needed
    if ref == ref0:
        return (0, line)
    
    fmt_parts = fmt.split(":")
    fval_parts = fval.split(":")
    try:
        gt_idx = fmt_parts.index("GT")
        gt = fval_parts[gt_idx]
    except:
        sys.stderr.write("[W::fix_rec] skip No.%d %s:%s for error GT, format str: %s; format value: %s\n" % (nr, chrom, pos, fmt, fval))
        return((-1, None))
    new_alt = alt
    new_gt = gt
    if ref != ref0:
        sep = None
        if "/" in gt: 
            sep = "/"
        elif "|" in gt: 
            sep = "|"
        else:
            sys.stderr.write("[W::fix_rec] skip No.%d %s:%s for error GT sep, GT str: %s\n" % (nr, chrom, pos, gt))
            return((-1, None))
        ra_idx = gt.split(sep)    # index of ref/alt: 0, 1, 2
        if len(ra_idx) != 2: 
            sys.stderr.write("[W::fix_rec] skip No.%d %s:%s for error GT alleles, GT str: %s\n" % (nr, chrom, pos, gt))
            return((-1, None))
        try:
            idx1, idx2 = int(ra_idx[0]), int(ra_idx[1])
        except:
            sys.stderr.write("[W::fix_rec] skip No.%d %s:%s for error GT allele index, GT str: %s\n" % (nr, chrom, pos, gt))
            return((-1, None))
        allele1 = allele2 = None
        multi_alt = alt.split(",")
        try:
            if idx1 == 0: allele1 = ref
            else: allele1 = multi_alt[idx1 - 1]
            if idx2 == 0: allele2 = ref
            else: allele2 = multi_alt[idx2 - 1]
        except:
            sys.stderr.write("[W::fix_rec] skip No.%d %s:%s for error ALT, ALT str: %s\n" % (nr, chrom, pos, alt))
            return((-1, None))
        if len(allele1) != 1 or len(allele2) != 1 or allele1 not in "ACGTN" or allele2 not in "ACGTN":
            sys.stderr.write("[W::fix_rec] skip No.%d %s:%s for invalid allele, allele1 = %s; allele2 = %s\n" % (nr, chrom, pos, allele1, allele2))
            return((-1, None))
        new_alts = []
        new_idx1 = new_idx2 = None
        if allele1 == ref0: new_idx1 = 0
        else: new_idx1 = 1; new_alts.append(allele1)
        if allele2 == ref0: new_idx2 = 0
        elif allele2 == allele1: new_idx2 = new_idx1
        else: new_idx2 = new_idx1 + 1; new_alts.append(allele2)
        new_alt = ",".join(new_alts) if new_alts else "."
        new_gt = sep.join([str(i) for i in [new_idx1, new_idx2]])   # CHECK ME! does the order of allele indexes matter?
        #if new_idx1 == 0 and new_idx2 == 0:
        #    sys.stderr.write("[W::fix_rec] skip %s:%s for new gt being 0/0, from %s:%s:%s to %s:%s:%s.\n" % (chrom, pos, ref, alt, gt, ref0, new_alt, new_gt))
        #    return((-1, None))
    parts[2] = parts[5] = parts[7] = "."
    parts[3] = ref0
    parts[4] = new_alt
    parts[8] = "GT"
    parts[9] = new_gt
    new_vcf_line = "\t".join(parts) + "\n"
    if ref != ref0:
        sys.stderr.write("[I::fix_rec] change No.%d %s:%s from %s:%s:%s to %s:%s:%s\n" % (nr, chrom, pos, ref, alt, gt, ref0, new_alt, new_gt))
    return((1, new_vcf_line))

def __fix_file(in_fn, out_fn, ref_fn):
    """
    @abstract       Fix REF, ALT & GT while delete other fields in FORMAT
    @param in_fn    Input vcf file to be fixed [str]
    @param out_fn   Output vcf file [str]
    @param ref_fn   Ref fasta file generated by samtools faidx [str]
    @return         0 if success, -1 otherwise
    """
    # load ref fasta and input vcf
    # ref_alleles = __load_ref(ref_fn)
    
    FASTA = pysam.FastaFile(ref_fn)

    ifp = gzip.open(in_fn, "rt") if in_fn.endswith(".gz") else open(in_fn, "r")
    vcf_lines = ifp.readlines()
    ifp.close()
    nc = 0     # number of vcf comment lines.
    for line in vcf_lines:
        if line[0] == "#": nc += 1
        else: break
    # sys.stderr.write("Info: len(vcf_lines) = %d; len(ref_alleles) = %d; len(comment_lines) = %d\n" % (len(vcf_lines), len(ref_alleles), nc))
    # if len(vcf_lines) - nc != len(ref_alleles):
    #     sys.stderr.write("Error: nlines of ref_alleles is not equal to nrecords of vcf!\n")
    #     return(-1)
    
    # fixref and output
    # TODO: add cmdline of this run to the output file
    ofp = None
    if out_fn:
        ofp = gzip.open(out_fn, "wb") if out_fn.endswith(".gz") else open(out_fn, "w")
    else:
        ofp = sys.stdout
    for i in range(nc):
        ofp.write(vcf_lines[i])   
    nr = 0
    fix_cnt = 0
    matched_cnt = 0
    for line in vcf_lines[nc:]:
        if line[0] in ("\n", "#"):
            sys.stderr.write("Error: invalid vcf format, wrong comment line for No.%d record!\n" % (nr + 1,))
            return(-1)
        
        _chr, _pos = line.split('\t')[:2]
        _ref_allele = FASTA.fetch(_chr, int(_pos) - 1, int(_pos))
        ret, new_line = __fix_rec(nr + 1, _ref_allele, line)
        
        # if not ref_alleles[nr]:
        #     sys.stderr.write("Warning: skip No.%d record for no real REF!\n" % (nr + 1,))
        #     nr += 1
        #     continue
        # ret, new_line = __fix_rec(nr + 1, ref_alleles[nr], line)

        if ret < 0: pass
        elif ret == 0 or ret == 1: ofp.write(new_line)
        else: pass
        
        nr += 1
        if ret == 1: fix_cnt += 1
        if ret == 0: matched_cnt += 1
        
    sys.stderr.write("%d valid records in input VCF!\n" % (nr))
    sys.stderr.write("%d records have been fixed REF!\n" % (fix_cnt))
    sys.stderr.write("%d records don't need to fix REF!\n" % (matched_cnt))

    if out_fn:
        ofp.close()
    return(0)

def __usage(fp = sys.stderr):
    msg =  "\n"
    msg += "Usage: %s %s [options]\n" % (APP, COMMAND)
    msg += "\n"                                                        \
           "Options:\n"                                                \
           "  -i, --input FILE    Path to input vcf file\n"              \
           "  -r, --ref FILE      Path to ref fasta file, generated by samtools faidx\n"     \
           "  -o, --output FILE   Path to output vcf file. if not set, output to stdout\n"    \
           "  -h, --help          Print this message\n"                                       \
           "\n"
    fp.write(msg)

def fixref(argv):
    # parse and check command line
    if len(argv) < 3:
        __usage(sys.stderr)
        sys.exit(1)
           
    opts, args = getopt.getopt(argv[2:], "-h-i:-r:-o:", ["help", "input=", "ref=", "output="])
    ref_file = in_vcf_file = out_vcf_file = None
    for op, val in opts:
        if op in ("-i", "--input"): in_vcf_file = val
        elif op in ("-r", "--ref"): ref_file = val
        elif op in ("-o", "--output"): out_vcf_file = val
        elif op in ("-h", "--help"): __usage(sys.stderr); sys.exit(1)
        else: sys.stderr.write("invalid option: %s\n" % op); sys.exit(1)

    # TODO: check args
    
    __fix_file(in_vcf_file, out_vcf_file, ref_file)

if __name__ == "__main__":
    fixref(sys.argv)

