from SectionManager import *
from SectionUtils import *

class ShellCommand:
    def __init__(self, cmd, args=[]):
        self.args = [cmd]
        self.args.extend(args)

    def add_options(self, extra_args=[]):
        self.args.extend(extra_args)

    def save_cmd(self, extra_args=[]):
        return " ".join(self.args + extra_args)

    def save_output(self, name, extra_args=[]):
        return f"{name}=$({self.save_cmd(extra_args)})"


class BuildManager:
    def __init__(self, env_var, output_path, shell="/bin/zsh", file_name = "build.sh"):
        self.shell = shell
        self.output_path = output_path
        self.file_name = os.path.join(output_path, file_name)
        self.reset_time = 0
        self.env_var = env_var
        self.build_cmds = []

    def _save_file(self):
        with open(self.file_name, "wt") as f:
            f.write(f"#!{self.shell}\n")
            # exit if any command fails
            f.write("set -e -x\n")

            for env, val in self.env_var.items():
                f.write(f"export {env}={val}\n")
            f.write(f"export OUTPUT_PATH={self.output_path}\n")
            
            f.write(f"cd $OUTPUT_PATH\n")
            for cmd in self.build_cmds:
                f.write(cmd + "\n")

    def add_cmd(self, cmd):
        self.build_cmds.append(cmd)
    
    def add_env(self, env, val):
        self.env_var[env] = val
    
    def reset(self):
        self.build_cmds = []
        self.reset_time += 1
        self.file_name = os.path.join(self.output_path, f"build_{self.reset_time}.sh")

    def run(self, cmd=None):
        if cmd is not None:
            self.build_cmds.append(cmd)

        self.add_cmd(f'echo "[*] Script {self.file_name} done"')

        self._save_file()
        os.system(f"chmod +x {self.file_name}")
        if os.system(f"{self.file_name}") != 0:
            raise Exception(f'{self.file_name} execution fails')
