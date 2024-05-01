import os
import argparse
from DistributeManager import *

if "RAZZLE_ROOT" not in os.environ:
    os.environ["RAZZLE_ROOT"] = os.path.join(os.path.dirname(os.path.realpath(__file__)))

def genonly_entry(args):
    dist = DistributeManager(args.input, args.output, args.virtual, args.do_fuzz, args.debug)
    dist.generate()

def stage1_entry(args):
    dist = DistributeManager(args.input, args.output, args.virtual, args.do_fuzz, args.debug)
    dist.fuzz_stage1(args.rtl_sim, args.rtl_sim_mode, args.taint_log, args.repo_path, do_fuzz=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(required=True)

    parser.add_argument("-I", "--input", dest="input", required=True, help="input hjson")
    parser.add_argument(
        "-O", "--output", dest="output", required=True, help="output of the fuzz code"
    )
    parser.add_argument(
        "-V",
        "--virtual",
        dest="virtual",
        action="store_true",
        help="link in virtual address",
    )
    parser.add_argument(
        "--fuzz", dest="do_fuzz", action="store_true", help="payload generate by fuzz"
    )
    parser.add_argument(
        "--debug", dest="debug", action="store_true", help="the code can print some debug info"
    )

    parser_genonly = subparsers.add_parser('generate', aliases=['gen'])
    parser_genonly.set_defaults(func=genonly_entry)

    parser_stage1 = subparsers.add_parser('stage1', aliases=['s1'])
    parser_stage1.set_defaults(func=stage1_entry)
    parser_stage1.add_argument(
        "--rtl_sim", dest="rtl_sim", help="the path of the rtl simulation workspace"
    )
    parser_stage1.add_argument(
        "--rtl_sim_mode", dest="rtl_sim_mode", help="the mode of the rtl simulation, must be vlt or vcs"
    )
    parser_stage1.add_argument(
        "--taint_log", dest="taint_log", help="the path of the taint log file"
    )
    parser_stage1.add_argument(
        "--repo_path", dest="repo_path", help="the path of the trigger and leak reposity"
    )

    args = parser.parse_args()
    args.output = os.path.realpath(args.output)

    if not os.path.exists(args.output):
        os.makedirs(args.output)
    
    args.func(args)
