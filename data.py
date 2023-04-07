import bpy


def refresh():
    IfcGitData.is_loaded = False


class IfcGitData:

    data = {}
    is_loaded = False

    data["repo"] = None
    data["branch_names"] = []

    @classmethod
    def load(cls):
        cls.data = {
            "repo": cls.repo(),
            "branch_names": cls.branch_names(),
            "path_ifc": cls.path_ifc(),
        }
        cls.is_loaded = True

    @classmethod
    def repo(cls):
        pass

    @classmethod
    def branch_names(cls):
        pass

    @classmethod
    def path_ifc(cls):
        return bpy.data.scenes["Scene"].BIMProperties.ifc_file
