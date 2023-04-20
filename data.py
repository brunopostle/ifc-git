import bpy
import tool
import blenderbim.tool as btool


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
            "branches_by_hexsha": cls.branches_by_hexsha(),
            "tags_by_hexsha": cls.tags_by_hexsha()
        }
        cls.is_loaded = True

    @classmethod
    def repo(cls):
        path_ifc = btool.Ifc.get_path()
        print("@@@@", path_ifc)
        return tool.IfcGit.repo_from_path(path_ifc)
        pass

    @classmethod
    def branch_names(cls):
        pass

    @classmethod
    def path_ifc(cls):
        return btool.Ifc.get_path()

    @classmethod
    def branches_by_hexsha(cls):
        return tool.IfcGit.branches_by_hexsha(tool.IfcGitRepo.repo)
    
    @classmethod
    def tags_by_hexsha(cls):
        return tool.IfcGit.tags_by_hexsha(tool.IfcGitRepo.repo)
