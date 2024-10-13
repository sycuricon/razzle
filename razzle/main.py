import os
import argparse
from FuzzMachine import *

if "RAZZLE_ROOT" not in os.environ:
    os.environ["RAZZLE_ROOT"] = os.path.join(os.path.dirname(os.path.realpath(__file__)))

def genonly_entry(args):
    fuzz = FuzzMachine(args.input, args.output, args.prefix, args.core, args.rand_seed)
    fuzz.generate()

def compile_entry(args):
    fuzz = FuzzMachine(args.input, args.output, args.prefix, args.core, args.rand_seed)
    fuzz.offline_compile(args.mem_cfg)

def analysis_entry(args):
    fuzz = FuzzMachine(args.input, args.output, args.prefix, args.core, args.rand_seed)
    fuzz.fuzz_analysis(args.thread_num)

def fuzz_entry(args):
    fuzz = FuzzMachine(args.input, args.output, args.prefix, args.core, args.rand_seed)
    fuzz.fuzz(args.rtl_sim, args.rtl_sim_mode, args.taint_log, args.fuzz_mode, int(args.thread_num))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(required=True)

    parser.add_argument("-I", "--input", dest="input", required=True, help="input hjson")
    parser.add_argument(
        "-O", "--output", dest="output", required=True, help="output of the fuzz code"
    )
    parser.add_argument("--prefix", dest="prefix", required=True, help="the prefix of the generate_file")
    parser.add_argument("--core", dest="core", required=True , help="the type of core")
    parser.add_argument("--rand_seed", dest="rand_seed", help="the random seed for fuzz geenrate")

    parser_genonly = subparsers.add_parser('generate', aliases=['gen'])
    parser_genonly.set_defaults(func=genonly_entry)

    parser_compile = subparsers.add_parser('compile')
    parser_compile.set_defaults(func=compile_entry)
    parser_compile.add_argument(
        "--mem_cfg", dest="mem_cfg", help="the path of the mem_cfg to be compiled"
    )

    parser_analysis = subparsers.add_parser('analysis')
    parser_analysis.set_defaults(func=analysis_entry)
    parser_analysis.add_argument(
        "--thread_num", dest="thread_num", help="the thread of the leak"
    )

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
        "--thread_num", dest="thread_num", help="the thread of the leak"
    )
    parser_fuzz.add_argument(
        "--fuzz_mode", dest="fuzz_mode", help="fuzz for trigger, access or leak"
    )
    
    args = parser.parse_args()
    args.output = os.path.realpath(args.output)

    args.rand_seed = int(args.rand_seed)
    if args.rand_seed == 0:
        args.rand_seed = int(time.time())

    if not os.path.exists(args.output):
        os.makedirs(args.output)
    
    args.func(args)
