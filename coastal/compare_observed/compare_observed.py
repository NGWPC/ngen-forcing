#! /usr/bin/env python

import os, sys, time, urllib, getopt, glob, re
import logging
import argparse
import math
from datetime import datetime, timedelta
import dateutil.parser
import numpy as np
from scipy.spatial import cKDTree
import netCDF4
import matplotlib.dates as mdates
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.ticker import MultipleLocator, FormatStrFormatter, Formatter
from matplotlib.ticker import FuncFormatter
import matplotlib.ticker as ticker
from SCHISMOutput import SCHISMOutput
from NOAAObservedWL import NOAAObservedWL

def list_of_strings(arg):
    return arg.split(',')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('schism_output_dir', type=str, help='schism output directory')
    parser.add_argument('station_list', type=list_of_strings, help='list of the observed station IDs')
    parser.add_argument('observed_wl_dir', type=str, help='Observed water level files')
    parser.add_argument('output_dir', type=str, help='output directory for the comparison figures')

    args = parser.parse_args()

    schism_output_dir = args.schism_output_dir
    outputfiles = sorted( glob.glob( schism_output_dir +'/out2d_*.nc'),
               key=lambda x:float(re.findall("out2d_(\d+)\.nc",x)[0]) ) #path to, and name of the output files

    schismout = []
    for f in outputfiles:
#       print( f )
       schismout.append( SCHISMOutput( f ) )

    #stations = ['9751364', '9751639', '9755371', '9759938', '9751381', '9752235', '9759110', '9751401', 
    #            '9752695', '9759394' ]
    stations = args.station_list

#    test the cKDtree algorithm
#
#    #"lat": "21.9544",
#    #"lon": "-159.3561"
#    dist = 999.0;
#    node = 0
#    for n in range( 0, schismout[0].nnodes ):
#       temp = ( schismout[0].lons[ n ] - (-159.3561)) *              \
#               ( schismout[0].lons[ n ] - (-159.3561)) +             \
#               ( schismout[0].lats[ n ] - (21.9544) ) *              \
#               ( schismout[0].lats[ n ] - (21.9544) )
#       if temp < dist:
#           dist = temp
#           node = n
#       print( "n = ", n, " (", schismout[0].lons[ n ], ',', schismout[0].lats[ n ], ")")
#
#    print( " dist = ", dist )
#    print( "node lat = ", schismout[0].lats[ node ] )
#    print( "node lon = ", schismout[0].lons[ node ] )
#    print( "node = ", node )

    
    schism_nodes = np.column_stack([schismout[0].lons,schismout[0].lats])
    tree = cKDTree(schism_nodes)

    for s in stations:
       try:
         obv = NOAAObservedWL( f"{args.observed_wl_dir}/{s}.json" )
       except (FileNotFoundError, ValueError) as e: 
        print( e )
        print( f"Warning: Skipping station {s}" )
        continue

#       print( obv.data['metadata'] )
       dist, idx = tree.query([[ float( obv.data['metadata'][ 'lon'] ), float( obv.data['metadata'][ 'lat'] ) ]])
#       print( "obv :", obv.data['metadata'][ 'lon'], obv.data['metadata'][ 'lat'] )
#       print( "s = ", s, idx, dist )
#       print( schismout[0].lats[ idx[0] ], schismout[0].lons[ idx[0] ] )
#       print( schismout[0].lats[ idx[0] ] - float( obv.data['metadata']['lat'] ), 
#               schismout[0].lons[ idx[0] ] - float( obv.data['metadata'][ 'lon' ] ) )
#       print( "============================" )

       elev_date = []
       elev_value = []
       for o in schismout:
          elev_date.append( o.valid_time )
#          print( f"{ o.valid_time.strftime('%Y%m%d%H')} z = { o.elev[ idx[0] ]:10.5} d = { o.depth[ idx[0] ]:10.5} " )
          elev_value.append( o.elev[ idx[0] ] )
#       print( elev_value )

       obv_elev_date = []
       obv_elev_value = []
       for o in obv.data['data']:
#         print( o['t'], o['v'] )
         obv_elev_date.append( datetime.strptime( o['t'], "%Y-%m-%d %H:%M") )
         obv_elev_value.append( float( o['v'] ) )

       fig = Figure()
       canvas = FigureCanvas(fig)

       ax = fig.add_subplot(111)
       ax.xaxis.set_major_formatter( mdates.DateFormatter('%b %d' ))
       ax.xaxis.set_minor_formatter( mdates.DateFormatter('%Hz' ))

       ax.xaxis.set_major_locator( mdates.DayLocator() )
       ax.xaxis.set_minor_locator( mdates.HourLocator( interval=2) )

       ax.yaxis.set_major_locator(ticker.AutoLocator())
       ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())

       ax.tick_params(axis='x', rotation=90)

       ax.set_xlim( elev_date[0] - timedelta( hours=1), \
		elev_date[-1] + timedelta( hours = 1 ) )

       #set the y limit
       obv_trimed_date = []
       obv_trimed_elev = []
       for t, v in zip ( obv_elev_date, obv_elev_value ):
           if t <= elev_date[-1] and t >= elev_date[0]:
               obv_trimed_date.append( t )
               obv_trimed_elev.append( v )

       ymax = max( obv_trimed_elev )
       if ymax < max( elev_value ):
           ymax = max( elev_value )
       ax.set_ylim( top = ymax )

       ymin = min( obv_trimed_elev )
       if ymin > min( elev_value ):
           ymin = min( elev_value )
       ax.set_ylim( bottom=ymin, top = ymax )

       ax.grid( True, "minor", "x" )
       ax.grid( True, "major", "y" )

       #box = ax.get_position()
       #ax.set_position([box.x0, box.y0, box.width * 0.8, box.height])

       ax.set_xlabel( 'Time' )
       ax.set_ylabel( 'Elevation (m)' )
       ax.set_title( f"Station ID: {s} ({obv.data['metadata'][ 'lon']}, {obv.data['metadata'][ 'lat']})" )

       elevplot, = ax.plot_date( obv_trimed_date, obv_trimed_elev, \
	      label='obv', \
            fmt='o-', markersize=5, markerfacecolor='None', color='k' )

       elevplot, = ax.plot_date( elev_date, elev_value, \
		label='sim', \
                fmt='x:', markersize=5, markerfacecolor='None', color='k' )

       lgd = ax.legend( bbox_to_anchor=(1.02, 1), loc=2, borderaxespad=0. ) 

       #ax.legend(loc='center', ncol=3, bbox_to_anchor=(0.5,-0.23))
       #ax.legend( loc=2 ) 
       art=[ lgd ]

       fig.text(0.5, 0.8, f"Node seq: {idx[0]}({schismout[0].lons[idx[0]]}, {schismout[0].lats[idx[0]]})",
                horizontalalignment="center")
       #canvas.print_figure(out, additional_artists=art, bbox_inches='tight')
       canvas.print_figure(args.output_dir + "/" + s, bbox_inches='tight')

       #write the text files
       with open( args.output_dir + "/" + s + "_sim.txt", 'w') as txtfile:
           txtfile.write( f"#SCHISM node seq: {idx[0]} lon: {schismout[0].lons[idx[0]]} lat:{schismout[0].lats[idx[0]]}\n" )
           txtfile.write( f"#time(YYYYmmdd_HH:MM)    elevation above sea level (m)\n" )
           for t,d in zip( elev_date, elev_value ):
               txtfile.write( f"{t.strftime('%Y%m%d_%H:%M')} {d}\n" )
       with open( args.output_dir + "/" + s + "_obv.txt", 'w') as txtfile:
           txtfile.write( f"#{obv.data['metadata']}\n" )
           txtfile.write( f"#time(YYYYmmdd_HH:MM)    elevation above sea level (m)\n" )
           for t,d in zip( obv_elev_date, obv_elev_value ):
               txtfile.write( f"{t.strftime('%Y%m%d_%H:%M')} {d}\n" )

if __name__ == "__main__":
   try:
      main()
   except Exception as e:
      logger.error("Failed to get program options.", exc_info=True)

