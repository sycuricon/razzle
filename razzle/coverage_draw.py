import argparse
import os
import matplotlib.pyplot as plt

def coverage_draw(curve_fuzz):
    cov_inc = [0]
    cov_time = [0]
    trigger_mutate = []
    access_mutate = []
    state = None
    for line in open(curve_fuzz, "rt"):
        line_token = line.split()
        log_time = float(line_token[0])
        log_type = line_token[1]
        log_info = line_token[2:]
        match log_type:
            case 'inc_coverage':
                if state != '[FuzzFSM.MUTATE_ACCESS]':
                    new_cov_inc = int(log_info[-1])
                    cov_inc.append(cov_inc[-1]+new_cov_inc)
                    cov_time.append(log_time)
            case 'state_switch':
                from_state = log_info[0]
                to_state = log_info[2]
                state = to_state
                if to_state == '[FuzzFSM.MUTATE_TRIGGER]':
                    trigger_mutate.append(log_time)
                elif to_state == '[FuzzFSM.MUTATE_ACCESS]':
                    access_mutate.append(log_time)
    curve_folder = os.path.dirname(curve_fuzz)
    plt.plot(cov_time, cov_inc)

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