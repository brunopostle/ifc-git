import os
import re
import bpy

import core
import tool
from tool import (
    is_valid_ref_format,
    repo_from_path,
)

from data import IfcGitData


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

        core.create_repo(tool)
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

        core.add_file(tool)
        return {"FINISHED"}


class DiscardUncommitted(bpy.types.Operator):
    """Discard saved changes and update to HEAD"""

    bl_label = "Discard uncommitted changes"
    bl_idname = "ifcgit.discard"
    bl_options = {"REGISTER"}

    def execute(self, context):

        core.discard_uncomitted(tool)
        return {"FINISHED"}


class CommitChanges(bpy.types.Operator):
    """Commit current saved changes"""

    bl_label = "Commit changes"
    bl_idname = "ifcgit.commit_changes"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        props = context.scene.IfcGitProperties
        if props.commit_message == "":
            return False
        if (
            IfcGitData.data["repo"]
            and IfcGitData.data["repo"].head.is_detached
            and (
                not is_valid_ref_format(props.new_branch_name)
                or props.new_branch_name
                in [branch.name for branch in IfcGitData.data["repo"].branches]
            )
        ):
            return False
        return True

    def execute(self, context):

        core.commit_changes(tool, context)
        return {"FINISHED"}


class RefreshGit(bpy.types.Operator):
    """Refresh revision list"""

    bl_label = ""
    bl_idname = "ifcgit.refresh"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        if IfcGitData.data["repo"] != None and IfcGitData.data["repo"].heads:
            return True
        return False

    def execute(self, context):

        core.refresh_revision_list(tool, context)
        return {"FINISHED"}


class DisplayRevision(bpy.types.Operator):
    """Colourise objects by selected revision"""

    bl_label = ""
    bl_idname = "ifcgit.display_revision"
    bl_options = {"REGISTER"}

    def execute(self, context):

        core.colourise_revision(tool, context)
        return {"FINISHED"}


class DisplayUncommitted(bpy.types.Operator):
    """Colourise uncommitted objects"""

    bl_label = "Show uncommitted changes"
    bl_idname = "ifcgit.display_uncommitted"
    bl_options = {"REGISTER"}

    def execute(self, context):

        core.colourise_uncommitted(tool)
        return {"FINISHED"}


class SwitchRevision(bpy.types.Operator):
    """Switches the repository to the selected revision and reloads the IFC file"""

    bl_label = ""
    bl_idname = "ifcgit.switch_revision"
    bl_options = {"REGISTER"}

    def execute(self, context):

        core.switch_revision(tool, context)
        return {"FINISHED"}


class Merge(bpy.types.Operator):
    """Merges the selected branch into working branch"""

    bl_label = "Merge this branch"
    bl_idname = "ifcgit.merge"
    bl_options = {"REGISTER"}

    def execute(self, context):

        if core.merge_branch(tool, context, self):
            return {"FINISHED"}
        else:
            return {"CANCELLED"}
