import os
import re
import git
import bpy
import time
from blenderbim.bim.ifc import IfcStore

bl_info = {
    "name": "IFC git",
    "author": "Bruno Postle",
    "location": "Scene > IFC git",
    "description": "Manage IFC files in git",
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

# GUI CLASSES


class IfcGitPanel(bpy.types.Panel):
    """Scene Properties panel to interact with IFC repository data"""

    bl_label = "IFC Git"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    def draw(self, context):
        layout = self.layout
        path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
        # FIXME
        global ifcgit_repo

        # FIXME if file isn't saved, offer to save to disk

        row = layout.row()
        if path_ifc:
            ifcgit_repo = repo_from_ifc_path(path_ifc)
            name_ifc = os.path.basename(path_ifc)
            if ifcgit_repo:
                row.label(text=ifcgit_repo.working_dir, icon="SYSTEM")
                if name_ifc in ifcgit_repo.untracked_files:
                    row.operator(
                        "ifcgit.addfile",
                        text="Add '" + name_ifc + "' to repository",
                        icon="FILE",
                    )
                    return
                else:
                    row.label(text=name_ifc, icon="FILE")
            else:
                row.operator("ifcgit.createrepo", icon="SYSTEM")
                row.label(text=name_ifc, icon="FILE")
                return
        else:
            row.label(text="No git repository found", icon="SYSTEM")
            row.label(text="No IFC project loaded or saved", icon="FILE")
            return

        if ifcgit_repo.is_dirty(path=path_ifc):
            row = layout.row()
            row.label(text="Saved changes have not been committed", icon="ERROR")

            row = layout.row()
            row.operator("ifcgit.display_uncommitted", icon="SELECT_DIFFERENCE")
            row.operator("ifcgit.discard", icon="TRASH")

            if ifcgit_repo.head.is_detached:
                row = layout.row()
                row.label(
                    text="HEAD is detached, commit will create a branch", icon="ERROR"
                )
                # FIXME committing a detached HEAD should create a branch
                # git branch my_branch; git checkout my_branch

            row = layout.row()
            context.scene.commit_message
            row.prop(context.scene, "commit_message")
            row = layout.row()
            row.operator("ifcgit.commit_changes", icon="GREASEPENCIL")

            return

        row = layout.row()
        # FIXME assumes branch is 'main'
        row.label(text="Showing branch: " + ifcgit_repo.branches[0].name)
        # FIXME should just be a side icon as only needed after external repo updates
        row.operator("ifcgit.refresh", icon="FILE_REFRESH")

        row = layout.row()
        row.template_list(
            "COMMIT_UL_List",
            "The_List",
            context.scene,
            "ifcgit_commits",
            context.scene,
            "commit_index",
        )

        item = context.scene.ifcgit_commits[context.scene.commit_index]
        commit = ifcgit_repo.commit(rev=item.hexsha)

        row = layout.row()
        row.label(text=commit.hexsha)
        if item.relevant:
            # FIXME don't show if selected is current HEAD
            row.operator("ifcgit.display_revision", icon="SELECT_DIFFERENCE")
            row.operator("ifcgit.switch_revision", icon="FILE_TICK")
        else:
            row.label(text="Revision unrelated to current IFC", icon="ERROR")
        row = layout.row()
        row.label(text=commit.author.name + " <" + commit.author.email + ">")
        row = layout.row()
        row.label(text=commit.message)


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
    """List of git commits"""

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):

        # FIXME selecting a commit should call DisplayRevision operator without Show diff button
        current_revision = ifcgit_repo.commit()
        commit = ifcgit_repo.commit(rev=item.hexsha)
        if commit == current_revision:
            layout.label(text="[HEAD] " + commit.message, icon="DECORATE_KEYFRAME")
        else:
            layout.label(text=commit.message, icon="DECORATE_ANIMATE")
        layout.label(text=time.asctime(time.gmtime(commit.committed_date)))


# OPERATORS


class CreateRepo(bpy.types.Operator):
    """Initialise a git repository"""

    bl_label = "Create Git repository"
    bl_idname = "ifcgit.createrepo"
    bl_options = {"REGISTER"}

    def execute(self, context):

        path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
        if not os.path.isfile(path_ifc):
            return None
        if repo_from_ifc_path(path_ifc):
            # repo already exists
            return
        path_dir = os.path.abspath(os.path.dirname(path_ifc))
        git.Repo.init(path_dir)

        return {"FINISHED"}


class AddFileToRepo(bpy.types.Operator):
    """Add a file to a repository"""

    bl_label = "Add file to repository"
    bl_idname = "ifcgit.addfile"
    bl_options = {"REGISTER"}

    def execute(self, context):

        path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
        if not os.path.isfile(path_ifc):
            return None
        repo = repo_from_ifc_path(path_ifc)
        repo.index.add(path_ifc)
        repo.index.commit(message="Added " + os.path.basename(path_ifc))
        bpy.ops.ifcgit.refresh()

        return {"FINISHED"}


class DiscardUncommitted(bpy.types.Operator):
    """Discard saved changes and update to HEAD"""

    bl_label = "Discard uncommitted changes"
    bl_idname = "ifcgit.discard"
    bl_options = {"REGISTER"}

    def execute(self, context):

        path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
        ifcgit_repo.git.checkout(path_ifc)

        IfcStore.purge()
        # delete any IfcProject/* collections
        for collection in bpy.data.collections:
            if re.match("^IfcProject/", collection.name):
                delete_collection(collection)

        bpy.ops.bim.load_project(filepath=path_ifc)
        bpy.ops.ifcgit.refresh()

        return {"FINISHED"}


class CommitChanges(bpy.types.Operator):
    """Commit current saved changes"""

    bl_label = "Commit changes"
    bl_idname = "ifcgit.commit_changes"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        if context.scene.commit_message == "Write your commit message here":
            return False
        return True

    def execute(self, context):

        path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
        ifcgit_repo.index.add(path_ifc)
        ifcgit_repo.index.commit(message=context.scene.commit_message)
        context.scene.commit_message = "Write your commit message here"
        bpy.ops.ifcgit.refresh()

        return {"FINISHED"}


class RefreshGit(bpy.types.Operator):
    """Update IFC Git panel"""

    bl_label = "Refresh revision history"
    bl_idname = "ifcgit.refresh"
    bl_options = {"REGISTER"}

    def execute(self, context):

        area = next(area for area in bpy.context.screen.areas if area.type == "VIEW_3D")
        area.spaces[0].shading.color_type = "MATERIAL"

        # ifcgit_commits is registered list widget
        context.scene.ifcgit_commits.clear()

        path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file

        # FIXME
        global ifcgit_repo
        ifcgit_repo = repo_from_ifc_path(path_ifc)
        global ifcgit_branch
        # ifcgit_branch = ifcgit_repo.active_branch

        commits = list(
            git.objects.commit.Commit.iter_items(
                # FIXME assumes current branch is 'main'
                repo=ifcgit_repo,
                rev=[ifcgit_repo.branches[0].name],
            )
        )
        commits_relevant = list(
            git.objects.commit.Commit.iter_items(
                # FIXME assumes current branch is 'main'
                repo=ifcgit_repo,
                rev=[ifcgit_repo.branches[0].name],
                paths=[path_ifc],
            )
        )

        for commit in commits:
            context.scene.ifcgit_commits.add()
            context.scene.ifcgit_commits[-1].hexsha = commit.hexsha
            if commit in commits_relevant:
                context.scene.ifcgit_commits[-1].relevant = True

        return {"FINISHED"}


class DisplayRevision(bpy.types.Operator):
    """Colourise objects by selected revision"""

    bl_label = "Show diff"
    bl_idname = "ifcgit.display_revision"
    bl_options = {"REGISTER"}

    def execute(self, context):

        path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
        item = context.scene.ifcgit_commits[context.scene.commit_index]

        selected_revision = ifcgit_repo.commit(rev=item.hexsha)
        current_revision = ifcgit_repo.commit()

        if current_revision.committed_date > selected_revision.committed_date:
            step_ids = ifc_diff_ids(
                ifcgit_repo, selected_revision.hexsha, current_revision.hexsha, path_ifc
            )
        else:
            step_ids = ifc_diff_ids(
                ifcgit_repo, current_revision.hexsha, selected_revision.hexsha, path_ifc
            )

        # FIXME showing diff against current revision should reset to MATERIAL colours
        colourise(step_ids)

        return {"FINISHED"}


class DisplayUncommitted(bpy.types.Operator):
    """Colourise uncommitted objects"""

    bl_label = "Show uncommitted changes"
    bl_idname = "ifcgit.display_uncommitted"
    bl_options = {"REGISTER"}

    def execute(self, context):

        path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
        step_ids = ifc_diff_ids(ifcgit_repo, None, "HEAD", path_ifc)
        colourise(step_ids)

        return {"FINISHED"}


class SwitchRevision(bpy.types.Operator):
    """Switches the repository to the given revision and reloads the IFC file"""

    bl_label = "Checkout revision"
    bl_idname = "ifcgit.switch_revision"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        if ifcgit_repo.is_dirty():
            return False
        return True

    def execute(self, context):

        path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
        item = context.scene.ifcgit_commits[context.scene.commit_index]

        # NOTE this is calling the git binary in a subprocess
        ifcgit_repo.git.checkout(item.hexsha)

        # FIXME switching to HEAD should reattach to 'main' branch

        IfcStore.purge()
        # delete any IfcProject/* collections
        for collection in bpy.data.collections:
            if re.match("^IfcProject/", collection.name):
                delete_collection(collection)

        bpy.ops.bim.load_project(filepath=path_ifc)
        bpy.ops.ifcgit.refresh()
        # context.scene.commit_index = 0

        return {"FINISHED"}


# FUNCTIONS


def repo_from_ifc_path(path_ifc):
    """Returns a Git repository object or None"""
    # FIXME doesn't work if IFC is in a sub-folder

    if not os.path.isfile(path_ifc):
        return None
    path_dir = os.path.abspath(os.path.dirname(path_ifc))
    try:
        repo = git.Repo(path_dir)
    except:
        return None
    return repo


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
    bpy.utils.register_class(IfcGitPanel)
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
    bpy.types.Scene.ifcgit_commits = bpy.props.CollectionProperty(type=ListItem)
    bpy.types.Scene.commit_index = bpy.props.IntProperty(
        name="Index for my_list", default=0
    )
    bpy.types.Scene.commit_message = bpy.props.StringProperty(
        name="Commit message",
        description="A human readable description of these changes",
        default="Write your commit message here",
    )


def unregister():
    del bpy.types.Scene.ifcgit_commits
    del byp.types.Scene.commit_index
    del bpy.types.Scene.commit_message
    bpy.utils.unregister_class(IfcGitPanel)
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


if __name__ == "__main__":
    register()
