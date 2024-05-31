import argparse
import os
import matplotlib.pyplot as plt

def coverage_draw(curve_fuzz):
    cov_inc = [0]
    for line in open(curve_fuzz, "rt"):
        if line.startswith("inc coverage:"):
            cov_inc.append(int(line.split()[-1])+cov_inc[-1])
    curve_folder = os.path.dirname(curve_fuzz)
    plt.plot(cov_inc)
    plt.savefig(os.path.join(curve_folder, 'coverage.png'))

if __name__ == "__main__":
    parse = argparse.ArgumentParser(description="draw the curve of the coverage inc")
    parse.add_argument("--input", "-I", dest="input", required=True, help="curve file")
    args = parse.parse_args()

    coverage_draw(args.input)