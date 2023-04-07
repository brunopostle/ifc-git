import os
import re
import git
import bpy

from tool import (
    is_valid_ref_format,
    load_project,
    repo_from_path,
    branches_by_hexsha,
    tags_by_hexsha,
    ifc_diff_ids,
    get_modified_shape_object_step_ids,
    colourise,
)


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
        global ifcgit_repo
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
        global ifcgit_repo
        if ifcgit_repo and ifcgit_repo.head.is_detached and (
            not is_valid_ref_format(context.scene.new_branch_name)
            or context.scene.new_branch_name
            in [branch.name for branch in ifcgit_repo.branches]
        ):
            return False
        return True

    def execute(self, context):

        path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
        global ifcgit_repo
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
        global ifcgit_repo
        if "ifcgit_repo" in globals() and ifcgit_repo != None and ifcgit_repo.heads:
            return True
        return False

    def execute(self, context):

        area = next(area for area in bpy.context.screen.areas if area.type == "VIEW_3D")
        area.spaces[0].shading.color_type = "MATERIAL"
        global ifcgit_repo

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
        lookup = tags_by_hexsha(ifcgit_repo)

        for commit in commits:

            if context.scene.ifcgit_filter == "tagged" and not commit.hexsha in lookup:
                continue
            elif (
                context.scene.ifcgit_filter == "relevant"
                and not commit in commits_relevant
            ):
                continue

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

        global ifcgit_repo
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

        modified_shape_object_step_ids = get_modified_shape_object_step_ids(step_ids)

        final_step_ids = {}
        final_step_ids["added"] = step_ids["added"]
        final_step_ids["removed"] = step_ids["removed"]
        final_step_ids["modified"] = step_ids["modified"].union(
            modified_shape_object_step_ids["modified"]
        )

        colourise(final_step_ids)

        return {"FINISHED"}


class DisplayUncommitted(bpy.types.Operator):
    """Colourise uncommitted objects"""

    bl_label = "Show uncommitted changes"
    bl_idname = "ifcgit.display_uncommitted"
    bl_options = {"REGISTER"}

    def execute(self, context):

        global ifcgit_repo
        path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
        step_ids = ifc_diff_ids(ifcgit_repo, None, "HEAD", path_ifc)
        colourise(step_ids)

        return {"FINISHED"}


class SwitchRevision(bpy.types.Operator):
    """Switches the repository to the selected revision and reloads the IFC file"""

    bl_label = ""
    bl_idname = "ifcgit.switch_revision"
    bl_options = {"REGISTER"}

    # FIXME bad things happen when switching to a revision that predates current project

    def execute(self, context):

        path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
        item = context.scene.ifcgit_commits[context.scene.commit_index]

        global ifcgit_repo
        lookup = branches_by_hexsha(ifcgit_repo)
        if item.hexsha in lookup:
            for branch in lookup[item.hexsha]:
                if branch.name == context.scene.display_branch:
                    branch.checkout()
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

        global ifcgit_repo
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
            for branch in lookup[item.hexsha]:
                if branch.name == context.scene.display_branch:
                    # this is a branch!
                    try:
                        # NOTE this is calling the git binary in a subprocess
                        ifcgit_repo.git.merge(branch)
                    except git.exc.GitCommandError:
                        # merge is expected to fail, run ifcmerge
                        try:
                            ifcgit_repo.git.mergetool(tool="ifcmerge")
                        except:
                            # ifcmerge failed, rollback
                            ifcgit_repo.git.merge(abort=True)
                            # FIXME need to report errors somehow

                            self.report({"ERROR"}, "IFC Merge failed")
                            return {"CANCELLED"}
                    except:

                        self.report({"ERROR"}, "Unknown IFC Merge failure")
                        return {"CANCELLED"}

            ifcgit_repo.index.add(path_ifc)
            context.scene.commit_message = (
                "Merged branch: " + context.scene.display_branch
            )
            context.scene.display_branch = ifcgit_repo.active_branch.name

            load_project(path_ifc)

            return {"FINISHED"}
        else:
            return {"CANCELLED"}
