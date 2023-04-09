import bpy
from bpy.types import PropertyGroup

from bpy.props import (
    StringProperty,
    BoolProperty,
    CollectionProperty,
    IntProperty,
    EnumProperty,
)


class IfcGitListItem(bpy.types.PropertyGroup):
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

class IfcGitProperties(PropertyGroup):

    
    ifcgit_commits: CollectionProperty(type=ListItem)
    commit_index: IntProperty(
        name="Index for my_list", default=0
    )
    commit_message: StringProperty(
        name="Commit message",
        description="A human readable description of these changes",
        default="",
    )
    new_branch_name: StringProperty(
        name="New branch name",
        description="A short name used to refer to this branch",
        default="",
    )
    display_branch: EnumProperty(
        items=git_branches, update=update_revlist
    )
    ifcgit_filter: EnumProperty(
        items=[
            ("all", "All", "All revisions"),
            ("tagged", "Tagged", "Tagged revisions"),
            ("relevant", "Relevant", "Revisions for this project"),
        ],
        update=update_revlist,
    )
