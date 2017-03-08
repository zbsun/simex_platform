##########################################################################
#                                                                        #
# Copyright (C) 2016 Carsten Fortmann-Grote                              #
# Contact: Carsten Fortmann-Grote <carsten.grote@xfel.eu>                #
#                                                                        #
# This file is part of simex_platform.                                   #
# simex_platform is free software: you can redistribute it and/or modify #
# it under the terms of the GNU General Public License as published by   #
# the Free Software Foundation, either version 3 of the License, or      #
# (at your option) any later version.                                    #
#                                                                        #
# simex_platform is distributed in the hope that it will be useful,      #
# but WITHOUT ANY WARRANTY; without even the implied warranty of         #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          #
# GNU General Public License for more details.                           #
#                                                                        #
# You should have received a copy of the GNU General Public License      #
# along with this program.  If not, see <http://www.gnu.org/licenses/>.  #
#                                                                        #
##########################################################################

""" Module for entity checks.
    @author CFG
    @institution XFEL
    @creation 20160623
"""

import exceptions
import h5py
import numpy
import numpy
import os, shutil
import periodictable
import sys, os


from Bio import PDB
from scipy.constants import m_e, c, e

def checkAndGetPDB( path ):
    """ Query a given pdb code from the PDB.

    :param pdb_code: The PDB code of the molecule to query.
    :type pdb_code: str

    :return: The queried molecule pdb dataset.
    :rtype: ???

    """

    if path is None:
        raise IOError( "The parameter 'path' must be a path to a valid pdb file.")

    if not isinstance (path, str):
        raise IOError( "The parameter 'path' must be a path to a valid pdb file.")

    # Setup paths and filenames.
    pdb_target_name = os.path.basename(path).split('.pdb')[0]
    pdb_target_dir = os.path.dirname(path)
    source = os.path.join(pdb_target_dir, 'pdb'+pdb_target_name.lower()+'.ent')
    target = os.path.join(pdb_target_dir, pdb_target_name.lower()+'.pdb')

    if not os.path.isfile( path ):
        # Query from pdb.org
        pdb_list = PDB.PDBList()
        if pdb_target_dir == '':
            pdb_target_dir = '.'

        try:
            print "PDB file %s could not be found. Attempting to query from protein database server." % (path)
            pdb_list.retrieve_pdb_file( pdb_target_name, pdir=pdb_target_dir )
        except:
            raise IOError( "Database query failed.")

        # Move and rename the downloaded file.
        shutil.move( source, path  )

    return path


def loadPDB( path = None ):
    """ Wrapper to convert a given pdb file to a sample dictionary used by e.g. the XMDYNCalculator.

    :param path: The path to the pdb file to be converted.
    :type path: str

    :return: The dictionary describing the sample molecule.
    :rtype: dict
    """

    # Check if the sample is present, retrieve it from the pdb if not.
    target = checkAndGetPDB(path)

    # Convert to dict and return.
    return _pdbToS2ESampleDict(target)

def _pdbToS2ESampleDict(path=None):
    """ """
    """
    Workhorse function that converts a pdb file to the sample dictionary.

    :param path: Path to the pdb file to be loaded.
    :type path : string

    :return: The dictionary expected by downstream simex modules.
    :rtype : dict

    :throws IOError: Path not existing, not a pdb file or corrupt.
    """

    try:
        if not os.path.isfile( path ):
            raise IOError()
    except:
        raise IOError( "Parameter 'path' must be a valid pdb file.")

    # Setup the return dictionary.
    atoms_dict = {'Z' : [],     # Atomic number.
                  'r' : [],     # Cartesian coordinates.
                  'selZ' : {},  # Abundance of each element.
                  'N' : 0,      # Number of atoms.
                  }

    # Attempt loading the pdb.
    try:
        parser = PDB.PDBParser()
        structure = parser.get_structure("sample", path)

        # Get the atoms.
        atoms = structure.get_atoms()

        # Loop over atoms and get charge and coordinates.
        for atom in atoms:

            # Get the element symbol from pdb.
            symbol = atom.element.title()

            # Get the coordinates from pdb.
            coordinates = atom.coord

            # Get the corresponding periodic table element as an instance.
            atom_obj = getattr(periodictable, symbol)

            # Query the atomic number.
            charge = atom_obj.number

            # Write to dict.
            atoms_dict['Z'].append(charge)
            atoms_dict['r'].append(coordinates*1e-10)

    except:
        raise IOError( "Input file %s is not a valid pdb file. " % (path) )


    if len(atoms_dict['Z']) == 0:
        raise IOError( "Input file %s is not a valid pdb file. " % (path) )

    # Get unique elements.
    for sel_Z in numpy.unique( atoms_dict['Z'] ) :
        atoms_dict['selZ'][sel_Z] = numpy.nonzero( atoms_dict['Z'] == sel_Z )[0]

    # Count number of atoms.
    atoms_dict['N'] = len( atoms_dict['Z'] )

    # Convert to numpy arrays.
    atoms_dict['Z'] = numpy.array( atoms_dict['Z'] )
    atoms_dict['r'] = numpy.array( atoms_dict['r'] )

    # Return.
    return atoms_dict

def pic2dist( pic_file_name, target='genesis'):
    """ Utility to extract particle data from openPMD and write into genesis distribution file.

    :param pic_file_name: Filename of openpmd input data file.
    :type pic_file_name: str

    :param target: The targeted file format (genesis || simplex).
    :type target: str

    """

    #  Check path.
    if not os.path.isfile(pic_file_name):
        raise RuntimeError("%s is not a file." % (pic_file_name))

    # Check if input is native or openPMD.
    with h5py.File( pic_file_name, 'r' ) as h5_handle:

        timestep = h5_handle['data'].keys()[-1]

        positions = '/data/%s/particles/e/position/' % (timestep)
        momenta = '/data/%s/particles/e/momentum/' % (timestep)

        x_data = h5_handle[positions]['x'].value
        x_data_unit = h5_handle[positions]['x'].attrs['unitSI']
        x = x_data*x_data_unit

        y_data = h5_handle[positions]['y'].value
        y_data_unit = h5_handle[positions]['y'].attrs['unitSI']
        y = y_data*y_data_unit

        z_data = h5_handle[positions]['z'].value
        z_data_unit = h5_handle[positions]['z'].attrs['unitSI']
        z = z_data*z_data_unit

        px_data = h5_handle[momenta]['x'].value
        px_data_unit = h5_handle[momenta]['x'].attrs['unitSI']
        px = px_data*px_data_unit

        py_data = h5_handle[momenta]['y'].value
        py_data_unit = h5_handle[momenta]['y'].attrs['unitSI']
        py = py_data*py_data_unit

        pz_data = h5_handle[momenta]['z'].value
        pz_data_unit = h5_handle[momenta]['z'].attrs['unitSI']
        pz = pz_data*pz_data_unit

        # Convert to xprime, yprime.
        xprime = numpy.arctan(px/py)
        zprime = numpy.arctan(pz/py)

        # Calculate particle charge.
        charge_group = h5_handle['/data/%s/particles/e/charge/' %(timestep)]
        macroparticle_charge = charge_group.attrs['unitSI']

        # Get number of particles and total charge.
        particle_patches = h5_handle['/data/%s/particles/e/particlePatches/numParticles' %(timestep)].value
        number_of_macroparticles = numpy.sum( particle_patches )

        number_of_electrons_per_macroparticle = macroparticle_charge / e
        total_charge = number_of_macroparticles * macroparticle_charge

        # Calculate momentum
        psquare = px**2 + py**2 + pz**2
        gamma = numpy.sqrt( 1. + psquare/((number_of_electrons_per_macroparticle * m_e*c)**2))
        P = numpy.sqrt(psquare/((number_of_electrons_per_macroparticle * m_e*c)**2))

        print "Number of electrons per macroparticle = ", number_of_electrons_per_macroparticle
        print "Total charge = ", total_charge
        print "Number of macroparticles = ", number_of_macroparticles

        h5_handle.close()

    if target == 'genesis':
	    return numpy.vstack([ x, xprime, z, zprime, y/c, P]).transpose(),  total_charge
    elif target == 'simplex':
	    return numpy.vstack([ y/c, x, xprime, z, zprime,  gamma]).transpose(),  total_charge



if __name__ == "__main__":
    data, charge = pic2dist(sys.argv[1], sys.argv[2])
    # Setup header for distribution file.
    comments = "? "
    size = data.shape[0]
    header = "VERSION = 1.0\nSIZE = %d\nCHARGE = %7.6E\nCOLUMNS X XPRIME Y YPRIME T P" % (size, charge)

    if sys.argv[2] == 'genesis':
        numpy.savetxt( fname='beam.dist', X=data, header=header, comments=comments)
    if sys.argv[2] == 'simplex':
        numpy.savetxt( fname='beam.dist', X=data)


