#
# This script converts PLYs in the current dirctory to Alembic Files
# (i.e. you simply need to copy this script into the current PLY files directory)
# It will create an AlembicFiles directory
#
# Use:
#	-> python3 combine_ABC.py -c -t -i abc -b cells_changing -o testuv
#	[-c for color; -t for texture coordinates; -i [ply,abc] for the extension of the input files,
#        -b [name] to specify the base name of the input files, -o [name] to specify part of the
#         output filename]
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

import PLY_to_ABC as P2A

##
# Globals Change These items per Run as desired
####



processInputColors = False
processInputTextures = False
verboseOutput = False

## IMPORT ABC
#def importABC(tempAbcPath, num):
def importABC(inputAbcFilename):
    rgba = uvs = None

    print ("\n" + inputAbcFilename)
    print ("Reading input Alembic file...")
    sys.stdout.flush()

    ## XFORM
    top = aA.IArchive(inputAbcFilename).getTop()
    #xform = aAG.IXform(top, 'cube1')
    xform = aAG.IXform(top, top.getChild(0).getName())

    ## POLYMESH
    #meshObj = aAG.IPolyMesh(xform, 'meshShape1')
    meshObj = aAG.IPolyMesh(xform, xform.getChild(0).getName())
    mesh = meshObj.getSchema()
    mesh_samp = mesh.getValue(aA.ISampleSelector(0))
    points =  mesh_samp.getPositions()
    faceCounts =  mesh_samp.getFaceCounts()
    faceIndices =  mesh_samp.getFaceIndices()

    ## COLOR
    if processInputColors:
        arb = mesh.getArbGeomParams()
        colorParam = None
        if arb.getProperty(0).getDataType().getPod() == aU.POD.kUint8POD:
            print("WARNING: Getting colors in unsigned int format")
            colorParam = aAG.IC4cGeomParam(arb, "rgba")
        elif arb.getProperty(0).getDataType().getPod() == aU.POD.kFloat32POD:
            colorParam = aAG.IC4fGeomParam(arb, "rgba")
        else:
            print("not getting any color info")
        if colorParam:
            color_samp = colorParam.getExpandedValue(aA.ISampleSelector(0))
            rgba = color_samp.getVals()

    ## TEXTURE
    if (processInputTextures):
        arb = mesh.getArbGeomParams()
        for p in arb.propertyheaders:
            if p.getName() == 'uvs':
                uvsParam = aAG.IV2fGeomParam(arb, "uvs")
                uvs_samp = uvsParam.getExpandedValue(aA.ISampleSelector(0))
                uvs = uvs_samp.getVals()

        if not uvs:
            uvsParam = mesh.getUVsParam()
            uvs_samp = uvsParam.getExpandedValue(aA.ISampleSelector())
            uvs = uvs_samp.getVals()

    return points, faceCounts, faceIndices, rgba, uvs


## EXPORT ABC FILE
def exportABC(outputAbcFilename, inputAbcFilenames):
    useVuTextures = True
    #if useVuTextures:
    #    print ("Writing ABC...with Vu texture method")
    #else:
    #    print ("Writing ABC...with online texture method")

    sys.stdout.flush()

    ## TIMESAMPLING DATA
    tvec = aACA.TimeVector()
    tvec[:] = [0]
    fps = 30
    timePerCycle = float(1) / fps
    numSamplesPerCycle = len(tvec)
    #print("time information is ", len(tvec), tvec, timePerCycle)
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

        print ("Writing result to final ABC file with input from", inputAbcFilename)
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
            if useVuTextures:
                if not uvsParam:
                    print ("Has texture -- output in Vu style")
                    arb = mesh.getArbGeomParams()
                    uvsParam = aAG.OV2fGeomParam(arb, "uvs", False, aAG.GeometryScope.kVertexScope, 1)
                    uvsParam.setTimeSampling(ts)
                uvsSamp = aAG.OV2fGeomParamSample(uvs, aAG.GeometryScope.kVertexScope)
                uvsParam.set(uvsSamp)
            else:
                # below was some test code to write out the texture information in a different way.
                # it no longer seems necessary to do it this way though since Max and Maya work the other way
                #print(help(mesh_samp.setUVs))
                # https://docs.alembic.io/python/abcg.html?highlight=setuvs#alembic.AbcGeom.OPolyMeshSchemaSample.setUVs
                #setUVs(...) method of alembic.AbcGeom.OPolyMeshSchemaSample instance
                #   setUVs( (OPolyMeshSchemaSample)arg1, (OV2fGeomParamSample)arg2) -> None
                uvsSamp = aAG.OV2fGeomParamSample(uvs, aAG.GeometryScope.kVertexScope)

                if not uvsParam:
                    print ("Has texture -- output in online example style")
                    #mesh.setUVSourceName()
                    #setUVSourceName(...) method of alembic.AbcGeom.OPolyMeshSchema instance
                    #    setUVSourceName( (OPolyMeshSchema)arg1, (str)arg2) -> None
                    #                    print(help(mesh.setUVSourceName))
                    arb = mesh.getArbGeomParams().getParent()
                    uvsParam = aAG.OV2fGeomParam(arb, "uvs", False, aAG.GeometryScope.kVertexScope, 1)
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

    parser.add_argument("-n", "--np", help="specify number of simultaneous processes for PLY processing, default=10", action="store", type=int, dest='np', default=10)
    parser.add_argument("-c", "--color", help="process colorVertex PLYs", action="store_true", dest='color', default=False)
    parser.add_argument("-t", "--texture", help="process texture coordinates PLYs", action="store_true", dest='texture', default=False)
    parser.add_argument("-w", "--workingdirectory", help="use working directory other than current directory", dest='workingdirectory', default='')
    parser.add_argument("-b", "--basefilename", help="the base file name (doesn't include extension, indexing, or path)", dest='basefilename', required=False, default='')
    parser.add_argument("-i", "--inputextension", help="the input file extension", dest='extension', required=False, default='ply')
    parser.add_argument("-o", "--output", help="the output basefilename (uses basefilename if not set)", dest='output', required=False, default='')


    args = parser.parse_args()
    if args.color :
        print ("Processing colorVertex PLYs")
        sys.stdout.flush()
        processInputColors = True
    if args.texture :
        print ("Processing texture coordinates PLYs")
        sys.stdout.flush()
        processInputTextures = True
    if args.workingdirectory:
        workingDir = args.workingdirectory
    else:
        workingDir = os.getcwd()

    print ("working directory for ABC files is: ", workingDir)
    sys.stdout.flush()

    globName = args.basefilename + '*.' + args.extension
    print ("Looking for input files that match ", globName, " in ", workingDir)
    if args.extension == 'ply':
        inputPlyFilenames = glob.glob(os.path.join(workingDir, globName))
        inputPlyFilenames.sort()
        ambientTempDir = os.path.join(workingDir, 'TempABCFiles')
        P2A.generateTempAbcs(inputPlyFilenames, ambientTempDir, processInputColors, processInputTextures, args.np)
        inputAbcFilenames = glob.glob(os.path.join(ambientTempDir, '*abc'))
        print("AMBIENT is ", ambientTempDir)
    elif args.extension == 'abc':
        inputAbcFilenames = glob.glob(os.path.join(workingDir, globName))
    else:
        print ("ERROR: unknown file extension:", args.extension, " extension needs to be either 'ply' or 'abc'")
        sys.exit(0)

    output = args.output
    if not output:
        output = args.basefilename

    inputAbcFilenames.sort()
    ## RECOMBINE INTO ONE FINAL ABC
    print ("Recombining " + str(len(inputAbcFilenames)) + " ABC's...")
    if len(inputAbcFilenames) == 0:
        print ("No ABC input files")
        sys.exit(0)

    outputAbcFilename = os.path.join(workingDir, '_FINAL_from_' + args.extension + '_' + output + '.abc')

    print ("Making final ABC file from " + str(len(inputAbcFilenames)) + " ABC files")
    print ("This may take a while...")
    exportABC(outputAbcFilename, inputAbcFilenames)
    print ("\nDone creating final ABC file", outputAbcFilename, "\n")

    if args.extension == 'ply':
        print ("Tidying up now...\n")
        print ("Deleting temp ABC's and temp directory")
        shutil.rmtree(ambientTempDir)

    print ("\nDONE\n")
