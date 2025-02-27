from swe_timeseries.swe_timeseries import main

main(['sample_csv/09359500', 
	  'sample_gpkg/gages-09359500.gpkg',
	  '2019-10-02',
	  '2020-09-29',
	  '--plot_output', 'comb_plot.png',
	  '--csv_output','comb_table.csv'
	  ])
