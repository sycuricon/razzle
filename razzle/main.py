import os
import argparse
from DistributeManager import *

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

    args = parse.parse_args()
    if not os.path.exists(args.output):
        os.makedirs(args.output)
    dist = DistributeManager(args.input, args.output, args.virtual, args.do_fuzz)
    dist.generate_test()
