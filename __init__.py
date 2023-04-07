import os
import sys
import re
import git
import bpy
import time
from blenderbim.bim.ifc import IfcStore
import blenderbim.tool as tool

sys.path.insert(0, "/home/bruno/src/ifc-git")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import operators
from operators import (
    AddFileToRepo,
    CommitChanges,
    CreateRepo,
    DiscardUncommitted,
    DisplayRevision,
    DisplayUncommitted,
    Merge,
    RefreshGit,
    SwitchRevision,
)
import ui
from ui import IFCGIT_PT_panel

# import ui, prop, operator

classes = (
    operators.AddFileToRepo,
    operators.CommitChanges,
    operators.CreateRepo,
    operators.DiscardUncommitted,
    operators.DisplayRevision,
    operators.DisplayUncommitted,
    operators.Merge,
    operators.RefreshGit,
    operators.SwitchRevision,
    ui.IFCGIT_PT_panel,
)

bl_info = {
    "name": "IFC Git",
    "author": "Bruno Postle",
    "location": "Scene > IFC Git",
    "description": "Manage IFC files in Git repositories",
    "blender": (2, 80, 0),
    "category": "Import-Export",
}

#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# 2023 Bruno Postle <bruno@postle.net>


class ListItem(bpy.types.PropertyGroup):
    """Group of properties representing an item in the list."""

    hexsha: bpy.props.StringProperty(
        name="Git hash",
        description="checksum for this commit",
        default="Uncommitted data!",
    )
    relevant: bpy.props.BoolProperty(
        name="Is relevant",
        description="does this commit reference our ifc file",
        default=False,
    )


class COMMIT_UL_List(bpy.types.UIList):
    """List of Git commits"""

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):

        current_revision = ifcgit_repo.commit()
        commit = ifcgit_repo.commit(rev=item.hexsha)

        lookup = branches_by_hexsha(ifcgit_repo)
        refs = ""
        if item.hexsha in lookup:
            for branch in lookup[item.hexsha]:
                if branch.name == context.scene.display_branch:
                    refs = "[" + branch.name + "] "

        lookup = tags_by_hexsha(ifcgit_repo)
        if item.hexsha in lookup:
            for tag in lookup[item.hexsha]:
                refs += "{" + tag.name + "} "

        if commit == current_revision:
            layout.label(
                text="[HEAD] " + refs + commit.message, icon="DECORATE_KEYFRAME"
            )
        else:
            layout.label(text=refs + commit.message, icon="DECORATE_ANIMATE")
        layout.label(text=time.strftime("%c", time.localtime(commit.committed_date)))


# FUNCTIONS


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

    if (
        "ifcgit_repo" in globals()
        and ifcgit_repo != None
        and ifcgit_repo.working_dir == path_dir
    ):
        return ifcgit_repo

    try:
        repo = git.Repo(path_dir)
    except:
        parentdir_path = os.path.abspath(os.path.join(path_dir, os.pardir))
        if parentdir_path == path_dir:
            # root folder
            return None
        return repo_from_path(parentdir_path)
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
    global ifcgit_branch_names
    ifcgit_branch_names = sorted([branch.name for branch in ifcgit_repo.heads])

    if "main" in ifcgit_branch_names:
        ifcgit_branch_names.remove("main")
        ifcgit_branch_names = ["main"] + ifcgit_branch_names

    return [(myname, myname, myname) for myname in ifcgit_branch_names]


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
    model = tool.Ifc.get()
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


def register():
    bpy.utils.register_class(IFCGIT_PT_panel)
    bpy.utils.register_class(ListItem)
    bpy.utils.register_class(COMMIT_UL_List)
    bpy.utils.register_class(CreateRepo)
    bpy.utils.register_class(AddFileToRepo)
    bpy.utils.register_class(DiscardUncommitted)
    bpy.utils.register_class(CommitChanges)
    bpy.utils.register_class(RefreshGit)
    bpy.utils.register_class(DisplayRevision)
    bpy.utils.register_class(DisplayUncommitted)
    bpy.utils.register_class(SwitchRevision)
    bpy.utils.register_class(Merge)
    bpy.types.Scene.ifcgit_commits = bpy.props.CollectionProperty(type=ListItem)
    bpy.types.Scene.commit_index = bpy.props.IntProperty(
        name="Index for my_list", default=0
    )
    bpy.types.Scene.commit_message = bpy.props.StringProperty(
        name="Commit message",
        description="A human readable description of these changes",
        default="",
    )
    bpy.types.Scene.new_branch_name = bpy.props.StringProperty(
        name="New branch name",
        description="A short name used to refer to this branch",
        default="",
    )
    bpy.types.Scene.display_branch = bpy.props.EnumProperty(
        items=git_branches, update=update_revlist
    )
    bpy.types.Scene.ifcgit_filter = bpy.props.EnumProperty(
        items=[
            ("all", "All", "All revisions"),
            ("tagged", "Tagged", "Tagged revisions"),
            ("relevant", "Relevant", "Revisions for this project"),
        ],
        update=update_revlist,
    )


def unregister():
    del bpy.types.Scene.ifcgit_commits
    del bpy.types.Scene.commit_index
    del bpy.types.Scene.commit_message
    del bpy.types.Scene.new_branch_name
    del bpy.types.Scene.display_branch
    del bpy.types.Scene.ifcgit_filter
    bpy.utils.unregister_class(IFCGIT_PT_panel)
    bpy.utils.unregister_class(ListItem)
    bpy.utils.unregister_class(COMMIT_UL_List)
    bpy.utils.unregister_class(CreateRepo)
    bpy.utils.unregister_class(AddFileToRepo)
    bpy.utils.unregister_class(DiscardUncommitted)
    bpy.utils.unregister_class(CommitChanges)
    bpy.utils.unregister_class(RefreshGit)
    bpy.utils.unregister_class(DisplayRevision)
    bpy.utils.unregister_class(DisplayUncommitted)
    bpy.utils.unregister_class(SwitchRevision)
    bpy.utils.unregister_class(Merge)


if __name__ == "__main__":
    register()
