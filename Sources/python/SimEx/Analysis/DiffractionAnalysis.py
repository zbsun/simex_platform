##########################################################################
#                                                                        #
# Copyright (C) 2015-2017 Carsten Fortmann-Grote                         #
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
"""
    :module DiffractionAnalysis: Module that hosts the DiffractionAnalysis class."""
from SimEx.Analysis.AbstractAnalysis import AbstractAnalysis, plt, mpl
from matplotlib.colors import Normalize, LogNorm

from copy import deepcopy
import h5py
import math
import numpy
import os
import wpg

class DiffractionAnalysis(AbstractAnalysis):
    """
    :class DiffractionAnalysis: Class that implements common data analysis tasks for wavefront (radiation field) data.
    """

    def __init__(self,
                 input_path=None,
                 pattern_indices=None,
                 poissonize=True,
            ):
        """ Constructor for the DiffractionAnalysis class.

        :param input_path: Name of file or directory that contains data to analyse.
        :type input_path: str

        :param pattern_indices: Identify which patterns to include in the analysis (defaul "all").
        :type pattern_indices: int || sequence of int || "all"

        :param poissonized: Whether to add Poisson noise to the integer photon numbers (default True)
        :type poissonized: bool

        """

        # Initialize base class. This takes care of parameter checking.
        super(DiffractionAnalysis, self).__init__(input_path)

        # Handle patterns.
        self.__given_indices = pattern_indices
        self.pattern_indices = pattern_indices

        # Init attributes.
        self.poissonize = poissonize
        self.__parameters = diffractionParameters(self.input_path)

    @property
    def pattern_indices(self):
        """ Query pattern indices attribute. """
        return self.__pattern_indices

    @pattern_indices.setter
    def pattern_indices(self, pattern_indices):
        """ Set the pattern indices. """

        indices = pattern_indices
        if indices is None:
            indices = 'all'

        if not (isinstance(indices, int) or indices == 'all' or hasattr(indices, '__iter__')):
            raise TypeError('The parameter "pattern_indices" must be an int, iterable over ints, or "all".')

        # Convert int to list.
        if isinstance(pattern_indices, int):
            indices = [pattern_indices]

        self.__pattern_indices = indices

    @property
    def patterns_iterator(self):
        return self.patternGenerator()

    @property
    def poissonize(self):
        """ Query whether to read data with (True) or without (False) Poisson noise. """
        return self.__poissonize
    @poissonize.setter
    def poissonize(self, val):
        """ Set the 'poissonize' flag."""
        # Handle default.
        if val is None:
            val = True
        if not isinstance(val, bool):
            raise TypeError('The parameter "poissonize" must be a bool.')

        self.__poissonize = val


    def patternGenerator(self):
        """ Yield an iterator over a given pattern sequence from a diffraction file.
        """
        indices = self.pattern_indices
        path = self.input_path
        if os.path.isdir(path): # legacy format.
            dir_listing = os.listdir(path)
            dir_listing.sort()
            if indices != 'all':
                dir_listing = [d for (i,d) in enumerate(dir_listing) if i in indices]
            h5_files = [os.path.join(path, f) for f in dir_listing if f.split('.')[-1] == "h5"]
            for h5_file in h5_files:
                try:
                    with h5py.File(h5_file, 'r') as h5:
                        root_path = '/data/'
                        if self.poissonize:
                            path_to_data = root_path + 'data'
                        else:
                            path_to_data = root_path + 'diffr'

                        diffr = h5[path_to_data].value

                        yield diffr
                except:
                    continue

        else: # v0.2
            # Open file for reading
            with h5py.File(path, 'r') as h5:
                if indices is None or indices == 'all':
                    indices = [key for key in h5['data'].iterkeys()]
                else:
                    indices = ["%0.7d" % ix for ix in indices]
                for ix in indices:
                    root_path = '/data/%s/'% (ix)
                    if self.poissonize:
                        path_to_data = root_path + 'data'
                    else:
                        path_to_data = root_path + 'diffr'

                    diffr = h5[path_to_data].value

                    yield diffr



    def plotPattern(self, operation=None, logscale=False):
        """ Plot a pattern.

        :param operation: Operation to apply to the given pattern(s).
        :type operation: function
        :note operation: Function must accept the "axis" keyword-argument. Axis will always be chosen as axis=0.
        :rtype operation: 2D numpy.array

        :param logscale: Whether to plot the intensity on a logarithmic scale (z-axis) (default False).
        :type logscale: bool

        """

        # Handle default operation
        if operation is None:
            operation = numpy.sum

        # Complain if operating on single pattern.
        else:
            if len(self.pattern_indices) == 1:
                print "WARNING: Giving an operation with a single pattern has no effect."
        # Get pattern to plot.
        pi = self.patterns_iterator
        if len(self.pattern_indices) == 1:
            pattern_to_plot = pi.next()
        else:
            pattern_to_plot = operation(numpy.array([p for p in pi]), axis=0)

        # Plot image and colorbar.
        plotImage(pattern_to_plot, logscale)

        # Plot resolution rings.
        plotResolutionRings(self.__parameters)

    def statistics(self):
        """ Get basic statistics from queried patterns. """

        pi = self.patterns_iterator
        stack = numpy.array([p for p in pi])

        photonStatistics(stack)

def diffractionParameters(path):
    """ Extract beam parameters and geometry from given file or directory.

    :param path: Path to file that holds the parameters to extract.
    :type path: str

    """

    # Check if old style.
    if os.path.isdir(path):
        h5_file = os.path.join(path, "diffr_out_0000001.h5")
    elif os.path.isfile(path):
        h5_file = path
    else:
        raise IOError("%s: no such file or directory." % (path))

    # Setup return dictionary.
    parameters_dict = {'beam':{}, 'geom':{}}

    # Open file.
    with h5py.File(h5_file, 'r') as h5:
        # Loop over entries in /params.
        for top_key in ['beam', 'geom']:
            # Loop over groups.
            for key, val in h5['params/%s' % (top_key)].iteritems():
                # Insert into return dictionary.
                parameters_dict[top_key][key] = val.value

    # Return.
    return parameters_dict


def plotImage(pattern, logscale=False):
    """ Workhorse function to plot an image

    :param logscale: Whether to show the data on logarithmic scale (z axis) (default False).
    :type logscale: bool

    """
    plt.figure()
    # Get limits.
    mn, mx = pattern.min(), pattern.max()

    if logscale:
        if mn <= 0.0:
            mn += pattern.min()+1e-5
            pattern = pattern.astype(float) + mn
        plt.imshow(pattern, norm=mpl.colors.LogNorm(vmin=mn, vmax=mx), cmap="viridis")
    else:
        plt.imshow(pattern, norm=Normalize(vmin=mn, vmax=mx), cmap='viridis')

    plt.xlabel(r'$x$ (pixel)')
    plt.ylabel(r'$y$ (pixel)')
    plt.colorbar()

def plotResolutionRings(parameters):
    """
    Show resolution rings on current plot.

    :param parameters: Parameters needed to construct the resolution rings.
    :type parameters: dict

    """

    # Extract parameters.
    beam = parameters['beam']
    geom = parameters['geom']

    # Photon energy and wavelength
    E0 = beam['photonEnergy']
    lmd = 1239.8 / E0

    # Pixel dimension
    apix = geom['pixelWidth']
    # Sample-detector distance
    Ddet = geom['detectorDist']
    # Number of pixels in each dimension
    Npix = geom['mask'].shape[0]

    # Max. scattering angle.
    theta_max = math.atan( 0.5*Npix * apix / Ddet )
    # Min resolution.
    d_min = 0.5*lmd/math.sin(theta_max)

    # Next integer resolution.
    d0 = 0.1*math.ceil(d_min*10.0) # 10 powers to get Angstrom

    # Array of resolution rings to plot.
    ds = numpy.array([1.0, 0.5, .3])

    # Pixel numbers corresponding to resolution rings.
    Ns = Ddet/apix * numpy.arctan(numpy.arcsin(lmd/2./ds))

    # Plot each ring and attach a label.
    for i,N in enumerate(Ns):
        x0 = 0.5*Npix
        X = numpy.linspace(x0-N,x0+N, 512)
        Y_up = x0 + numpy.sqrt(N**2 - (X-x0)**2)
        Y_dn = x0 - numpy.sqrt(N**2 - (X-x0)**2)
        plt.plot(X,Y_up,color='k')
        plt.plot(X,Y_dn,color='k')
        plt.text(0.5*Npix+0.75*N,0.5*Npix+0.75*N, "%2.1f" % (ds[i]*10.))

    plt.xlim(0,Npix)
    plt.ylim(0,Npix)

def photonStatistics(stack):
    """ """

    number_of_images = stack.shape[0]
    photons = numpy.sum(stack, axis=(1,2))
    avg_photons = numpy.mean(photons)
    rms_photons =  numpy.std(photons)

    print "***********************"
    print "avg = %s, std = %s" % (avg_photons, rms_photons)
    print "***********************"


    # Plot histogram.
    plt.figure()
    max_photon_number = numpy.max( photons )
    min_photon_number = numpy.min( photons )
    binwidth = max_photon_number - min_photon_number
    number_of_bins = min(20, number_of_images)
    binwidth = int( binwidth / number_of_bins )

    plt.hist(photons, bins=xrange(min_photon_number, max_photon_number, binwidth), facecolor='red', alpha=0.75)
    plt.xlim([min_photon_number, max_photon_number])
    plt.xlabel("Photons")
    plt.ylabel("Histogram")
    plt.title("Photon number histogram")

    #pylab.figure(2)
    ## Average
    #sum_over_images = 1.0*sum_over_images / number_of_samples
    ## Offset for log scale.
    ##sum_over_images += 0.01 * numpy.min(sum_over_images[numpy.where(sum_over_images > 0)])
    #sum_over_images += 1e-4
    #vmax=10.
    #vmin=1.0e-4
    #raw_input([vmin, vmax])
    #pylab.pcolor(sum_over_images,norm=LogNorm(vmax=vmax, vmin=vmin), cmap='YlGnBu_r')
    ##pylab.pcolor(sum_over_images, cmap='YlGnBu_r')
    #pylab.colorbar()

    #pylab.figure(3)
    #pylab.semilogy( numpy.sum( sum_over_images, axis=0 ), label='x axis projection')
    #pylab.semilogy( numpy.sum( sum_over_images, axis=1 ), label='y axis projection')

    #pylab.legend()
    #pylab.show()


def animate(h5):
    root_path = '/data/'

    img = h5[root_path+'0000001/diffr'].value

    keys = h5[root_path].keys()

    rands = numpy.random.choice(range(len(keys)), 20)
    keys = [keys[i] for i in rands]
    stack = numpy.empty((len(keys), img.shape[0], img.shape[1]))

    for i,key in enumerate(keys):
        print "Reading %s" % (key)
        stack[i] = h5[root_path][key]['diffr'].value

    mn, mx = stack.min(), stack.max()
    print "Range = [", mn,",", mx,"]"
    for i,img in enumerate(stack):
        plt.pcolor(img, norm=LogNorm(vmin=mn, vmax=mx), cmap='viridis')
        plotResolutionRings()
        plt.title(keys[i])
        plt.colorbar()
        plt.savefig("%s.png" % (keys[i]))
        plt.clf()

#if __name__ == "__main__":

    #filename = sys.argv[1]
    #pattern_number = 1
    #if len(sys.argv) > 2:
        #pattern_number = sys.argv[2]

    #main(filename, pattern_number)

