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
