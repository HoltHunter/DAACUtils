#
# This script is used by combine_ABC.py to generate temporary ABC
# files from PLY files.
#
# Dependencies:
# 	Python 3.10
# 	PlyFile
# 	numpy-1.22.4+mkl-cp310-cp310-win_amd64.whl
# 	boost_python-1.78-cp310-cp310-win_amd64.whl
# 	PyAlembic-1.8.2-cp310-cp310-win_amd64.whl
#
# Wheel Location:
# 	U:\Vu_Tran\PyAlembic\PyAlembic_packages_x64\Python3.10
#
#####

##
# vhtran edit
# 11-17-23
#####

import sys
import os
import os.path
import glob
import time
import argparse
import itertools
import multiprocessing as mp
import shutil

from itertools import repeat
from plyfile import PlyData, PlyElement
from imath import *
from alembic.AbcCoreAbstract import *
from alembic.Abc import *
from alembic.AbcGeom import *
from alembic.Util import *

##
# Globals Change These items per Run as desired
####

verboseOutput = False

def testForRGBAInPLYFile(filename):
    plydata = PlyData.read(filename)
    try:
        vertex = plydata['vertex'][0]
        r = float(vertex['red'])
        return True
    except ValueError:
        return False

def testForUVsInPLYFile(filename):
    plydata = PlyData.read(filename)
    try:
        vertex = plydata['vertex'][0]
        u = float(vertex['u'])
        v = float(vertex['v'])
        return True
    except ValueError:
        return False

def writeTempABCFiles(plyFilename, fileIndex, ambientTempDir, processInputColors, processInputTextures):
    sys.stdout.write(".")
    sys.stdout.flush()

    ## INIT
    data = []
    C4f = Color4f

    ## PROCESS ARRAYS TO BE WRITABLE TO AN ABC FILE
    def setArray( iTPTraits, iList ):
        array = iTPTraits.arrayType( len( iList ) )
        for i in range( len( iList ) ):
            array[i] = iList[i]
        return array

    plydata = PlyData.read(plyFilename)
    plyFaceCount = plydata['face'].count
    plyVertexCount = plydata['vertex'].count


    ## SANITY CHECKS
    if( verboseOutput ) :
        print (str(fileIndex) + " plyFaceCount: " + str(plyFaceCount))
        print (str(fileIndex) + " plyVertexCount: " + str(plyVertexCount))
        print ("processInputColors: " + str(processInputColors))
        print ("processInputTextures: " + str(processInputTextures))
    sys.stdout.flush()

    ## FACE COUNT & INDICES
    faceCountList = []
    faceIndicesList = []
    for i in range(plyFaceCount):
        vertexIndices = plydata['face']['vertex_indices'][i]
        vertPerFace = len(vertexIndices)
        faceCountList.append( int(vertPerFace) )

        ## REVERSED FIXES NORMALS
        for each in reversed(vertexIndices):
            faceIndicesList.append( int(each) )

    ## SET FACEINDICES & FACECOUNTS
    faceIndices = setArray(Int32TPTraits, faceIndicesList)
    faceCounts = setArray(Int32TPTraits, faceCountList)

    ## VERTICES, COLOR, & UV
    pointList = []
    rgbaList = []
    uvList = []
    for i in range(plyVertexCount):
        vertex = plydata['vertex'][i]
        point = V3f(float(vertex[0]), float(vertex[1]), float(vertex[2]))
        pointList.append(point)

        if (processInputColors):
            r = float(vertex['red']) / 255
            g = float(vertex['green']) / 255
            b = float(vertex['blue']) / 255
            a = float(1.0)
            rgbaList.append(C4f(r, g, b, a))

        if (processInputTextures):
            u = float(vertex['u'])
            v = float(vertex['v'])
            w = 0.0
            uvList.append(V2f(u, v))

    ## SET POINTS, COLORS, & UVS
    points = setArray(P3fTPTraits, pointList)
    if (processInputColors):
        rgba = setArray(C4fTPTraits, rgbaList)
    if (processInputTextures):
        uvsArray = setArray(V2fTPTraits, uvList)


    ## EXPORT ABC FILE
    ## TIMESAMPLING DATA
    tvec = TimeVector()
    tvec[:] = [0]
    fps = 30
    timePerCycle = float(1) / fps
    numSamplesPerCycle = len(tvec)
    tst = TimeSamplingType( numSamplesPerCycle, timePerCycle )
    ts = TimeSampling( tst, tvec )

    ## CREATE XFORM
    abcFilename = "TempFile_" +str(fileIndex) + ".abc"
    abcPath     = os.path.join( ambientTempDir, abcFilename )
    top = OArchive( abcPath ).getTop()
    tsidx = top.getArchive().addTimeSampling(ts)
    xform = OXform(top, 'cube1', tsidx)
    xschema = xform.getSchema()

    ## CREATE MESH
    meshObj = OPolyMesh(xform, 'meshShape1', tsidx)
    mesh = meshObj.getSchema()

    ## COLOR
    if (processInputColors):
        arb = mesh.getArbGeomParams()
        color = OC4fGeomParam(arb, "rgba", False, GeometryScope.kVertexScope, 1) ## MUST BE NAMED "rgba"
        color.setTimeSampling(ts)

    ## TEXTURE
    if (processInputTextures):
        arb = mesh.getArbGeomParams()
        uvs = OV2fGeomParam(arb, "uvs", False, GeometryScope.kVertexScope, 1) ## MUST BE NAMED "uvs"
        uvs.setTimeSampling(ts)

    ## SET MESH DATA FOR EACH PLY TIMESTEP
    mesh_samp = OPolyMeshSchemaSample(points, faceIndices, faceCounts)
    mesh.set(mesh_samp)
    if (processInputColors):
        samp = OC4fGeomParamSample(rgba, GeometryScope.kVertexScope)
        color.set(samp)

    if (processInputTextures):
        uvsamp = OV2fGeomParamSample(uvsArray, GeometryScope.kVertexScope)
        uvs.set(uvsamp)

def generateTempAbcs(inputPlyFilenames, ambientTempDir, processInputColors, processInputTextures, poolBatchSize):
    print ("Number of threads/processors: %d" % poolBatchSize)
    if processInputColors:
        print ("Processing colorVertex PLYs")
    if processInputTextures:
        print ("Processing texture coordinates PLYs")


    ## CHECK FOR RGBA/UV INFO
    if processInputColors:
        isRGBAInFile = testForRGBAInPLYFile(inputPlyFilenames[0])
        print ("isRGBAInFile from testForRGBAInPLYFile: %r" % isRGBAInFile)
        if not isRGBAInFile:
            print ("\nWARNING: you specified color processing (-c, --color), but there is no RGBA in the PLY file.")
            print ("Turning OFF color processing. Moron.")
            processInputColors = False

    if processInputTextures:
        isUVsInFile = testForUVsInPLYFile(inputPlyFilenames[0])
        print ("isUVsInFile from testForUVsInPLYFile: %r" % isUVsInFile)
        if not isUVsInFile:
            print ("\nWARNING: you specified texture processing (-t, --texture), but there are no UVs in the PLY file.")
            print ("Turning OFF texture processing. Moron.")
            processInputTextures = False
    print ("processInputColors: %r" % processInputColors)
    print ("processInputTextures: %r" % processInputTextures)

    ##
    # Create the temp directory
    ####
    if not os.path.exists(ambientTempDir):
        os.makedirs(ambientTempDir)

    ## PRINT
    print ("\nConverting " + str(len(inputPlyFilenames)) + " PLY's, (" + str(poolBatchSize) + " at a time)")

    ## POOL
    pool = mp.Pool( processes = poolBatchSize)
    print ("Working on individual ABC files")
    #pool.starmap( writeTempABCFiles, zip( range(0, numPlyFiles), repeat(processInputColors), repeat(processInputTextures) ) )
    #pool.starmap( writeTempABCFiles, zip( inputPlyFilenames, range(0, len(inputPlyFilenames)), repeat(ambientTempDir), repeat(processInputColors), repeat(processInputTextures) ) )
    index = 0
    for f in inputPlyFilenames:
        writeTempABCFiles(f, index, ambientTempDir, processInputColors, processInputTextures)
        index = index + 1
    print ("\nDone creating temp ABC files\n")

    ## RECOMBINE INTO ONE FINAL ABC

    return
