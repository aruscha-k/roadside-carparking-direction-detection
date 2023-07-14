
from DB_helpers import open_connection
from PATH_CONFIGS import CYCLO_IMG_FOLDER_PATH, AIR_CROPPED_ROTATED_FOLDER_PATH, RES_FOLDER_PATH, DB_CONFIG_FILE_NAME, DB_USER, LOG_FILES
from ML_IMGs_methods import run_detection
import ERROR_CODES as ec
from datetime import datetime
import os
import psycopg2

# import matplotlib.pyplot as plt
# from shapely.geometry import Polygon


def log(img_type, logstart, logtime, message: str):
    log_file_name = str(logstart) + "_" + str(img_type) + ".txt"
    log_file = os.path.join(LOG_FILES, log_file_name)
    if os.path.exists(log_file):
        with open(log_file, 'a') as lfile:
            lfile.write(logtime.strftime('%Y-%m-%d %H:%M:%S')  + ' ' + message + '\n')
    else:
        with open(log_file, 'w') as lfile:
            lfile.write(logtime.strftime('%Y-%m-%d %H:%M:%S')  + ' ' + message +  '\n')

# get images and use ML detection on them to determine parking, possibility to submit a specific suburb
# iterate all segments in suburb and, for each segment fetch all iteration steps (bounding boxes). for each box, check which record IDs lie within and run ML on them
# fetch all record IDs. for each record ID fetch the path where it is saved
def run(db_config, db_user, suburb_list, img_type, result_table_name):
    log_start = datetime.now()
    with open_connection(db_config, db_user) as con:
        
        cursor = con.cursor()

        if suburb_list == []:
             # get ortsteile and their number codes
            cursor.execute("""SELECT ot_name, ot_nr FROM ortsteile""")
            suburb_list = cursor.fetchall()
        
        for ot_name, ot_nr in suburb_list:
            print("[i] Getting Segments in ", ot_name)

            # get all segments
            cursor.execute("""SELECT id FROM segments WHERE ot_name = %s""", (ot_name, ))
            segment_id_list = [item[0] for item in cursor.fetchall()]

            for i, segment_id in enumerate(segment_id_list):
                print(f"------{i+1} of {len(segment_id_list)+1}, segment_ID: {segment_id}--------")

                if img_type == "cyclo":
                    cursor.execute("""SELECT recording_id, segmentation_number, recording_lat, recording_lon FROM segments_cyclomedia WHERE segment_id = %s ORDER BY segmentation_number ASC""", (segment_id, ))
                elif img_type == "air":
                    cursor.execute("""SELECT segmentation_number, start_lat, start_lon, end_lat, end_lon FROM segments_segmentation WHERE segment_id = %s ORDER BY segmentation_number ASC""", (segment_id, ))

                result_rows = cursor.fetchall()
                if result_rows == []:
                    print("no result for segment: ", segment_id)
                    log(img_type=img_type, logstart=log_start, logtime=datetime.now(), message=f"{segment_id}: No Result for segment")
                    continue

                else:
                    print(f"Found {len(result_rows)} items for segment")
                    img_path_and_position_list = []
                    for idx, row in enumerate(result_rows):
                        # check for existing in DB?: TODO
                        # cursor.execute("""SELECT segment_id, segmentation_number, iteration_number, parking FROM {} WHERE segment_id = %s AND segmentation_number = %s AND iteration_number = %s""".format(result_table_name), (segment_id, segmentation_number, iteration_number,))
                        # result = cursor.fetchone()
                        # if len(result) == 2:
                        #     print("EXISTS - skip")
                        #     continue

                        if img_type == "cyclo":
                            
                            recording_id = result_rows[idx][0]
                            segmentation_number = result_rows[idx][1]
                            recording_lat, recording_lon = result_rows[idx][2], result_rows[idx][3]
                            img_position_information = (recording_lat, recording_lon)

                            if segmentation_number < 10:
                                segmentation_no_string = "0" + str(segmentation_number)
                            else:
                                segmentation_no_string = str(segmentation_number)
                            img_file_path = CYCLO_IMG_FOLDER_PATH + str(segment_id)+ "_" + segmentation_no_string +  "_" + str(recording_id) + ".jpg"
                            

                        elif img_type == "air":
                            segmentation_number = result_rows[idx][0]
                            start_lat, start_lon = result_rows[idx][1], result_rows[idx][2]
                            end_lat, end_lon = result_rows[idx][3], result_rows[idx][4]
                            img_position_information = ((start_lat, start_lon), (end_lat, end_lon))
                            img_file_path = AIR_CROPPED_ROTATED_FOLDER_PATH + str(ot_name) + "_" +  str(segment_id)+ "_" + str(segmentation_number) + ".tif"
                            
                        if os.path.exists(img_file_path):
                            img_path_and_position_list.append((img_file_path, img_position_information))
                        else:
                            print("invalid path", img_file_path)
                            log(img_type=img_type, logstart=log_start, logtime=datetime.now(), message= f"no file found for segment_id {segment_id}")
                            break

                        if img_path_and_position_list == []:
                            print("No images for iteration")
                            continue
                        
                        # get iteration step information
                    cursor.execute(""" SELECT iteration_number, left_coordinates, right_coordinates FROM segments_segmentation_iteration WHERE segment_id = %s AND segmentation_number = %s ORDER BY iteration_number ASC""", (segment_id, segmentation_number, ))
                    iteration_result_rows = cursor.fetchall()
                    if iteration_result_rows == []:
                        print("no iteration information for segment: ", segment_id)
                        log(img_type=img_type, logstart=log_start, logtime=datetime.now(), message=f"{segment_id}: No iteration information for segment")
                        continue

                    iter_information = {}
                    for iteration_row in iteration_result_rows:
                    
                        iteration_number = iteration_row[0]
                        left_coords, right_coords = iteration_row[1], iteration_row[2]
                        iteration_poly = [left_coords[0], left_coords[1], right_coords[1], right_coords[0]]
                        iter_information[iteration_number] = iteration_poly

                    parking_dict = run_detection(img_path_and_position_list, img_type, iter_information)
                    break

                    #  write to DB # parking_dict = {iteration_number: {'left': [()], 'right': []}}
                    # for key, value in parking_dict.items():

                    #     for (parking, percentage) in parking_dict[key]:
                    #         try:
                    #             if img_type == "cyclo":
                    #                 cursor.execute("""INSERT INTO {} VALUES (%s, %s, %s, %s, %s, %s)""".format(result_table_name), (segment_id, segmentation_number, iteration_number, key, parking, percentage,))
                    #             elif img_type == "air":
                    #                 cursor.execute("""INSERT INTO {} VALUES (%s, %s, %s, %s, %s)""".format(result_table_name), (segment_id, iteration_number, key, parking, percentage,))

                    #         except psycopg2.errors.UniqueViolation as e:
                    #             #print(e)
                    #             con.rollback()
                    #             continue
                    #         con.commit()



if __name__ == "__main__":

    db_config_path = os.path.join(RES_FOLDER_PATH, DB_CONFIG_FILE_NAME)
    run(db_config_path, DB_USER, [("Lindenau", 70)], img_type="cyclo", result_table_name="parking_cyclomedia")
    #run(db_config_path, DB_USER, [("Lindenau", 70)], img_type="air", result_table_name="parking_air")


#https://atlas.cyclomedia.com/PanoramaRendering/Render/WE4IK5SE/?apiKey=2_4lO_8ZuXEBuXY5m7oVWzE1KX41mvcd-PQZ2vElan85eLY9CPsdCLstCvYRWrQ5&srsName=epsg:55567837&direction=0&hfov=80
#test_rec_IDs = ['WE4IK5OM', 'WE4IK5SO', 'WE4IK5SN', 'WE4IK5SM', 'WE4IK5SL', 'WE4IK5SK', 'WE4IK5SJ', 'WE4IK5SI', 'WE4IK5SH', 'WE4IK5SG', 'WE4IK5SF', 'WE4IK5SE', 'WE4IK5SD', 'WE4IK5SC', 'WE4IK5SB', 'WE4IK5SA', 'WE4IK5S9', 'WE4IK5S8', 'WE4IK5S7', 'WE4IK5S6', 'WE4IK5S5', 'WE4MDYHX', 'WE4IK5N8']