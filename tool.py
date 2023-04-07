import os
import re
import git
import bpy
from blenderbim.bim.ifc import IfcStore
import blenderbim.tool

from data import IfcGit


def is_valid_ref_format(string):
    """Check a bare branch or tag name is valid"""

    return re.match(
        "^(?!\.| |-|/)((?!\.\.)(?!.*/\.)(/\*|/\*/)*(?!@\{)[^\~\:\^\\\ \?*\[])+(?<!\.|/)(?<!\.lock)$",
        string,
    )


def load_project(path_ifc):
    """Clear and load an ifc project"""

    IfcStore.purge()
    # delete any IfcProject/* collections
    for collection in bpy.data.collections:
        if re.match("^IfcProject/", collection.name):
            delete_collection(collection)
    bpy.data.orphans_purge(do_recursive=True)

    bpy.ops.bim.load_project(filepath=path_ifc)
    bpy.ops.ifcgit.refresh()


def repo_from_path(path):
    """Returns a Git repository object or None"""

    if os.path.isdir(path):
        path_dir = os.path.abspath(path)
    elif os.path.isfile(path):
        path_dir = os.path.abspath(os.path.dirname(path))
    else:
        return None

    if IfcGit.repo != None and IfcGit.repo.working_dir == path_dir:
        return IfcGit.repo

    try:
        repo = git.Repo(path_dir)
    except:
        parentdir_path = os.path.abspath(os.path.join(path_dir, os.pardir))
        if parentdir_path == path_dir:
            # root folder
            return None
        return repo_from_path(parentdir_path)
    if repo:
        IfcGit.repo = repo
    return repo


def branches_by_hexsha(repo):
    """reverse lookup for branches"""

    result = {}
    for branch in repo.branches:
        if branch.commit.hexsha in result:
            result[branch.commit.hexsha].append(branch)
        else:
            result[branch.commit.hexsha] = [branch]
    return result


def tags_by_hexsha(repo):
    """reverse lookup for tags"""

    result = {}
    for tag in repo.tags:
        if tag.commit.hexsha in result:
            result[tag.commit.hexsha].append(tag)
        else:
            result[tag.commit.hexsha] = [tag]
    return result


def git_branches(self, context):
    """branches enum"""

    # NOTE "Python must keep a reference to the strings returned by
    # the callback or Blender will misbehave or even crash"
    IfcGit.branch_names = sorted([branch.name for branch in IfcGit.repo.heads])

    if "main" in IfcGit.branch_names:
        IfcGit.branch_names.remove("main")
        IfcGit.branch_names = ["main"] + IfcGit.branch_names

    return [(myname, myname, myname) for myname in IfcGit.branch_names]


def update_revlist(self, context):
    """wrapper to trigger update of the revision list"""

    bpy.ops.ifcgit.refresh()
    context.scene.commit_index = 0


def ifc_diff_ids(repo, hash_a, hash_b, path_ifc):
    """Given two revision hashes and a filename, retrieve"""
    """step-ids of modified, added and removed entities"""

    # NOTE this is calling the git binary in a subprocess
    if not hash_a:
        diff_lines = repo.git.diff(hash_b, path_ifc).split("\n")
    else:
        diff_lines = repo.git.diff(hash_a, hash_b, path_ifc).split("\n")

    inserted = set()
    deleted = set()
    for line in diff_lines:
        re_search = re.search(r"^\+#([0-9]+)=", line)
        if re_search:
            inserted.add(int(re_search.group(1)))
            continue
        re_search = re.search(r"^-#([0-9]+)=", line)
        if re_search:
            deleted.add(int(re_search.group(1)))

    modified = inserted.intersection(deleted)

    return {
        "modified": modified,
        "added": inserted.difference(modified),
        "removed": deleted.difference(modified),
    }


def get_modified_shape_object_step_ids(step_ids):
    model = blenderbim.tool.Ifc.get()
    modified_shape_object_step_ids = {"modified": []}

    for step_id in step_ids["modified"]:
        if model.by_id(step_id).is_a() == "IfcProductDefinitionShape":
            product = model.by_id(step_id).ShapeOfProduct[0]
            modified_shape_object_step_ids["modified"].append(product.id())

    return modified_shape_object_step_ids


def colourise(step_ids):
    area = next(area for area in bpy.context.screen.areas if area.type == "VIEW_3D")
    area.spaces[0].shading.color_type = "OBJECT"

    for obj in bpy.context.visible_objects:
        if not obj.BIMObjectProperties.ifc_definition_id:
            continue
        step_id = obj.BIMObjectProperties.ifc_definition_id
        if step_id in step_ids["modified"]:
            obj.color = (0.3, 0.3, 1.0, 1)
        elif step_id in step_ids["added"]:
            obj.color = (0.2, 0.8, 0.2, 1)
        elif step_id in step_ids["removed"]:
            obj.color = (1.0, 0.2, 0.2, 1)
        else:
            obj.color = (1.0, 1.0, 1.0, 0.5)


def delete_collection(blender_collection):
    for obj in blender_collection.objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.collections.remove(blender_collection)
    for collection in bpy.data.collections:
        if not collection.users:
            bpy.data.collections.remove(collection)
