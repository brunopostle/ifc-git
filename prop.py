import bpy
from bpy.types import PropertyGroup

from bpy.props import (
    StringProperty,
    BoolProperty,
)


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
