# -*- coding: utf-8 -*-
"""
Templates to rigidify a deformable object.

The rigidification consist in mixing in a single object rigid and deformable parts.
The rigid and deformable parts are interacting together.

**Sofa Templates:**

.. autosummary::

    Rigidify

stlib.physics.mixedmaterial.Rigidify
*******************************
.. autofunction:: Rigidify


Contributors:
        damien.marchal@univ-lille.fr
        eulalie.coevoet@inria.fr
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.absolute())+"/../")
sys.path.insert(0, str(pathlib.Path(__file__).parent.absolute()))



import Sofa
from splib3.numerics import Vec3, Quat


def Rigidify(targetObject, sourceObject, groupIndices, frames=None, name=None, frameOrientation=None):
    """ Transform a deformable object into a mixed one containing both rigid and deformable parts.

        :param targetObject: parent node where to attach the final object.
        :param sourceObject: node containing the deformable object. The object should be following
                             the ElasticMaterialObject template.
        :param list groupIndices: array of array indices to rigidify. The length of the array should be equal to the number
                                  of rigid component.
        :param list frames: array of frames. The length of the array should be equal to the number
                            of rigid component. The orientation are given in eulerAngles (in degree) by passing
                            three values or using a quaternion by passing four values.
                            [[rx,ry,rz], [qx,qy,qz,w]]
                            User can also specify the position of the frame by passing six values (position and orientation in degree)
                            or seven values (position and quaternion).
                            [[x,y,z,rx,ry,rz], [x,y,z,qx,qy,qz,w]]
                            If the position is not specified, the position of the rigids will be the barycenter of the region to rigidify.
        :param str name: specify the name of the Rigidified object, is none provided use the name of the SOurceObject.
    """
    # Deprecation Warning
    if frameOrientation is not None:
        Sofa.msg_warning("The parameter frameOrientations of the function Rigidify is now deprecated. "
                         "Please use frames instead.")
        frames = frameOrientation

    if frames is None:
        frames = [[0., 0., 0.]]*len(groupIndices)

    assert len(groupIndices) == len(frames), "size mismatch."

    if name is None:
        name = sourceObject.name.value

    sourceObject.init()
    ero = targetObject.addChild(name)

    # allPositions = [sourceObject.container.position.value.copy('K')]
    # allIndices = [sourceObject.container.points.value.copy('K')]

    allPositions = [list(i) for i in sourceObject.container.position.value]
    allIndices = list(sourceObject.container.points.value)
    rigids = []
    indicesMap = []

    def mfilter(si, ai, pts):
        tmp = []
        for i in ai:
            # print(i)
            if i in si:
                tmp.append(pts[i])
        return tmp

    # get all the points from the source.
    sourcePoints = list(map(Vec3, sourceObject.dofs.position.value))
    selectedIndices = []
    # print('-----------------------')
    # print(groupIndices[0], allIndices, sourcePoints)
    # print('-----------------------')
    for i in range(len(groupIndices)):
        selectedPoints = mfilter(groupIndices[i], allIndices, sourcePoints)

        if len(frames[i]) == 3:
            orientation = Quat.createFromEuler(frames[i], inDegree=True)
            poscenter = getBarycenter(selectedPoints)
        elif len(frames[i]) == 4:
            orientation = frames[i]
            poscenter = getBarycenter(selectedPoints)
        elif len(frames[i]) == 6:
            orientation = Quat.createFromEuler([frames[i][3], frames[i][4], frames[i][5]], inDegree=True)
            poscenter = [frames[i][0], frames[i][1], frames[i][2]]
        elif len(frames[i]) == 7:
            orientation = [frames[i][3], frames[i][4], frames[i][5], frames[i][6]]
            poscenter = [frames[i][0], frames[i][1], frames[i][2]]
        else:
            Sofa.msg_error("Do not understand the size of a frame.")
            raise NotImplementedError("Do not understand the size of a frame.")

        rigids.append(poscenter + list(orientation))

        selectedIndices += map(lambda x: x, groupIndices[i])
        indicesMap += [i] * len(groupIndices[i])

    otherIndices = list(set(allIndices) - set(selectedIndices))
    # otherIndices = filter(lambda x: x not in selectedIndices, allIndices)
    Kd = {v: None for k, v in enumerate(allIndices)}
    Kd.update({v: [0, k] for k, v in enumerate(otherIndices)})
    Kd.update({v: [1, k] for k, v in enumerate(selectedIndices)})
    indexPairs = [v for kv in Kd.values() for v in kv]

    freeParticules = ero.addChild("DeformableParts")
    freeParticules.addObject("MechanicalObject", template="Vec3", name="dofs",
                             position=[allPositions[i] for i in otherIndices])

    rigidParts = ero.addChild("RigidParts")
    rigidParts.addObject("MechanicalObject", template="Rigid3d", name="dofs", reserve=len(rigids), position=rigids)

    rigidifiedParticules = rigidParts.addChild("RigidifiedParticules")
    rigidifiedParticules.addObject("MechanicalObject", template="Vec3", name="dofs",
                                   position=[allPositions[i] for i in selectedIndices])

    rigidifiedParticules.addObject("RigidMapping", name="mapping", globalToLocalCoords='true',
                                   rigidIndexPerPoint=indicesMap)

    sourceObject.removeObject(sourceObject.solver)
    sourceObject.removeObject(sourceObject.integration)
    sourceObject.removeObject(sourceObject.LinearSolverConstraintCorrection)

    # The coupling is made with the sourceObject. If the source object is from an ElasticMaterialObject
    # We need to get the owning node form the current python object (this is a hack because of the not yet
    # Finalized design of stlib.
    coupling = sourceObject
    if hasattr(sourceObject, "node"):
        coupling = sourceObject.node

    coupling.addObject("SubsetMultiMapping", name="mapping", template="Vec3,Vec3",
                       input=freeParticules.dofs.getLinkPath()+" "+rigidifiedParticules.dofs.getLinkPath(),
                       output=sourceObject.dofs.getLinkPath(), indexPairs=indexPairs)

    rigidifiedParticules.addChild(coupling)
    freeParticules.addChild(coupling)
    return ero
