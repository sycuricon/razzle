import os
import argparse
from FuzzMachine import *

if "RAZZLE_ROOT" not in os.environ:
    os.environ["RAZZLE_ROOT"] = os.path.join(os.path.dirname(os.path.realpath(__file__)))

def genonly_entry(args):
    fuzz = FuzzMachine(args.input, args.output, args.prefix)
    fuzz.generate()

def fuzz_entry(args):
    fuzz = FuzzMachine(args.input, args.output, args.prefix)
    fuzz.fuzz(args.rtl_sim, args.rtl_sim_mode, args.taint_log, args.repo_path, int(args.thread_num))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(required=True)

    parser.add_argument("-I", "--input", dest="input", required=True, help="input hjson")
    parser.add_argument(
        "-O", "--output", dest="output", required=True, help="output of the fuzz code"
    )
    parser.add_argument("--prefix", dest="prefix", required=True, help="the prefix of the generate_file")

    parser_genonly = subparsers.add_parser('generate', aliases=['gen'])
    parser_genonly.set_defaults(func=genonly_entry)

    parser_fuzz = subparsers.add_parser('fuzz')
    parser_fuzz.set_defaults(func=fuzz_entry)
    parser_fuzz.add_argument(
        "--rtl_sim", dest="rtl_sim", help="the path of the rtl simulation workspace"
    )
    parser_fuzz.add_argument(
        "--rtl_sim_mode", dest="rtl_sim_mode", help="the mode of the rtl simulation, must be vlt or vcs"
    )
    parser_fuzz.add_argument(
        "--taint_log", dest="taint_log", help="the path of the taint log file"
    )
    parser_fuzz.add_argument(
        "--repo_path", dest="repo_path", help="the path of the trigger and leak reposity"
    )
    parser_fuzz.add_argument(
        "--thread_num", dest="thread_num", help="the thread of the leak"
    )
    
    args = parser.parse_args()
    args.output = os.path.realpath(args.output)

    if not os.path.exists(args.output):
        os.makedirs(args.output)
    
    args.func(args)
