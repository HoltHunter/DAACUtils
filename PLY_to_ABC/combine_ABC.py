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

import argparse
import glob
import itertools
import multiprocessing as mp
import os
import os.path
import shutil
import sys
import time

from itertools import repeat
import imath
import alembic.AbcCoreAbstract as aACA
import alembic.Abc as aA
import alembic.AbcGeom as aAG
import alembic.Util as aU

##
# Globals Change These items per Run as desired
####



plyContainsColors = False
plyContainsTexture = False
verboseOutput = False

## IMPORT ABC
#def importABC(tempAbcPath, num):
def importABC(inputAbcFilename):
    rgba = uvs = None

    print ("\n" + inputAbcFilename)
    print ("Reading temp ABC...")
    sys.stdout.flush()

    ## XFORM
    top = aA.IArchive(inputAbcFilename).getTop()
    #xform = aAG.IXform(top, 'cube1')
    xform = aAG.IXform(top, top.getChild(0).getName())

    ## POLYMESH
    #meshObj = aAG.IPolyMesh(xform, 'meshShape1')
    meshObj = aAG.IPolyMesh(xform, xform.getChild(0).getName())
    mesh = meshObj.getSchema()
    print(dir(aU))
    mesh_samp = mesh.getValue(aA.ISampleSelector(0))
    points =  mesh_samp.getPositions()
    faceCounts =  mesh_samp.getFaceCounts()
    faceIndices =  mesh_samp.getFaceIndices()

    ## COLOR
    arb = mesh.getArbGeomParams()
    colorParam = None
    if arb.getProperty(0).getDataType().getPod() == aU.POD.kUint8POD:
        print("1111111111111111111111111111111111", arb.getProperty(0).getDataType().getPod())
        colorParam = aAG.IC4cGeomParam(arb, "rgba")
    elif arb.getProperty(0).getDataType().getPod() == aU.POD.kFloat32POD:
        print("222222222222222222222222")
        colorParam = aAG.IC4fGeomParam(arb, "rgba")
    else:
        print("not getting any color info")
    if colorParam:
        color_samp = colorParam.getExpandedValue(aA.ISampleSelector(0))
        rgba = color_samp.getVals()

    ## TEXTURE
    if (plyContainsTexture):
        arb = mesh.getArbGeomParams()
        uvsParam = aAG.IV2fGeomParam(arb, "uvs")
        uvs_samp = uvsParam.getExpandedValue(aA.ISampleSelector(0))
        uvs = uvs_samp.getVals()

    return points, faceCounts, faceIndices, rgba, uvs


## EXPORT ABC FILE
def exportABC(outputAbcFilename, inputAbcFilenames):
    print ("Writing ABC...")
    sys.stdout.flush()

    ## TIMESAMPLING DATA
    tvec = aACA.TimeVector()
    tvec[:] = [0]
    fps = 30
    timePerCycle = float(1) / fps
    numSamplesPerCycle = len(tvec)
    tst = aACA.TimeSamplingType( numSamplesPerCycle, timePerCycle )
    ts = aACA.TimeSampling( tst, tvec )

    ## CREATE XFORM
    top = aA.OArchive( outputAbcFilename ).getTop()
    tsidx = top.getArchive().addTimeSampling(ts)
    xform = aAG.OXform(top, 'cube1', tsidx)
    xschema = xform.getSchema()

    ## CREATE MESH
    meshObj = aAG.OPolyMesh(xform, 'meshShape', tsidx)
    mesh = meshObj.getSchema()

    color = None
    uvsParam = None

    ## SET MESH DATA FOR EACH PLY TIMESTEP
    for inputAbcFilename in inputAbcFilenames:
        (points, faceCounts, faceIndices, rgba, uvs) = importABC(inputAbcFilename)

        print ("Writing result to final ABC file...")
        sys.stdout.flush()
        mesh_samp = aAG.OPolyMeshSchemaSample(points, faceIndices, faceCounts)
        mesh.set(mesh_samp)

        ## COLOR
        if rgba:
            if not color:
                print ("Has color")
                arb = mesh.getArbGeomParams()
                color = aAG.OC4fGeomParam(arb, "rgba", False, aAG.GeometryScope.kVertexScope, 1)
                color.setTimeSampling(ts)
            samp = aAG.OC4fGeomParamSample(rgba, aAG.GeometryScope.kVertexScope)
            color.set(samp)
        ## TEXTURE
        if uvs:
            if not uvsParam:
                print ("Has texture")
                arb = mesh.getArbGeomParams()
                uvsParam = aAG.OV2fGeomParam(arb, "uvs", False, aG.GeometryScope.kVertexScope, 1)
                uvsParam.setTimeSampling(ts)
            uvsSamp = aAG.OV2fGeomParamSample(uvs, aAG.GeometryScope.kVertexScope)
            uvsParam.set(uvsSamp)


if __name__ == '__main__':

    ## PARSE COMMANDLINE ARGUMENTS
    parser = argparse.ArgumentParser()
    parser.formatter_class = argparse.RawTextHelpFormatter
    if ( False ):
    	pd = dir(parser)
    	for i,d in enumerate(pd) :
    		print ("%d %s" % (i,d))

    parser.add_argument("-c", "--color", help="process colorVertex PLYs", action="store_true", dest='color', default=False)
    parser.add_argument("-t", "--texture", help="process texture coordinates PLYs", action="store_true", dest='texture', default=False)
    parser.add_argument("-w", "--workingdirectory", help="use working directory other than current directory", dest='workingdirectory', default='./')
    parser.add_argument("-b", "--basefilename", help="the base file name (doesn't include extension, indexing, or path)", dest='basefilename', required=True)

    args = parser.parse_args()
    if args.color :
    	print ("Processing colorVertex PLYs")
    	sys.stdout.flush()
    	plyContainsColors = True
    if args.texture :
    	print ("Processing texture coordinates PLYs")
    	sys.stdout.flush()
    	plyContainsTexture = True

    workingDirectory = args.workingdirectory
    baseFilename = args.basefilename

    print ("working directory for ABC files is: ", workingDirectory)
    sys.stdout.flush()

    inputAbcFilenames = glob.glob(baseFilename+'*abc', root_dir=workingDirectory)
    inputAbcFilenames.sort()
    ## RECOMBINE INTO ONE FINAL ABC
    print ("Recombining " + str(len(inputAbcFilenames)) + " ABC's...")
    if len(inputAbcFilenames) == 0:
        print ("No ABC input files")
        sys.exit(0)

    outputAbcFilename = workingDirectory + '/combined' + baseFilename + '.abc'
    print ("Making final ABC file from " + str(len(inputAbcFilenames)) + " ABC files")
    print ("This may take a while...")
    exportABC(outputAbcFilename, inputAbcFilenames)
    print ("\nDone creating final ABC file\n")


    print ("\nDONE\n")
