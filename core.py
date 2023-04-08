import os
import bpy
import git
from data import IfcGitData


def create_repo(tool):
    path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
    path_dir = os.path.abspath(os.path.dirname(path_ifc))
    git.Repo.init(path_dir)


def add_file(tool):
    path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
    repo = tool.repo_from_path(path_ifc)
    repo.index.add(path_ifc)
    repo.index.commit(message="Added " + os.path.relpath(path_ifc, repo.working_dir))

    bpy.ops.ifcgit.refresh()


def discard_uncomitted(tool):
    path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
    # NOTE this is calling the git binary in a subprocess
    IfcGitData.data["repo"].git.checkout(path_ifc)
    tool.load_project(path_ifc)


def commit_changes(tool, context):
    path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
    IfcGitData.data["repo"].index.add(path_ifc)
    IfcGitData.data["repo"].index.commit(message=context.scene.commit_message)
    context.scene.commit_message = ""

    if IfcGitData.data["repo"].head.is_detached:
        new_branch = IfcGitData.data["repo"].create_head(context.scene.new_branch_name)
        new_branch.checkout()
        context.scene.display_branch = context.scene.new_branch_name
        context.scene.new_branch_name = ""

    bpy.ops.ifcgit.refresh()


def refresh_revision_list(tool, context):
    area = next(area for area in bpy.context.screen.areas if area.type == "VIEW_3D")
    area.spaces[0].shading.color_type = "MATERIAL"

    # ifcgit_commits is registered list widget
    context.scene.ifcgit_commits.clear()

    path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file

    commits = list(
        git.objects.commit.Commit.iter_items(
            repo=IfcGitData.data["repo"],
            rev=[context.scene.display_branch],
        )
    )
    commits_relevant = list(
        git.objects.commit.Commit.iter_items(
            repo=IfcGitData.data["repo"],
            rev=[context.scene.display_branch],
            paths=[path_ifc],
        )
    )
    lookup = tool.tags_by_hexsha(IfcGitData.data["repo"])

    for commit in commits:

        if context.scene.ifcgit_filter == "tagged" and not commit.hexsha in lookup:
            continue
        elif (
            context.scene.ifcgit_filter == "relevant" and not commit in commits_relevant
        ):
            continue

        context.scene.ifcgit_commits.add()
        context.scene.ifcgit_commits[-1].hexsha = commit.hexsha
        if commit in commits_relevant:
            context.scene.ifcgit_commits[-1].relevant = True


def colourise_revision(tool, context):
    path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
    item = context.scene.ifcgit_commits[context.scene.commit_index]

    selected_revision = IfcGitData.data["repo"].commit(rev=item.hexsha)
    current_revision = IfcGitData.data["repo"].commit()

    if selected_revision == current_revision:
        area = next(area for area in bpy.context.screen.areas if area.type == "VIEW_3D")
        area.spaces[0].shading.color_type = "MATERIAL"
        return

    if current_revision.committed_date > selected_revision.committed_date:
        step_ids = tool.ifc_diff_ids(
            IfcGitData.data["repo"],
            selected_revision.hexsha,
            current_revision.hexsha,
            path_ifc,
        )
    else:
        step_ids = tool.ifc_diff_ids(
            IfcGitData.data["repo"],
            current_revision.hexsha,
            selected_revision.hexsha,
            path_ifc,
        )

    modified_shape_object_step_ids = tool.get_modified_shape_object_step_ids(step_ids)

    final_step_ids = {}
    final_step_ids["added"] = step_ids["added"]
    final_step_ids["removed"] = step_ids["removed"]
    final_step_ids["modified"] = step_ids["modified"].union(
        modified_shape_object_step_ids["modified"]
    )

    tool.colourise(final_step_ids)


def colourise_uncommitted(tool):
    path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
    step_ids = tool.ifc_diff_ids(IfcGitData.data["repo"], None, "HEAD", path_ifc)
    tool.colourise(step_ids)


def switch_revision(tool, context):
    # FIXME bad things happen when switching to a revision that predates current project

    path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
    item = context.scene.ifcgit_commits[context.scene.commit_index]

    lookup = tool.branches_by_hexsha(IfcGitData.data["repo"])
    if item.hexsha in lookup:
        for branch in lookup[item.hexsha]:
            if branch.name == context.scene.display_branch:
                branch.checkout()
    else:
        # NOTE this is calling the git binary in a subprocess
        IfcGitData.data["repo"].git.checkout(item.hexsha)

    tool.load_project(path_ifc)


def merge_branch(tool, context, operator):
    path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file
    item = context.scene.ifcgit_commits[context.scene.commit_index]

    config_reader = IfcGitData.data["repo"].config_reader()
    section = 'mergetool "ifcmerge"'
    if not config_reader.has_section(section):
        config_writer = IfcGitData.data["repo"].config_writer()
        config_writer.set_value(section, "cmd", "ifcmerge $BASE $LOCAL $REMOTE $MERGED")
        config_writer.set_value(section, "trustExitCode", True)

    lookup = tool.branches_by_hexsha(IfcGitData.data["repo"])
    if item.hexsha in lookup:
        for branch in lookup[item.hexsha]:
            if branch.name == context.scene.display_branch:
                # this is a branch!
                try:
                    # NOTE this is calling the git binary in a subprocess
                    IfcGitData.data["repo"].git.merge(branch)
                except git.exc.GitCommandError:
                    # merge is expected to fail, run ifcmerge
                    try:
                        IfcGitData.data["repo"].git.mergetool(tool="ifcmerge")
                    except:
                        # ifcmerge failed, rollback
                        IfcGitData.data["repo"].git.merge(abort=True)
                        # FIXME need to report errors somehow

                        operator.report({"ERROR"}, "IFC Merge failed")
                        return False
                except:

                    operator.report({"ERROR"}, "Unknown IFC Merge failure")
                    return False

        IfcGitData.data["repo"].index.add(path_ifc)
        context.scene.commit_message = "Merged branch: " + context.scene.display_branch
        context.scene.display_branch = IfcGitData.data["repo"].active_branch.name

        tool.load_project(path_ifc)
