import ERROR_CODES as ec
from GLOBAL_VARS import ITERATION_LENGTH, CITY_CENTERPT_LEIPZIG
from DB_helpers import open_connection
from helpers_geometry import calculate_start_end_pt, calculate_bounding_box, find_angle_to_x, calculate_slope, get_y_intercept, segment_iteration_condition, calculate_specific_street_width
from helpers_coordiantes import convert_coords, sort_coords, shift_pt_along_street
from PATH_CONFIGS import RES_FOLDER_PATH, DB_CONFIG_FILE_NAME, DB_USER

import operator
import json

def create_segm_gid_relation(db_config, db_user):
    print('Creating area_segment_relation table ....')

    with open_connection(db_config, db_user) as con:

        cursor = con.cursor()
        cursor.execute("""CREATE TABLE area_segment_relation AS SELECT id AS area_id, segm_gid FROM trafficareas;""")
        cursor.execute("""ALTER TABLE area_segment_relation ADD COLUMN multiple_areas boolean, ADD COLUMN segment_id int""")

        cursor.execute("""SELECT segm_gid FROM area_segment_relation""")
        #iterate all segm_gids and get the segment Id and the number of segm_gis in area table
        for segm_gid in cursor.fetchall():
            segm_gid = segm_gid[0]
       
            cursor.execute("""SELECT id FROM segments WHERE segm_gid = (%s)""",(segm_gid,))
            res = cursor.fetchone()
            if res is None:
                continue
            else:
                segment_id = res[0]

            cursor.execute("""SELECT count(segm_gid) FROM trafficareas WHERE segm_gid = (%s)""",(segm_gid,))
            num_entries = cursor.fetchone()
            if num_entries is None:
                num_entries = None

            if num_entries[0] == 1:
                cursor.execute("""UPDATE area_segment_relation 
                                    SET segment_id = %s, multiple_areas = FALSE
                                    WHERE segm_gid = %s""",(segment_id, segm_gid,))
            if num_entries[0] > 1:
                cursor.execute("""UPDATE area_segment_relation 
                                SET segment_id = %s, multiple_areas = TRUE
                                WHERE segm_gid = %s""",(segment_id, segm_gid,))
                
            
def create_iteration_segments(str_start, str_end, width):
    print("Creating iteration segments")
    iteration_segments = []
    # width is multiplied with a factor
    width = calculate_specific_street_width(width)

    x_angle = find_angle_to_x([str_start, str_end])
    slope = calculate_slope([str_start, str_end])
    if slope == None:
        b = 0
    else:
        b = get_y_intercept(str_start, slope)

    #first
    x_shifted, y_shifted = shift_pt_along_street((str_start[0], str_start[1]), x_angle, ITERATION_LENGTH, slope, b)
    # [start_left, end_left, end_right, start_right]
    bbox = calculate_bounding_box([str_start, (x_shifted, y_shifted)], width)
    iteration_segments.append(bbox)
    
    while segment_iteration_condition(slope, x_angle, str_start, str_end, x_shifted, y_shifted):
        x_shifted_2, y_shifted_2 = shift_pt_along_street((x_shifted, y_shifted), x_angle, ITERATION_LENGTH, slope, b)
        bbox = calculate_bounding_box([(x_shifted, y_shifted), (x_shifted_2, y_shifted_2)], width)
        iteration_segments.append(bbox)
        x_shifted, y_shifted = x_shifted_2, y_shifted_2
    
    #last
    bbox = calculate_bounding_box([(x_shifted, y_shifted), (str_end[0], str_end[1])], width)
    iteration_segments.append(bbox)

    return iteration_segments


 # get width of street segment
def get_traffic_area_width(segm_gid, cursor):

    cursor.execute("""SELECT multiple_areas from area_segment_relation WHERE segm_gid =  %s""", (segm_gid, ))
    res = cursor.fetchone()
    if res == None:
        return 0
    
    multiple_areas = res[0]
    if not multiple_areas:
        cursor.execute("""SELECT median_breite FROM trafficareas WHERE segm_gid = %s""", (segm_gid, ))
        median_breite = cursor.fetchone()

        if median_breite == []:
            print("[!] NO WIDTH FOR SEGMENT ", segm_gid)
            return ec.NO_WIDTH
        else:
            median_breite = median_breite[0]+ (1/3*median_breite[0])
            return median_breite
    else:
        return 0


# bbox = [start_left, end_left, end_right, start_right]
def write_bboxes_to_DB(bboxes, cursor, segment_id, segmentation_number):
    print("write iteration bboxes to DB")
    for idx, bbox in enumerate(bboxes):
        left_coords = [bbox[0], bbox[1]]
        right_coords = [bbox[3], bbox[2]]
        #print(left_coords,right_coords)
        # left_coords = [convert_coords("EPSG:25833", "EPSG:4326", coord[0], coord[1]) for coord in left_coords]
        # right_coords = [convert_coords("EPSG:25833", "EPSG:4326", coord[0], coord[1]) for coord in right_coords]

        cursor.execute("""
                        INSERT INTO segments_segmentation_iteration
                        VALUES (%s, %s, %s, %s, %s)""", (segment_id, segmentation_number, idx, json.dumps(left_coords), json.dumps(right_coords), ))
    

# for every segment in the segments table check, if the segment is sectioned into more than one piece (Len(coords) > 2) if yes => segment has a bend
# for every segment add information if it is segmented and if yes the specific start end coordinates of the segmented segment to a table segments_segmentation
def create_segmentation(db_config, db_user):
    print('Creating segmentations ....')

    with open_connection(db_config, db_user) as con:
        cursor = con.cursor()
        cursor.execute("""SELECT id, segm_gid, geom_type, geom_coordinates FROM segments""")
        result = cursor.fetchall()

        for idx, res_item in enumerate(result):
            segment_id, segm_gid, geom_type, geom_coords = res_item[0], res_item[1], res_item[2], res_item[3]
            print("segmentid", segment_id)
          
            # geom_type can be LineString or MultiLineString
            #TODO: Multilinestring
            if geom_type == "LineString":
        
                #TODO: check if segment exists already?
                converted_coords = [convert_coords("EPSG:25833", "EPSG:4326", pt[0], pt[1]) for pt in geom_coords]
                str_start, str_end = calculate_start_end_pt(converted_coords)
                sorted_coords = sort_coords(converted_coords, str_start)
                
                # if sorting method didnt work TODO: find way to sort coords
                if sorted_coords != []:
                    sorted_coords = [convert_coords("EPSG:4326", "EPSG:25833", pt[0], pt[1]) for pt in sorted_coords]
                else:
                    cursor.execute("""INSERT INTO segments_segmentation VALUES (%s, %s, %s, %s, %s, %s) """, (segment_id, ec.WRONG_COORD_SORTING,  ec.WRONG_COORD_SORTING, ec.WRONG_COORD_SORTING, ec.WRONG_COORD_SORTING, ec.WRONG_COORD_SORTING, ))
                    con.commit()
                    continue

                # if more than two coordinates, street has a bend => 
                # partition the segment further and extract every two pairs of coordinate
                if len(sorted_coords) > 2:
                    width = get_traffic_area_width(segm_gid, cursor)
                    if width == ec.NO_WIDTH:
                        print("[!!] SKIP: no width for segment: ", segm_gid)
                        cursor.execute("""INSERT INTO segments_segmentation VALUES (%s, %s, %s, %s, %s, %s) """, (segment_id, ec.NO_WIDTH,  ec.NO_WIDTH, ec.NO_WIDTH, ec.NO_WIDTH, ec.NO_WIDTH, ))
                        con.commit()
                        continue

                    segmentation_counter = 1
                    for i in range(0,len(sorted_coords)):
                        try:
                            cursor.execute("""INSERT INTO segments_segmentation VALUES (%s, %s, %s, %s, %s, %s) """, (segment_id, segmentation_counter,  sorted_coords[i][0], sorted_coords[i][1], sorted_coords[i+1][0], sorted_coords[i+1][1], ))
                            con.commit()
                            segmentation_counter += 1

                        except IndexError:
                            break  
                     
                    # add segmentation for iteration length
                    segmentation_counter = 1
                    for i in range(0,len(sorted_coords)):
                        
                        try:
                            if width != 0:
                                iteration_segments_bboxes = create_iteration_segments((sorted_coords[i][0], sorted_coords[i][1]), (sorted_coords[i+1][0], sorted_coords[i+1][1]), width)
                                write_bboxes_to_DB(iteration_segments_bboxes,cursor, segment_id, segmentation_counter)
                                con.commit()
                                segmentation_counter += 1
                            else: 
                                print("[!!] SKIP: multiple areas for segment: ", segm_gid)

                        except IndexError:
                            break

                else:
                    segmentation_counter = 0 
                    width = get_traffic_area_width(segm_gid, cursor)
                    if width == ec.NO_WIDTH:
                        print("[!!] SKIP: no width for segment: ", segm_gid)
                        cursor.execute("""INSERT INTO segments_segmentation VALUES (%s, %s, %s, %s, %s, %s) """, (segment_id, ec.NO_WIDTH,  ec.NO_WIDTH, ec.NO_WIDTH, ec.NO_WIDTH, ec.NO_WIDTH, ))
                        con.commit()
                        continue

                    #insert into DB
                    cursor.execute("""INSERT INTO segments_segmentation VALUES (%s, %s, %s, %s, %s, %s) """, (segment_id, segmentation_counter,  sorted_coords[0][0], sorted_coords[0][1], sorted_coords[1][0], sorted_coords[1][1], ))
                    con.commit()
                    # add segmentation for iteration length
                    if width != 0:
                        iteration_segments_bboxes = create_iteration_segments(sorted_coords[0], sorted_coords[1], width)
                        write_bboxes_to_DB(iteration_segments_bboxes,cursor, segment_id, segmentation_counter)
                        con.commit()
                    else: 
                        print("[!!] SKIP: multiple areas for segment: ", segm_gid)


# add the geometries as PostGIS geometries
# in the loaded segments table intersect each segment with the ortsteile geometry and if there is an intersection, add the accoding ot_name to segments table
def add_ot_to_segments(db_config, db_user):
    print("Add OT to segments...")
    with open_connection(db_config, db_user) as con:
        cursor = con.cursor()

        #convert geometry from JSON to postgis column type for tables segemtns and ortsteile
        # make sure POSTGIS EXTENSION IS INSTALLED
        for table in ['ortsteile', 'segments']:
            cursor.execute(""" 
                    ALTER TABLE {} ADD COLUMN geometry_from_json geometry;
                    UPDATE {} SET geometry_from_json = ST_GeomFromGeoJSON(geometry);
                    ALTER TABLE {} DROP COLUMN geometry;""".format(table, table, table))

        # add ot_name to segments table checking with ortsteile geometry
        cursor.execute(""" 
                UPDATE segments
                SET ot_name = ot.ot_name
                FROM ortsteile ot
                WHERE ST_Intersects(segments.geometry_from_json, ot.geometry_from_json);""")
        
        con.commit()


if __name__ == "__main__":
    config_path = f'{RES_FOLDER_PATH}/{DB_CONFIG_FILE_NAME}'

    # add_ot_to_segments(config_path, DB_USER)
    # create_segm_gid_relation(config_path, DB_USER)
    create_segmentation(config_path, DB_USER)

    