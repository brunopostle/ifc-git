# ifc-git
*BlenderBIM Git support*

This is a prototype add-on, with the intention that something like this will be rolled into BlenderBIM.

## Installation

Download the file and install it using the Blender add-on preferences.

You will need [BlenderBIM](https://blenderbim.org/) and [GitPython](https://gitpython.readthedocs.io/en/stable/).
For the experimental branch merging feature you will need [ifcmerge](https://github.com/brunopostle/ifcmerge).

## Usage

A new *IFC Git* panel is addded to *Scene > Properties*.
If your IFC file in BlenderBIM is saved in a local Git repository you will be able to browse branches and revisions, loading any past version.
The panel offers functionality to create a Git repository if it doesn't already exist.

Saved changes can be committed or discarded.
Committing changes to an earlier revision forces the creation of a branch, forking the project.
Under some circumstances forked branches can be merged together.

External changes to the Git repository made using other tools, such as pulling remote branches, are reflected in the addon and don't require restarting Blender.

The diff functionality highlights *Products* that exist in the current revision that are different or which don't exist in the selected revision.

2023 Bruno Postle <bruno@postle.net>
