#
# This script converts PLYs in the current dirctory to Alembic Files
# (i.e. you simply need to copy this script into the current PLY files directory)
# It will create an AlembicFiles directory
#
# Use:
#	-> python PLY_to_ABC_WIN.py -c -t
#	[-c for color; -t for texture coordinates]
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

def getCwdTemplateNameFor( extentionString ):
    wildCardMatchString = "*" + extentionString
    aSingleFilenameMatch = glob.glob( wildCardMatchString )[0]
    print (aSingleFilenameMatch)
    # removing the extention
    template = os.path.splitext( aSingleFilenameMatch )[0]
    zfillNum = 0
    while list(template)[-1].isdigit():
        template = template[:-1]
        zfillNum += 1
    return( template, zfillNum )


ply_TemplateName, zfillNum = getCwdTemplateNameFor( "ply" )
ambientTempDir = os.path.join( os.getcwd(), "ABC")
plyContainsColors = False
plyContainsTexture = False
verboseOutput = False
poolBatchSize = 10


def testForRGBAInPLYFile():
    fileIndex = str(0).zfill(zfillNum)
    plyFilename = ply_TemplateName + fileIndex + ".ply"
    plyPath	= os.path.join( os.getcwd(), plyFilename )

    plydata = PlyData.read(plyPath)
    try:
        vertex = plydata['vertex'][0]
        r = float(vertex['red'])
        return True
    except ValueError:
        return False

def testForUVsInPLYFile():
    fileIndex = str(0).zfill(zfillNum)
    plyFilename = ply_TemplateName + fileIndex + ".ply"
    plyPath	= os.path.join( os.getcwd(), plyFilename )

    plydata = PlyData.read(plyPath)
    try:
        vertex = plydata['vertex'][0]
        u = float(vertex['u'])
        v = float(vertex['v'])
        return True
    except ValueError:
        return False

def writeTempABCFiles(fileIndex, cBool, tBool):

    fileIndex = str(fileIndex).zfill(zfillNum)

    plyFilename = ply_TemplateName + fileIndex + ".ply"
    plyPath     = os.path.join( os.getcwd(), plyFilename )

    abcFilename = ply_TemplateName + fileIndex + ".abc"
    abcPath     = os.path.join( os.getcwd(), "ABC", abcFilename )

    plyContainsColors = cBool
    plyContainsTexture = tBool

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


    plydata = PlyData.read(plyPath)
    plyFaceCount = plydata['face'].count
    plyVertexCount = plydata['vertex'].count


    ## SANITY CHECKS
    if( verboseOutput ) :
    	print (str(fileIndex) + " plyFaceCount: " + str(plyFaceCount))
    	print (str(fileIndex) + " plyVertexCount: " + str(plyVertexCount))
    	print ("plyContainsColors: " + str(plyContainsColors))
    	print ("plyContainsTexture: " + str(plyContainsTexture))
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

        if (plyContainsColors):
            r = float(vertex['red']) / 255
            g = float(vertex['green']) / 255
            b = float(vertex['blue']) / 255
            a = float(1.0)
            rgbaList.append(C4f(r, g, b, a))

        if (plyContainsTexture):
            u = float(vertex['u'])
            v = float(vertex['v'])
            w = 0.0
            uvList.append(V2f(u, v))

    ## SET POINTS, COLORS, & UVS
    points = setArray(P3fTPTraits, pointList)
    if (plyContainsColors):
    	rgba = setArray(C4fTPTraits, rgbaList)
    if (plyContainsTexture):
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
    top = OArchive( abcPath ).getTop()
    tsidx = top.getArchive().addTimeSampling(ts)
    xform = OXform(top, 'cube1', tsidx)
    xschema = xform.getSchema()

    ## CREATE MESH
    meshObj = OPolyMesh(xform, 'meshShape1', tsidx)
    mesh = meshObj.getSchema()

    ## COLOR
    if (plyContainsColors):
        arb = mesh.getArbGeomParams()
        color = OC4fGeomParam(arb, "rgba", False, GeometryScope.kVertexScope, 1) ## MUST BE NAMED "rgba"
        color.setTimeSampling(ts)

    ## TEXTURE
    if (plyContainsTexture):
        arb = mesh.getArbGeomParams()
        uvs = OV2fGeomParam(arb, "uvs", False, GeometryScope.kVertexScope, 1) ## MUST BE NAMED "uvs"
        uvs.setTimeSampling(ts)

    ## SET MESH DATA FOR EACH PLY TIMESTEP
    mesh_samp = OPolyMeshSchemaSample(points, faceIndices, faceCounts)
    mesh.set(mesh_samp)
    if (plyContainsColors):
        samp = OC4fGeomParamSample(rgba, GeometryScope.kVertexScope)
        color.set(samp)

    if (plyContainsTexture):
        uvsamp = OV2fGeomParamSample(uvsArray, GeometryScope.kVertexScope)
        uvs.set(uvsamp)

## IMPORT ABC
def importABC(tempAbcPath, num):
    global points, faceCounts, faceIndices, rgba, uvs
    faceCounts = faceIndices = points = rgba = uvs = None

    tempNum = num
    tempFilename = tempAbcPath + str(tempNum).zfill(zfillNum) + ".abc"
    print ("\n" + tempFilename)
    print ("Reading temp ABC...")
    sys.stdout.flush()

    ## XFORM
    top = IArchive(tempFilename).getTop()
    xform = IXform(top, 'cube1')

    ## POLYMESH
    meshObj = IPolyMesh(xform, 'meshShape1')
    mesh = meshObj.getSchema()
    mesh_samp = mesh.getValue(ISampleSelector(0))
    points =  mesh_samp.getPositions()
    faceCounts =  mesh_samp.getFaceCounts()
    faceIndices =  mesh_samp.getFaceIndices()

    ## COLOR
    if (plyContainsColors):
        arb = mesh.getArbGeomParams()
        colorParam = IC4fGeomParam(arb, "rgba")
        color_samp = colorParam.getExpandedValue(ISampleSelector(0))
        rgba = color_samp.getVals()

    ## TEXTURE
    if (plyContainsTexture):
        arb = mesh.getArbGeomParams()
        uvsParam = IV2fGeomParam(arb, "uvs")
        uvs_samp = uvsParam.getExpandedValue(ISampleSelector(0))
        uvs = uvs_samp.getVals()


## EXPORT ABC FILE
def exportABC(tempAbcPath, finalAbcPath, num):
    print ("Writing ABC...")
    sys.stdout.flush()

    ## TIMESAMPLING DATA
    tvec = TimeVector()
    tvec[:] = [0]
    fps = 30
    timePerCycle = float(1) / fps
    numSamplesPerCycle = len(tvec)
    tst = TimeSamplingType( numSamplesPerCycle, timePerCycle )
    ts = TimeSampling( tst, tvec )

    ## CREATE XFORM
    top = OArchive( finalAbcPath ).getTop()
    tsidx = top.getArchive().addTimeSampling(ts)
    xform = OXform(top, 'cube1', tsidx)
    xschema = xform.getSchema()

    ## CREATE MESH
    meshObj = OPolyMesh(xform, 'meshShape', tsidx)
    mesh = meshObj.getSchema()

    ## COLOR
    if (plyContainsColors):
    	print ("Has color")
    	arb = mesh.getArbGeomParams()
    	color = OC4fGeomParam(arb, "rgba", False, GeometryScope.kVertexScope, 1)
    	color.setTimeSampling(ts)

    ## TEXTURE
    if (plyContainsTexture):
    	print ("Has texture")
    	arb = mesh.getArbGeomParams()
    	uvsParm = OV2fGeomParam(arb, "uvs", False, GeometryScope.kVertexScope, 1)
    	uvsParm.setTimeSampling(ts)

    ## SET MESH DATA FOR EACH PLY TIMESTEP
    for i in range(0, num):
        importABC(tempAbcPath, i)

        print ("Writing result to final ABC file...")
        sys.stdout.flush()
        mesh_samp = OPolyMeshSchemaSample(points, faceIndices, faceCounts)
        mesh.set(mesh_samp)

        if (plyContainsColors):
            samp = OC4fGeomParamSample(rgba, GeometryScope.kVertexScope)
            color.set(samp)
        if (plyContainsTexture):
            uvsSamp = OV2fGeomParamSample(uvs, GeometryScope.kVertexScope)
            uvsParm.set(uvsSamp)


if __name__ == '__main__':

    ## PARSE COMMANDLINE ARGUMENTS
    parser = argparse.ArgumentParser()
    parser.formatter_class = argparse.RawTextHelpFormatter
    if ( False ):
        pd = dir(parser)
        for i,d in enumerate(pd) :
            print ("%d %s" % (i,d))

    parser.add_argument("-n", "--np", help="specify number of simultaneous processes, default=10", action="store", type=int, dest='np', default=10)
    parser.add_argument("-c", "--color", help="process colorVertex PLYs", action="store_true", dest='color', default=False)
    parser.add_argument("-t", "--texture", help="process texture coordinates PLYs", action="store_true", dest='texture', default=False)

    args = parser.parse_args()
    if args.np :
        print ("Number of threads/processors: %d" % args.np)
        sys.stdout.flush()
        poolBatchSize = args.np
    if args.color :
        print ("Processing colorVertex PLYs")
        sys.stdout.flush()
        plyContainsColors = True
    if args.texture :
        print ("Processing texture coordinates PLYs")
        sys.stdout.flush()
        plyContainsTexture = True

    ## CHECK FOR RGBA/UV INFO
    if plyContainsColors:
        isRGBAInFile = testForRGBAInPLYFile()
        print ("isRGBAInFile from testForRGBAInPLYFile: %r" % isRGBAInFile)
        if not isRGBAInFile:
            print ("\nWARNING: you specified color processing (-c, --color), but there is no RGBA in the PLY file.")
            print ("Turning OFF color processing. Moron.")
            plyContainsColors = False

    if plyContainsTexture:
        isUVsInFile = testForUVsInPLYFile()
        print ("isUVsInFile from testForUVsInPLYFile: %r" % isUVsInFile)
        if not isUVsInFile:
            print ("\nWARNING: you specified texture processing (-t, --texture), but there are no UVs in the PLY file.")
            print ("Turning OFF texture processing. Moron.")
            plyContainsTexture = False
    print ("plyContainsColors: %r" % plyContainsColors)
    print ("plyContainsTexture: %r" % plyContainsTexture)

    ##
    # Create the temp directory
    ####
    if not os.path.exists(ambientTempDir):
        os.makedirs(ambientTempDir)

    ## PRINT
    numPlyFiles = len( glob.glob("*.ply"))
    print ("\nConverting " + str(numPlyFiles) + " PLY's, (" + str(poolBatchSize) + " at a time)")

    ## POOL
    pool = mp.Pool( processes = poolBatchSize)
    print ("Working on individual ABC files")
    pool.starmap( writeTempABCFiles, zip( range(0, numPlyFiles), repeat(plyContainsColors), repeat(plyContainsTexture) ) )
    print ("\nDone creating temp ABC files\n")

    ## RECOMBINE INTO ONE FINAL ABC
    print ("Recombining " + str(numPlyFiles) + " temporary ABC's...")
    TempAbcFilename = ply_TemplateName
    TempAbcPath     = os.path.join( os.getcwd(), "ABC", TempAbcFilename )
    FinalAbcFilename = "_FINAL_" + ply_TemplateName + ".abc"
    FinalAbcPath     = os.path.join( os.getcwd(), FinalAbcFilename )
    print ("Making final ABC file from " + str(numPlyFiles) + " ABC files")
    print ("This may take a while...")
    exportABC(TempAbcPath, FinalAbcPath, numPlyFiles)
    print ("\nDone creating final ABC file\n")

    ## DELETE TEMP ABC FILES/FOLDER
    print ("Tidying up now...\n")
    print ("Deleting temp ABC's and temp directory")
    shutil.rmtree(ambientTempDir)

    print ("\nDONE\n")
