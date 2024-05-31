import argparse
import os
import matplotlib.pyplot as plt

def coverage_draw(curve_fuzz):
    cov_inc = [0]
    trigger_mutate = [0]
    access_mutate = []
    leak_mutate = []
    for line in open(curve_fuzz, "rt"):
        if line.startswith("inc coverage:"):
            cov_inc.append(int(line.split()[-1])+cov_inc[-1])
        elif line.startswith("state switch:"):
            _, _, state1, _, state2 = line.split()
            if state1 == '[FuzzFSM.MUTATE_LEAK]' and state2 == '[FuzzFSM.IDLE]' or\
                state1 == '[FuzzFSM.MUTATE_ACCESS]' and state2 == '[FuzzFSM.MUTATE_TRIGGER]':
                trigger_mutate.append(len(cov_inc))
            elif state1 == '[FuzzFSM.ACCUMULATE]' and state2 == '[FuzzFSM.MUTATE_ACCESS]':
                access_mutate.append(len(cov_inc))
            elif state1 == '[FuzzFSM.MUTATE_LEAK]' and state2 == '[FuzzFSM.ACCUMULATE]':
                leak_mutate.append(len(cov_inc))
    curve_folder = os.path.dirname(curve_fuzz)
    plt.plot(cov_inc)

    for line in leak_mutate:
        plt.axvline(line, color='red')
    for line in access_mutate:
        plt.axvline(line, color='green')
    for line in trigger_mutate:
        plt.axvline(line, color='blue')

    plt.savefig(os.path.join(curve_folder, 'coverage.png'))

if __name__ == "__main__":
    parse = argparse.ArgumentParser(description="draw the curve of the coverage inc")
    parse.add_argument("--input", "-I", dest="input", required=True, help="curve file")
    args = parse.parse_args()

    coverage_draw(args.input)