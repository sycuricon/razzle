import logging
import argparse
from snapshot import *

if __name__ == "__main__":
    parse = argparse.ArgumentParser(description="RVSnap is a RISC-V processor snapshot generator with a user-friendly interface that allows editing in JSON format.")
    parse.add_argument("-I", "--input", dest="input", required=True, help="input json")
    parse.add_argument("-O", "--output", dest="output", help="output file")
    parse.add_argument("-f", "--format", dest="format", default="hex", help="snapshot format")
    parse.add_argument("-d", "--debug", dest="debug", action="store_true", help="enable debug mode")
    args = parse.parse_args()

    if args.output is None:
        args.output = f"default.{args.format}"
    
    if args.debug is not None:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    design = RISCVSnapshot("rv64gc", 8, SUPPORTED_CSR)
    design.load_snapshot(args.input)
    design.save(args.output, format="hex", output_width=64)
