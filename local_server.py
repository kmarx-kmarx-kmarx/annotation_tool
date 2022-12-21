from dash import Dash, html, ctx
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd
import os
from sqlite3 import connect
from itertools import islice
import random
import base64
from itertools import islice

imgs_path = "./all_outs"
imgs_type = "png"
ilastik_csv_path = "./spot_list_ilastik_U3D.csv"
database_path = "./annotations.db"
fix_number = True # set True if the view numbers are offset by 100
log_length = 100
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
    con = connect(database_path)
    c = con.cursor()
    c.execute('SELECT * FROM annotations') 
    row = list(next(islice(c, idx, None)))
    (im_name, im_path) = get_name(row[0], row[1], row[3], row[4])
    stat = row[-1]
    capt = im_name + ": " + str(list(codes.keys())[list(codes.values()).index(int(stat))])
    # load image
    encoded_image = base64.b64encode(open(im_path, 'rb').read())
    encoded_image = f"data:image/png;base64, {bytes.decode(encoded_image)}"
    # close cursor and connection
    c.close()
    con.close()
    return capt, encoded_image
# define function for finding next un-annotated
def find_next_type(idx, idxs, code):
    stat = codes["DUMMY"] # assign dummy value
    con = connect(database_path)
    c = con.cursor()
    c.execute('SELECT * FROM annotations')
    # store original idx
    idx_0 = idx
    # skip to our index
    next(islice(c, idxs[idx], None))
    while stat != code:
        # go to next index
        idx += 1
        idx = idx % len(idxs)
        # if we looped back around, break
        if idx == idx_0:
            return idx
        # otherwise, read the next row and read its associated code
        row = list(next(c))
        stat = row[-1]
    # close cursor and connection
    c.close()
    con.close()
    return idx
def update_code(idxs, idx, code):
    con = connect(database_path)
    c = con.cursor()
    # fetch row
    c.execute('SELECT * FROM annotations')
    row = list(next(islice(c, idxs[idx], None)))
    c.execute(f'UPDATE annotations SET annotation=\'{code}\' WHERE FOV_row={row[0]} AND FOV_col={row[1]} AND x={row[3]} AND y={row[4]}')
    con.commit()
    c.close()
    con.close()
# initialize annotation log
log = [" "] * log_length

# initialize dash app
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = Dash(__name__, external_stylesheets=external_stylesheets)

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
# done with this cursor
c.close()
con.close()

caption, encoded_image = data_at_index(indices[i])
new_log(f"Initialized first image: {caption}")
logstring = log_to_string()

# Build layout - image and buttons
app.layout = html.Div([
    html.Div(caption, id='image_status'),
    html.Img(src='data:image/png;base64,{}'.format(encoded_image), id='image'),
    html.Div([
    html.Button(id='b_button_state', n_clicks=0, children='back'), # back
    html.Button(id='p_button_state', n_clicks=0, children='positive'), # positive
    html.Button(id='n_button_state', n_clicks=0, children='negative'), # negative
    html.Button(id='u_button_state', n_clicks=0, children='unsure'), # unsure
    html.Button(id='f_button_state', n_clicks=0, children='forward'), # forward
    html.Button(id='s_button_state', n_clicks=0, children='skip')]),#skip
    html.Div(logstring, id='log')
])

def back_callback():
    # track which log message we want
    global i
    flag = False
    if len(seen_images) == 1:
        new_log("Already at first image, can't go back")
    else:
        seen_images.pop()
        flag = True
    # target image is the last image in the list
    i = seen_images[-1]
    caption, encoded_image = data_at_index(indices[i])
    if flag:
        new_log(f"Went back to previous image: {caption}")
    return log_to_string(), caption, encoded_image

def fwd_callback():
    global i
    i += 1
    i = i % len(indices)
    seen_images.append(i)
    caption, encoded_image = data_at_index(indices[i])
    
    new_log(f"Went forward to next image: {caption}")
    return log_to_string(), caption, encoded_image

def mark_callback(code):
    global i
    # Mark this image
    update_code(indices, i, code)
    # get image name
    caption_old, __ = data_at_index(indices[i])
    i += 1
    i = i % len(indices)
    seen_images.append(i)
    caption, encoded_image = data_at_index(indices[i])
    new_log(f"Marked {caption_old}, moved to next image: {caption}")
    return log_to_string(), caption, encoded_image

def skip_callback():
    global i
    i = find_next_type(i, indices, codes["INIT_CODE"])
    seen_images.append(i)
    caption, encoded_image = data_at_index(indices[i])
    new_log(f"Went forward to next un-annotated: {caption}")
    return log_to_string(), caption, encoded_image

def do_nothing_callback():
    global i
    caption, encoded_image = data_at_index(indices[i])
    return log_to_string(), caption, encoded_image

# Define button-handling callback - read from all the buttons and output to the image, log, and status
@app.callback(Output('log', 'children'),
              Output('image_status', 'children'),
              Output('image', 'src'),
              Input('b_button_state', 'n_clicks'),
              Input('p_button_state', 'n_clicks'),
              Input('n_button_state', 'n_clicks'),
              Input('u_button_state', 'n_clicks'),
              Input('f_button_state', 'n_clicks'),
              Input('s_button_state', 'n_clicks'))
def button_callback(b_btn, p_btn, n_btn, u_btn, f_btn, s_btn):
    button_id = ctx.triggered_id if not None else ' '

    if   button_id == "f_button_state":
        return fwd_callback()
    elif button_id == "u_button_state":
        return mark_callback(codes['UNSURE_CODE'])
    elif button_id == "n_button_state":
        return mark_callback(codes['NEG_CODE'])
    elif button_id == "p_button_state":
        return mark_callback(codes['POS_CODE'])
    elif button_id == "b_button_state":
        return back_callback()
    elif button_id == "s_button_state":
        return skip_callback()
    else:
        return do_nothing_callback()

if __name__ == '__main__':
    app.run_server(debug=True)