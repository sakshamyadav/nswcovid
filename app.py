import pandas as pd
import numpy as np
import folium
from folium.plugins import Search
import geopandas
from shapely.geometry import Point
import altair as alt
import vincent
import json
import cufflinks as cf
from folium import IFrame


def update_map():
	area = pd.read_csv("https://data.nsw.gov.au/data/dataset/97ea2424-abaf-4f3e-a9f2-b5c883f42b6a/resource/2776dbb8-f807-4fb2-b1ed-184a6fc2c8aa/download/covid-19-cases-by-notification-date-location-and-likely-source-of-infection.csv")
	postcodes = pd.read_csv("australian_postcodes.csv")
	testing = pd.read_csv("https://data.nsw.gov.au/data/dataset/5424aa3b-550d-4637-ae50-7f458ce327f4/resource/227f6b65-025c-482c-9f22-a25cf1b8594f/download/covid-19-tests-by-date-and-location-and-result.csv")
	area = area.rename(columns={"likely_source_of_infection": "Source"})
	testing = testing.rename(columns={"result": "Test Result"})
	testing['Test Result']= testing['Test Result'].replace({'Tested & excluded': 'Negative Test', 'Case - Confirmed': 'Positive Test'})
	area['Source']= area['Source'].replace({'Locally acquired - contact of a confirmed case and/or in a known cluster': 'Local (Known Source)', 'Locally acquired - source not identified': 'Local (Unknown Source)', 'Under investigation': 'Under Investigation'})

	area = area.dropna()
	area = area.merge(postcodes, on='postcode', how='inner')

	source_area = area.copy()
	source_area = source_area.groupby(['notification_date', 'postcode', 'Source']).count()
	source_area = source_area.reset_index()

	testing_area = testing.dropna()
	testing_area = testing_area.groupby(['test_date', 'postcode', 'Test Result']).count()
	testing_area = testing_area.reset_index()

	chart_area = area.copy()
	chart_area = chart_area.groupby(['notification_date', 'postcode']).count()
	chart_area = chart_area.reset_index()

	area['Cases'] = area['postcode'].map(area['postcode'].value_counts())
	area =area.sort_values('notification_date').drop_duplicates('postcode',keep='last')
	geometry = [Point(xy) for xy in zip(area.long, area.lat)]
	a = area.drop(['long', 'lat'], axis=1)
	crs = {'init': 'epsg:4326'}
	gdf = geopandas.GeoDataFrame(a, crs=crs, geometry=geometry)

	#FOLIUM START
	start_coords = (-33.86051951, 151.2015802)
	m = folium.Map(location=start_coords, zoom_start=14, min_zoom = 8, width = '100%', height = '100%')


	for index, row in area.iterrows():

		source_subset = source_area[source_area['postcode']==row['postcode']]
		test_subset = testing_area[testing_area['postcode'] == row['postcode']]
		subset = chart_area[chart_area['postcode']==row['postcode']]
		subset['cumul'] = subset['long'].cumsum()

		chart = alt.Chart(source_subset).mark_bar(cornerRadiusTopLeft=3,
    cornerRadiusTopRight=3).encode(
		x=alt.X('notification_date', axis=alt.Axis(title='Date')),
		y=alt.Y('long', axis=alt.Axis(title='New Cases')),
		color = alt.Color('Source', legend = alt.Legend(orient="left")),
		tooltip = [alt.Tooltip('notification_date', title = "Date"), alt.Tooltip('Source', title = "Source"), alt.Tooltip('long', title = "New Cases")]
		).properties(
			title = "New Cases in Postcode "+str(int(row['postcode']))+" (Latest Case: "+row['notification_date']+")",
			width = 500,
			height = 200

		)

		cum_chart = alt.Chart(subset).mark_line(point=True).encode(
			x=alt.X('notification_date', axis=alt.Axis(title='Date')),
			y=alt.Y('cumul', axis=alt.Axis(title='Total Cases (Cumulative)')),
			tooltip = [alt.Tooltip('notification_date', title = "Date"), alt.Tooltip('cumul', title = "Total Cases")]
		).properties(
			title = "Total Cases in Postcode "+str(int(row['postcode']))+" (Current Total: "+str(int(row['Cases']))+")",
			width = 500,
			height = 200
		)

		#test_chart = alt.Chart(test_subset).mark_bar(cornerRadiusTopLeft=3,
    	#cornerRadiusTopRight=3).encode(
		#x=alt.X('test_date', axis=alt.Axis(title='Date')),
		#y=alt.Y('lga_code19', axis=alt.Axis(title='Tests Conducted')),
		#color = alt.Color('Test Result', legend = alt.Legend(orient="left")),
		#tooltip = [alt.Tooltip('test_date', title = "Date"), alt.Tooltip('Test Result', title = "Test Result"), alt.Tooltip('lga_code19', title = "Number")]
		#).properties(
		#	title = "Number of Tests in Postcode "+str(int(row['postcode']))+" (Total Tested: "+str(int(test_subset['lga_code19'].sum()))+")"+" - Testing data decomissioned as of 8th June",
		#	width = 1000,
		#	height = 200
		#)

		#chart = alt.hconcat(test_chart, chart, cum_chart).resolve_scale(color='independent')
		chart = alt.hconcat(chart, cum_chart).resolve_scale(color='independent')
		chart.save('chart.html', embed_options={'renderer':'svg'})

		with open('chart.html', 'r') as f:
			html = f.read()
		iframe = IFrame(html, height = 330, width = 600)
		popup = folium.Popup(iframe, max_width=2650)

		#day
		if row['notification_date'] >='2020-09-04':
			marker_color = 'red'
			fill_color = 'red'
		#week
		elif row['notification_date'] >= '2020-08-28':
			marker_color = 'blue'
			fill_color = 'blue'
		else:
			marker_color = 'green'
			fill_color = 'green'

		
		folium.Circle(
			  location=[row['lat'], row['long']],		  
			  tooltip=row['name'],
			  radius=row['Cases']*10,
			  color=marker_color,
			  fill=True,
			  fill_color=fill_color,
			popup= popup
		).add_to(m)

		print(row['postcode'], 'done')

	citygeo = folium.GeoJson(
		gdf, 
		show = False,
		name = 'Marker'
	).add_to(m)

	pcsearch = Search(
		layer=citygeo,
		geom_type='Point',
		placeholder='Search for an NSW postcode',
		collapsed=True,
		search_label= 'postcode',
		position = 'topleft',
		search_zoom = 14
	).add_to(m)

	subsearch = Search(
		layer=citygeo,
		geom_type='Point',
		placeholder='Search for an NSW suburb',
		collapsed=True,
		search_label= 'name',
		position = 'topright',
		search_zoom = 14
	).add_to(m)

	folium.LayerControl().add_to(m)

	m.save('templates/index.html')
	print('done')

#remember to update html file with adsense and analytics
update_map()

