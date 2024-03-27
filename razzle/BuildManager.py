from SectionManager import *
from SectionUtils import *

class ShellCommand:
    def __init__(self, cmd, args=[]):
        self.args = [cmd]
        self.args.extend(args)

    def add_options(self, extra_args=[]):
        self.args.extend(extra_args)

    def generate(self, extra_args=[]):
        return " ".join(self.args + extra_args)


class BuildManager:
    def __init__(self, env_var, file_name, shell="/bin/zsh"):
        self.shell = shell
        self.file_name = file_name
        self.env_var = env_var
        self.build_cmds = []

    def _save_file(self):
        with open(self.file_name, "wt") as f:
            f.write(f"#!{self.shell}\n")
            # exit if any command fails
            f.write("set -e\n")

            for env, val in self.env_var.items():
                f.write(f"export {env}={val}\n")

            for cmd in self.build_cmds:
                f.write(cmd + "\n")

    def add_cmd(self, cmd):
        self.build_cmds.append(cmd)
    
    def add_env(self, env, val):
        self.env_var[env] = val

    def run(self, cmd=None):
        if cmd is not None:
            self.build_cmds.append(cmd)

        self.add_cmd("echo Build Done")

        self._save_file()
        os.system(f"chmod +x {self.file_name}")
        os.system(f"{self.file_name}")
