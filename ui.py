import os
import bpy

from tool import (
    repo_from_path,
    branches_by_hexsha,
    tags_by_hexsha,
)


class IFCGIT_PT_panel(bpy.types.Panel):
    """Scene Properties panel to interact with IFC repository data"""

    bl_label = "IFC Git"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "BIM_PT_project_info"

    def draw(self, context):
        layout = self.layout
        path_ifc = bpy.data.scenes["Scene"].BIMProperties.ifc_file

        # TODO if file isn't saved, offer to save to disk

        row = layout.row()
        if path_ifc:
            # FIXME shouldn't be a global
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
        row.prop(bpy.context.scene, "ifcgit_filter", text="Filter revisions")

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
