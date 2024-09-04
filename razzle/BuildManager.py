from typing import Optional
from SectionManager import *
from SectionUtils import *
import time

class ShellCommand:
    def __init__(self, cmd, args=[]):
        self.args = [cmd]
        self.args.extend(args)
        self._last_output = None

    def add_options(self, extra_args=[]):
        self.args.extend(extra_args)

    def gen_cmd(self, extra_args=[], output_option="", output_file=None):
        self._last_output = output_file
        cmd_seq = self.args + extra_args + ([output_option, output_file] if output_file is not None else [])
        return " ".join(cmd_seq)

    def gen_result(self, name, extra_args=[]):
        return f"{name}=$({self.gen_cmd(extra_args)})"

    @property
    def last_output(self):
        assert self._last_output is not None
        return self._last_output


class BuildManager:
    def __init__(self, env_var, output_path, shell="/bin/zsh", file_name = "build.sh"):
        self.shell = shell
        self.output_path = output_path
        self.final_script = os.path.join(output_path, file_name)
        self.reset_time = 0
        self.env_var = env_var
        self.build_cmds = []

    def replace_output(self, file_path):
        return file_path.replace("$OUTPUT_PATH", self.output_path)

    def save_script(self):
        with open(self.final_script, "wt") as f:
            f.write(f"#!{self.shell}\n")
            # exit if any command fails
            f.write("set -e -x\n")

            for env, val in self.env_var.items():
                f.write(f"export {env}={val}\n")
            f.write(f"export OUTPUT_PATH={self.output_path}\n")
            
            f.write(f"cd $OUTPUT_PATH\n")
            for cmd in self.build_cmds:
                f.write(cmd + "\n")

            os.system(f"chmod +x {self.final_script}")

    def add_cmd(self, cmd):
        self.build_cmds.append(cmd)
    
    def add_env(self, env, val):
        self.env_var[env] = val

    def add_subshell(self, sub):
        self.build_cmds.append(f"{self.shell} {sub.final_script}")

    def reset(self):
        self.build_cmds = []
        self.reset_time += 1
        self.final_script = os.path.join(self.output_path, f"build_{self.reset_time}.sh")

    def run(self, cmd=None):
        if cmd is not None:
            self.build_cmds.append(cmd)

        self.add_cmd(f'echo "[*] Script {self.final_script} done"')

        self.save_script()
        for _ in range(3):
            if os.system(f"{self.final_script}") != 0:
                time.sleep(10)
            else:
                break
        else:
            raise Exception('cannot handle this system call by delay')
