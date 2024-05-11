import os
import argparse
from FuzzManager import *

if "RAZZLE_ROOT" not in os.environ:
    os.environ["RAZZLE_ROOT"] = os.path.join(os.path.dirname(os.path.realpath(__file__)))

def genonly_entry(args):
    fuzz = FuzzManager(args.input, args.output, args.virtual)
    fuzz.generate()

def load_entry(args):
    fuzz = FuzzManager(args.input, args.output, args.virtual)
    fuzz.load_example(args.rtl_sim, args.rtl_sim_mode, args.taint_log, args.repo_path, args.iter_num)

def fuzz_entry(args):
    fuzz = FuzzManager(args.input, args.output, args.virtual)
    fuzz.fuzz(args.rtl_sim, args.rtl_sim_mode, args.taint_log, args.repo_path)

def trigger_test_entry(args):
    fuzz = FuzzManager(args.input, args.output, args.virtual)
    fuzz.trigger_test(args.rtl_sim, args.rtl_sim_mode, args.taint_log, args.repo_path)

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

    parser_load = subparsers.add_parser('load')
    parser_load.set_defaults(func=load_entry)
    parser_load.add_argument(
        "--rtl_sim", dest="rtl_sim", help="the path of the rtl simulation workspace"
    )
    parser_load.add_argument(
        "--rtl_sim_mode", dest="rtl_sim_mode", help="the mode of the rtl simulation, must be vlt or vcs"
    )
    parser_load.add_argument(
        "--taint_log", dest="taint_log", help="the path of the taint log file"
    )
    parser_load.add_argument(
        "--repo_path", dest="repo_path", help="the path of the trigger and leak reposity"
    )
    parser_load.add_argument(
        "--iter_num", dest="iter_num", help="the index of the leak template repo"
    )

    parser_trigger_test = subparsers.add_parser('trigger_test')
    parser_trigger_test.set_defaults(func=trigger_test_entry)
    parser_trigger_test.add_argument(
        "--rtl_sim", dest="rtl_sim", help="the path of the rtl simulation workspace"
    )
    parser_trigger_test.add_argument(
        "--rtl_sim_mode", dest="rtl_sim_mode", help="the mode of the rtl simulation, must be vlt or vcs"
    )
    parser_trigger_test.add_argument(
        "--taint_log", dest="taint_log", help="the path of the taint log file"
    )
    parser_trigger_test.add_argument(
        "--repo_path", dest="repo_path", help="the path of the trigger and leak reposity"
    )
    parser_trigger_test.add_argument(
        "--iter_num", dest="iter_num", help="the index of the leak template repo"
    )
    

    args = parser.parse_args()
    args.output = os.path.realpath(args.output)

    if not os.path.exists(args.output):
        os.makedirs(args.output)
    
    args.func(args)
