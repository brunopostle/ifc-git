# ifc-git
*BlenderBIM git support*

This is a prototype add-on, with the intention that something like this will be rolled into BlenderBIM.

## Installation

Download the file and install it using the Blender add-on preferences.

You will need [BlenderBIM](https://blenderbim.org/) and [GitPython](https://gitpython.readthedocs.io/en/stable/)

## Usage

A new *IFC git* panel is addded to *Scene > Properties*.
If your IFC file in BlenderBIM is saved in a local git repository you will be able to interact with the commit history.

The diff functionality highlights *Products* that exist in the current revision that are different or which don't exist in the selected revision.

2023 Bruno Postle <bruno@postle.net>
