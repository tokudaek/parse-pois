#!/usr/bin/env python
""" Compute the voronoi diagram provided the map and seeds
"""

import argparse
import logging
from logging import debug, info
import numpy as np
import pandas as pd
import scipy.spatial as spatial
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.path as path
import matplotlib as mpl
from matplotlib import patches
import smopy
import fiona
from shapely import geometry
from descartes import PolygonPatch
import copy
from scipy.spatial import KDTree
import itertools
# import os
from os.path import join as pjoin


##########################################################
def load_map(shppath):
    """Load shapefile map

    Args:
    shppath(str): path to the shapefile

    Returns:
    geometry.Polygon: hull polygon
    """

    shape = fiona.open(shppath)
    b = next(iter(shape))
    p = b['geometry']['coordinates'][0]
    x = [z[0] for z in p ]
    y = [z[1] for z in p ]
    poly = geometry.Polygon(p)
    return poly
    
##########################################################
def get_encbox_from_borders(poly):
    """Get enclosing box from borders

    Args:
    poly(shapely.geometry): arbitrary shape polygon

    Returns:
    int, int, int, int: xmin, ymin, xmax, ymax
    """
    return poly.bounds

##########################################################
def get_crossing_point_rectangle(v0, alpha, orient, encbox):
    mindist = 999999999

    for j, c in enumerate(encbox):
        i = j % 2
        d = (c - v0[i]) # xmin, ymin, xmax, ymax
        if alpha[i] == 0: d *= orient
        else: d = d / alpha[i] * orient
        if d < 0: continue
        if d < mindist: mindist = d

    p = v0 + orient * alpha * mindist
    return p

##########################################################
def get_bounded_polygons(vor, newvorvertices, newridgevertices, encbox):
    newvorregions = copy.deepcopy(vor.regions)
    newvorregions = np.array([ np.array(f) for f in newvorregions])

    # Update voronoi regions to include added vertices and corners
    for regidx, rr in enumerate(vor.regions):
        reg = np.array(rr)
        if not np.any(reg == -1): continue
        foo = np.where(vor.point_region==regidx)
        seedidx = foo[0]

        newvorregions[regidx] = copy.deepcopy(rr)
        # Looking for ridges bounding my point
        for ridgeid, ridgepts in enumerate(vor.ridge_points):
            # print(ridgeid, ridgepts)
            if not np.any(ridgepts == seedidx): continue
            ridgevs = vor.ridge_vertices[ridgeid]
            if -1 not in ridgevs: continue # I want unbounded ridges
            myidx = 0 if ridgevs[0] == -1 else 1

            newvorregions[regidx].append(newridgevertices[ridgeid][myidx])
        if -1 in newvorregions[regidx]:  newvorregions[regidx].remove(-1)

    tree = KDTree(vor.points)
    corners = itertools.product((encbox[0], encbox[2]), (encbox[1], encbox[3]))
    ids = []

    for c in corners:
        dist, idx = tree.query(c)
        k = len(newvorvertices)
        newvorvertices = np.row_stack((newvorvertices, c))
        newvorregions[vor.point_region[idx]].append(k)

    convexpolys = []
    for reg in newvorregions:
        if len(reg) == 0: continue
        points = newvorvertices[reg]
        hull = spatial.ConvexHull(points)
        pp = points[hull.vertices]
        convexpolys.append(pp)
    return convexpolys

##########################################################
def plot_finite_ridges(ax, vor):
    """Plot the finite ridges of voronoi

    Args:
    ax(matplotlib.Axis): axis to plot
    vor(spatial.Voronoi): instance generated by spatial.Voronoi
    """

    for simplex in vor.ridge_vertices:
        simplex = np.asarray(simplex)
        if np.any(simplex < 0): continue
        ax.plot(vor.vertices[simplex, 0], vor.vertices[simplex, 1], 'k-')

##########################################################
def create_bounded_ridges(vor, encbox, ax=None):
    """Create bounded voronoi vertices bounded by encbox

    Args:
    vor(spatial.Voronoi): voronoi structure
    encbox(float, float, float, float): xmin, ymin, xmax, ymax

    Returns:
    ret
    """

    center = vor.points.mean(axis=0)
    newvorvertices = copy.deepcopy(vor.vertices)
    newridgevertices = copy.deepcopy(vor.ridge_vertices)

    for j in range(len(vor.ridge_vertices)):
        pointidx = vor.ridge_points[j]
        simplex = vor.ridge_vertices[j]
        simplex = np.asarray(simplex)
        if np.any(simplex < 0):
            i = simplex[simplex >= 0][0] # finite end Voronoi vertex
            t = vor.points[pointidx[1]] - vor.points[pointidx[0]]  # tangent
            t = t / np.linalg.norm(t)
            n = np.array([-t[1], t[0]]) # normal
            # input(n)
            midpoint = vor.points[pointidx].mean(axis=0)
            orient = np.sign(np.dot(midpoint - center, n))
            far_point_clipped = get_crossing_point_rectangle(vor.vertices[i],
                                                             n,
                                                             orient,
                                                             encbox)
            ii = np.where(simplex < 0)[0][0] # finite end Voronoi vertex
            kk = newvorvertices.shape[0]
            newridgevertices[j][ii] = kk
            newvorvertices = np.row_stack((newvorvertices, far_point_clipped))
            if ax == None: continue
            ax.plot([vor.vertices[i,0], far_point_clipped[0]],
                     [vor.vertices[i,1], far_point_clipped[1]], 'k--')

            ax.plot(far_point_clipped[0], far_point_clipped[1], 'og')
    return newvorvertices, newridgevertices

def plot_bounded_ridges(ax, polys):
    for p in polys:
        pgon = plt.Polygon(p, color=np.random.rand(3,), alpha=0.5)
        ax.add_patch(pgon)
    ax.autoscale_view()
##########################################################
def plot_bounded_voronoi(ax, vor, b):
    ax.plot(vor.points[:, 0], vor.points[:, 1], 'o') # Plot seeds (points)
    ax.plot(vor.vertices[:, 0], vor.vertices[:, 1], 's') # Plot voronoi vertices

    plot_finite_ridges(ax, vor)

    newvorvertices, newridgevertices = create_bounded_ridges(vor, b)
    ax.add_patch(patches.Rectangle(b[0:2], b[2]-b[0], b[3]-b[1],
                                   linewidth=1, edgecolor='r', facecolor='none'))
    cells = get_bounded_polygons(vor, newvorvertices, newridgevertices, b)

    plot_bounded_ridges(ax, cells)
    return cells


##########################################################
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('shp', help='Map in shapefile')
    parser.add_argument('pois', help='POIs in csv')
    parser.add_argument('--outdir', required=False, default='/tmp/', help='POIs in csv fmt')
    args = parser.parse_args()

    logging.basicConfig(format='[%(asctime)s] %(message)s',
    datefmt='%Y%m%d %H:%M', level=logging.INFO)

    figs, axs = plt.subplots(1, 3, figsize=(35, 15))

    mappoly = load_map(args.shp)
    bbox = get_encbox_from_borders(mappoly)
    df = pd.read_csv(args.pois) # Load seeds

    vor = spatial.Voronoi(df[['lon', 'lat']].to_numpy()) # Compute regular Voronoi

    spatial.voronoi_plot_2d(vor, ax=axs[0]) # Plot default unbounded voronoi

    cells = plot_bounded_voronoi(axs[1], vor, bbox)

    from descartes import PolygonPatch
    for c in cells:
        poly = geometry.Polygon(c)
        polygon1 = poly.intersection(mappoly)
        x,y = polygon1.exterior.xy
        z = list(zip(*polygon1.exterior.coords.xy))
        axs[2].add_patch(patches.Polygon(z, linewidth=2, edgecolor='r',
                                         facecolor=np.random.rand(3,)))
    axs[2].autoscale_view()

    plt.savefig(pjoin(args.outdir, 'out.pdf'))

if __name__ == "__main__":
    main()
