import os
import argparse
from DistributeManager import *

if "RAZZLE_ROOT" not in os.environ:
    os.environ["RAZZLE_ROOT"] = os.path.join(os.path.dirname(os.path.realpath(__file__)))

if __name__ == "__main__":
    parse = argparse.ArgumentParser()
    parse.add_argument("-I", "--input", dest="input", required=True, help="input hjson")
    parse.add_argument(
        "-O", "--output", dest="output", required=True, help="output of the fuzz code"
    )
    parse.add_argument(
        "-V",
        "--virtual",
        dest="virtual",
        action="store_true",
        help="link in virtual address",
    )
    parse.add_argument(
        "--fuzz", dest="do_fuzz", action="store_true", help="payload generate by fuzz"
    )
    parse.add_argument(
        "--debug", dest="debug", action="store_true", help="the code can print some debug info"
    )
    parse.add_argument(
        "--rtl_sim", dest="rtl_sim", help="the path of the rtl simulation workspace"
    )
    parse.add_argument(
        "--rtl_sim_mode", dest="rtl_sim_mode", help="the mode of the rtl simulation, must be vlt or vcs"
    )
    parse.add_argument(
        "--taint_log", dest="taint_log", help="the path of the taint log file"
    )
    parse.add_argument(
        "--repo_path", dest="repo_path", help="the path of the trigger and leak reposity"
    )

    args = parse.parse_args()
    args.output = os.path.realpath(args.output)

    if not os.path.exists(args.output):
        os.makedirs(args.output)

    dist = DistributeManager(args.input, args.output, args.virtual,\
        args.do_fuzz, args.debug, args.rtl_sim, args.rtl_sim_mode, args.taint_log,\
        args.repo_path)
    dist.fuzz_stage1()
