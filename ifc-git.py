import os
import re
import git
import bpy
import time
from blenderbim.bim.ifc import IfcStore

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

# GUI CLASSES


class IFCGIT_PT_panel(bpy.types.Panel):
    """Scene Properties panel to interact with IFC repository data"""

    bl_label = "IFC Git"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file

        # TODO if file isn't saved, offer to save to disk

        row = layout.row()
        if path_ifc:
            # FIXME
            global ifcgit_repo
            ifcgit_repo = repo_from_path(path_ifc)
            if ifcgit_repo:
                name_ifc = os.path.relpath(path_ifc, ifcgit_repo.working_dir)
                row.label(text=ifcgit_repo.working_dir, icon="SYSTEM")
                if name_ifc in ifcgit_repo.untracked_files:
                    row.operator(
                        "ifcgit.addfile",
                        text="Add '" + name_ifc + "' to repository",
                        icon="FILE",
                    )
                else:
                    row.label(text=name_ifc, icon="FILE")
            else:
                row.operator(
                    "ifcgit.createrepo",
                    text="Create '" + os.path.dirname(path_ifc) + "' repository",
                    icon="SYSTEM",
                )
                row.label(text=os.path.basename(path_ifc), icon="FILE")
                return
        else:
            row.label(text="No Git repository found", icon="SYSTEM")
            row.label(text="No IFC project saved", icon="FILE")
            return

        is_dirty = ifcgit_repo.is_dirty(path=path_ifc)

        if is_dirty:
            row = layout.row()
            row.label(text="Saved changes have not been committed", icon="ERROR")

            row = layout.row()
            row.operator("ifcgit.display_uncommitted", icon="SELECT_DIFFERENCE")
            row.operator("ifcgit.discard", icon="TRASH")

            row = layout.row()
            row.prop(context.scene, "commit_message")

            if ifcgit_repo.head.is_detached:
                row = layout.row()
                row.label(
                    text="HEAD is detached, commit will create a branch", icon="ERROR"
                )
                row.prop(context.scene, "new_branch_name")

            row = layout.row()
            row.operator("ifcgit.commit_changes", icon="GREASEPENCIL")

        row = layout.row()
        if ifcgit_repo.head.is_detached:
            row.label(text="Working branch: Detached HEAD")
        else:
            row.label(text="Working branch: " + ifcgit_repo.active_branch.name)

        grouped = layout.row()
        column = grouped.column()
        row = column.row()
        row.prop(bpy.context.scene, "display_branch", text="Browse branch")

        row = column.row()
        row.template_list(
            "COMMIT_UL_List",
            "The_List",
            context.scene,
            "ifcgit_commits",
            context.scene,
            "commit_index",
        )
        column = grouped.column()
        row = column.row()
        row.operator("ifcgit.refresh", icon="FILE_REFRESH")

        if not is_dirty:

            row = column.row()
            row.operator("ifcgit.display_revision", icon="SELECT_DIFFERENCE")

            row = column.row()
            row.operator("ifcgit.switch_revision", icon="CURRENT_FILE")

            # TODO operator to tag selected

            row = column.row()
            row.operator("ifcgit.merge", icon="EXPERIMENTAL", text="")

        if not context.scene.ifcgit_commits:
            return

        item = context.scene.ifcgit_commits[context.scene.commit_index]
        commit = ifcgit_repo.commit(rev=item.hexsha)

        if not item.relevant:
            row = layout.row()
            row.label(text="Revision unrelated to current IFC project", icon="ERROR")

        box = layout.box()
        column = box.column(align=True)
        row = column.row()
        row.label(text=commit.hexsha)
        row = column.row()
        row.label(text=commit.author.name + " <" + commit.author.email + ">")
        row = column.row()
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
    """List of Git commits"""

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):

        current_revision = ifcgit_repo.commit()
        commit = ifcgit_repo.commit(rev=item.hexsha)

        lookup = branches_by_hexsha(ifcgit_repo)
        branch_name = ""
        if item.hexsha in lookup:
            branch_name = "[" + lookup[item.hexsha].name + "] "
            # TODO also show tags

        if commit == current_revision:
            layout.label(
                text="[HEAD] " + branch_name + commit.message, icon="DECORATE_KEYFRAME"
            )
        else:
            layout.label(text=branch_name + commit.message, icon="DECORATE_ANIMATE")
        layout.label(text=time.strftime("%c", time.localtime(commit.committed_date)))


# OPERATORS


class CreateRepo(bpy.types.Operator):
    """Initialise a Git repository"""

    bl_label = "Create Git repository"
    bl_idname = "ifcgit.createrepo"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
        if not os.path.isfile(path_ifc):
            return False
        if repo_from_path(path_ifc):
            # repo already exists
            return False
        if re.match("^/home/[^/]+/?$", os.path.dirname(path_ifc)):
            # don't make ${HOME} a repo
            return False
        return True

    def execute(self, context):

        path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
        path_dir = os.path.abspath(os.path.dirname(path_ifc))
        git.Repo.init(path_dir)

        return {"FINISHED"}


class AddFileToRepo(bpy.types.Operator):
    """Add a file to a repository"""

    bl_label = "Add file to repository"
    bl_idname = "ifcgit.addfile"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
        if not os.path.isfile(path_ifc):
            return False
        if not repo_from_path(path_ifc):
            # repo doesn't exist
            return False
        return True

    def execute(self, context):

        path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
        repo = repo_from_path(path_ifc)
        repo.index.add(path_ifc)
        repo.index.commit(
            message="Added " + os.path.relpath(path_ifc, repo.working_dir)
        )

        bpy.ops.ifcgit.refresh()

        return {"FINISHED"}


class DiscardUncommitted(bpy.types.Operator):
    """Discard saved changes and update to HEAD"""

    bl_label = "Discard uncommitted changes"
    bl_idname = "ifcgit.discard"
    bl_options = {"REGISTER"}

    def execute(self, context):

        path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
        # NOTE this is calling the git binary in a subprocess
        ifcgit_repo.git.checkout(path_ifc)
        load_project(path_ifc)

        return {"FINISHED"}


class CommitChanges(bpy.types.Operator):
    """Commit current saved changes"""

    bl_label = "Commit changes"
    bl_idname = "ifcgit.commit_changes"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        if context.scene.commit_message == "":
            return False
        if ifcgit_repo.head.is_detached and (
            not is_valid_ref_format(context.scene.new_branch_name)
            or context.scene.new_branch_name
            in [branch.name for branch in ifcgit_repo.branches]
        ):
            return False
        return True

    def execute(self, context):

        path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
        ifcgit_repo.index.add(path_ifc)
        ifcgit_repo.index.commit(message=context.scene.commit_message)
        context.scene.commit_message = ""

        if ifcgit_repo.head.is_detached:
            new_branch = ifcgit_repo.create_head(context.scene.new_branch_name)
            new_branch.checkout()
            context.scene.display_branch = context.scene.new_branch_name
            context.scene.new_branch_name = ""

        bpy.ops.ifcgit.refresh()

        return {"FINISHED"}


class RefreshGit(bpy.types.Operator):
    """Refresh revision list"""

    bl_label = ""
    bl_idname = "ifcgit.refresh"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        if "ifcgit_repo" in globals() and ifcgit_repo != None and ifcgit_repo.heads:
            return True
        return False

    def execute(self, context):

        area = next(area for area in bpy.context.screen.areas if area.type == "VIEW_3D")
        area.spaces[0].shading.color_type = "MATERIAL"

        # ifcgit_commits is registered list widget
        context.scene.ifcgit_commits.clear()

        path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file

        commits = list(
            git.objects.commit.Commit.iter_items(
                repo=ifcgit_repo,
                rev=[context.scene.display_branch],
            )
        )
        commits_relevant = list(
            git.objects.commit.Commit.iter_items(
                repo=ifcgit_repo,
                rev=[context.scene.display_branch],
                paths=[path_ifc],
            )
        )

        # TODO option limit to relevant revisions/all revisions/tags/
        for commit in commits:
            context.scene.ifcgit_commits.add()
            context.scene.ifcgit_commits[-1].hexsha = commit.hexsha
            if commit in commits_relevant:
                context.scene.ifcgit_commits[-1].relevant = True

        return {"FINISHED"}


class DisplayRevision(bpy.types.Operator):
    """Colourise objects by selected revision"""

    bl_label = ""
    bl_idname = "ifcgit.display_revision"
    bl_options = {"REGISTER"}

    def execute(self, context):

        path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
        item = context.scene.ifcgit_commits[context.scene.commit_index]

        selected_revision = ifcgit_repo.commit(rev=item.hexsha)
        current_revision = ifcgit_repo.commit()

        if selected_revision == current_revision:
            area = next(
                area for area in bpy.context.screen.areas if area.type == "VIEW_3D"
            )
            area.spaces[0].shading.color_type = "MATERIAL"
            return {"FINISHED"}

        if current_revision.committed_date > selected_revision.committed_date:
            step_ids = ifc_diff_ids(
                ifcgit_repo, selected_revision.hexsha, current_revision.hexsha, path_ifc
            )
        else:
            step_ids = ifc_diff_ids(
                ifcgit_repo, current_revision.hexsha, selected_revision.hexsha, path_ifc
            )

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
    """Switches the repository to the selected revision and reloads the IFC file"""

    bl_label = ""
    bl_idname = "ifcgit.switch_revision"
    bl_options = {"REGISTER"}

    # FIXME bad tings happen when switching to a revision that predates current project

    def execute(self, context):

        path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
        item = context.scene.ifcgit_commits[context.scene.commit_index]

        lookup = branches_by_hexsha(ifcgit_repo)
        if item.hexsha in lookup:
            lookup[item.hexsha].checkout()
        else:
            # NOTE this is calling the git binary in a subprocess
            ifcgit_repo.git.checkout(item.hexsha)

        load_project(path_ifc)

        return {"FINISHED"}


class Merge(bpy.types.Operator):
    """Merges the selected branch into working branch"""

    bl_label = "Merge this branch"
    bl_idname = "ifcgit.merge"
    bl_options = {"REGISTER"}

    def execute(self, context):

        path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
        item = context.scene.ifcgit_commits[context.scene.commit_index]

        config_reader = ifcgit_repo.config_reader()
        section = 'mergetool "ifcmerge"'
        if not config_reader.has_section(section):
            config_writer = ifcgit_repo.config_writer()
            config_writer.set_value(
                section, "cmd", "ifcmerge $BASE $LOCAL $REMOTE $MERGED"
            )
            config_writer.set_value(section, "trustExitCode", True)

        lookup = branches_by_hexsha(ifcgit_repo)
        if item.hexsha in lookup:
            # this is a branch!
            try:
                # NOTE this is calling the git binary in a subprocess
                ifcgit_repo.git.merge(lookup[item.hexsha])
            except git.exc.GitCommandError:
                # merge is expected to fail, run ifcmerge
                try:
                    ifcgit_repo.git.mergetool(tool="ifcmerge")
                except:
                    # ifcmerge failed, rollback
                    ifcgit_repo.git.merge(abort=True)
                    # FIXME need to report errors somehow

                    return {"CANCELLED"}
            except:

                return {"CANCELLED"}

            ifcgit_repo.index.add(path_ifc)
            context.scene.commit_message = "Merged branch: " + lookup[item.hexsha].name

            load_project(path_ifc)

            return {"FINISHED"}
        else:
            return {"CANCELLED"}


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

    # FIXME a hexsha could represent more than one branch
    result = {}
    for branch in repo.branches:
        result[branch.commit.hexsha] = branch
    return result


def git_branches(self, context):
    """branches enum"""

    # NOTE "Python must keep a reference to the strings returned by
    # the callback or Blender will misbehave or even crash"
    global branch_names
    branch_names = sorted([branch.name for branch in ifcgit_repo.heads])

    if "main" in branch_names:
        branch_names.remove("main")
        branch_names = ["main"] + branch_names

    return [(myname, myname, myname) for myname in branch_names]


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


def unregister():
    del bpy.types.Scene.ifcgit_commits
    del bpy.types.Scene.commit_index
    del bpy.types.Scene.commit_message
    del bpy.types.Scene.new_branch_name
    del bpy.types.Scene.display_branch
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
