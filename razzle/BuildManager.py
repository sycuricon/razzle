from SectionManager import *
from SectionUtils import *


class FileSection(Section):
    def __init__(self, name, flag, link):
        super().__init__(name, flag)
        self.link = link


class FileManager(SectionManager):
    def __init__(self, config):
        super().__init__(config)
        self.folder = config["folder"]
        self.file = config["file"]

    def _generate_sections(self):
        pass

    def file_generate(self, path, name):
        self._generate_sections()
        self._distribute_address()

        filename = []
        for folder in self.folder:
            folder = os.path.join(os.environ["RAZZLE_ROOT"], folder)
            os.system("cp " + folder + "/* " + path)
            files = list(
                filter(
                    lambda filename: filename.endswith((".S", ".c")), os.listdir(folder)
                )
            )
            filename.extend(files)
        for file in self.file:
            file = os.path.join(os.environ["RAZZLE_ROOT"], file)
            os.system("cp " + file + " " + path)
            filename.append(os.path.basename(file))
        for i in range(len(filename)):
            filename[i] = os.path.join(path, filename[i])
        return [filename, filename]


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
