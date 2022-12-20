from dash import Dash, html, dcc
from dash.dependencies import Input, Output, State
import plotly.express as px
import pandas as pd
import os
from sqlite3 import connect
from itertools import islice
import random
import base64
from itertools import islice

imgs_path = "./outputs"
imgs_type = "png"
ilastik_csv_path = "./spot_list_ilastik_U3D.csv"
database_path = "./annotations.db"
fix_number = True # set True if the view numbers are offset by 100
log_length = 10
random.seed(1)

codes = {"INIT_CODE": -1, "POS_CODE": 1, "NEG_CODE":0, "UNSURE_CODE":9, "DUMMY": 999}

# define name generator
def get_name(FOV_row, FOV_col, x, y):
    img_name = str(int(FOV_row))  + "_" + str(int(FOV_col)) + "_" + str(int(x)) + "_" + str(int(y))
    target_path = os.path.join(imgs_path, img_name + "." + imgs_type)
    return (img_name, target_path)
# define log-handling functions
def new_log(new_string):
    log.pop(0)
    log.append(new_string)
def log_to_string():
    newlog = list(reversed(log))
    for b in range(len(log)):
        newlog.insert(b*2, html.Br())
    return newlog
# define function for getting data
def data_at_index(idx):
    c.execute('SELECT * FROM annotations') 
    row = list(next(islice(c, idx, None)))
    (im_name, im_path) = get_name(row[1], row[2], row[4], row[5])
    stat = row[-1]
    capt = im_name + ": " + str(list(codes.keys())[list(codes.values()).index(int(stat))])
    # load image
    encoded_image = base64.b64encode(open(im_path, 'rb').read())

    return capt, encoded_image
# define function for finding next un-annotated
def find_next_type(idx, idxs, code):
    stat = code["DUMMY"] # assign dummy value
    c.execute('SELECT * FROM annotations')
    # store original idx
    idx_0 = idx
    while stat != code:
        # go to next index
        idx += 1
        idx = idx % len(idxs)
        # if we looped back around, break
        if idx = idx_0:
            return idx
        # otherwise, read the next row and read its associated code
        row = list(next(islice(c, idxs[idx], None)))
        stat = row[-1]
    return idx

# initialize annotation log
log = [" "] * log_length

# initialize dash app
app = Dash(__name__)

# check if database exists - if it does, load it
if os.path.exists(database_path):
    con = connect(database_path)
    c = con.cursor()
# otherwise, load the ilastik dataframe into the database
else:
    # load ilastik dataframe
    spotlist = pd.read_csv(ilastik_csv_path)
    if fix_number:
        spotlist["FOV_row"] = spotlist["FOV_row"]  - 100
        spotlist["FOV_col"] = spotlist["FOV_col"]  - 100
    spotlist["annotation"] = codes["INIT_CODE"]

    # init empty database
    con = connect(database_path)
    c = con.cursor()
    # get headers
    headers = list(spotlist.columns)
    sql_headers = ", ".join(headers)
    # create empty table
    print(sql_headers)
    c.execute(f"CREATE TABLE IF NOT EXISTS annotations ({sql_headers})")
    con.commit()
    # write to table
    spotlist.to_sql("annotations", con, if_exists='replace', index = False)
    con.commit()

# Load initial (random) image
# get number of rows
c.execute('SELECT Count(*) FROM annotations')
n_rows = list(next(c))[0]
indices = list(range(int(n_rows)))
random.shuffle(indices)
i = 0
seen_images = []
seen_images.append(i)

caption, encoded_image = data_at_index(indices[i])
new_log(f"Initialized first image: {caption}")
logstring = log_to_string()

# Build layout - image and buttons
app.layout = html.Div([
    html.Div(caption, id='image_status'),
    html.Img(src='data:image/png;base64,{}'.format(encoded_image), id='image'),
    html.Button(id='b_button_state', n_clicks=0, children='b_button'), # back
    html.Button(id='p_button_state', n_clicks=0, children='p_button'), # positive
    html.Button(id='n_button_state', n_clicks=0, children='n_button'), # negative
    html.Button(id='u_button_state', n_clicks=0, children='u_button'), # unsure
    html.Button(id='f_button_state', n_clicks=0, children='f_button'), # forward
    html.Div(logstring, id='log')
])


# Define callbacks
# Go back without changing annotation
@app.callback(Output('log', 'children'),
              Output('image', 'src'),
              Output('image_status', 'value'),
              Input('b_button_state', 'n_clicks'))
def back_callback(n):
    flag = False
    if n > 0:
        if len(seen_images) == 1:
            new_log("Already at first image, can't go back")
        else:
            seen_images.pop()
            flag = True

    i = seen_images[-1]
    caption, encoded_image = data_at_index(indices[i])
    if flag:
        new_log(f"Went back to previous image: {caption}")

    return log_to_string(), encoded_image, caption

# Go to the next unlabeled without changing annotations
@app.callback(Output('log', 'children'),
              Output('image', 'src'),
              Output('image_status', 'value'),
              Input('f_button_state', 'n_clicks'))
def forward_callback(n):
    flag = False
    if n > 0:
        if i >= len(indices):
            new_log("Already at last image, can't go forward")
        else:
            i += 1
            flag = True
    seen_images.append(i)

    caption, encoded_image = data_at_index(indices[i])
    if flag:
        new_log(f"Went forward to next image: {caption}")

    return log_to_string(), encoded_image, caption



if __name__ == '__main__':
    app.run_server(debug=True)