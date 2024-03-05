import pandas as pd
from flask import Flask, request, jsonify, render_template
import math
import mplfinance as mpf
import numpy as np
import matplotlib
import io
import base64
import matplotlib.pyplot as plt
import json as js
matplotlib.use('Agg')

#libraries that I use. Matplotlib uses Agg as the backend to write file. Can't render a window with it though.

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
#these schedulers are to control when to update the graph.


app=Flask(__name__)


executors = {
    'default': ThreadPoolExecutor(16),
    'processpool': ProcessPoolExecutor(4)
}

sched = BackgroundScheduler(timezone='Asia/Seoul', executors=executors)



class API_object:
    def __init__(self, dict_of_candle_data={}):
        '''
        Let me explain what each of these are
        df. I have no idea what it is honestly. Will delete this.
        send_image. I honestly don't quite remember what this was. But back when this code was in its sort of "alpha" version, this was the variable that controlled whether to update the charts or not. Will delete this.
        dict_of_candle_data. This is literally all the data stored for each item. Data is added to this through a variable known as "temporary_df", which I explain later if you keep reading.
        image_array_list. This is where all the images are kept. This is gonna be a bit tough to explain. Basically, the images are kept here. When someone makes a get request to aquire the images for a certain minecraft server, each image_data is returned in this. The image_data consists of two things: (base64_image), (title).
        list_of_trades. This is where all the new trades that have been coming in from the minecraft server is being kept. Keyword, NEW trades. An iterator loops through these and a temporary df is made that takes the open, high, low, close of each dataframe. The open is the first row's value in the dataframe. The high is the maximum the value go tin the dataframe. The low is teh lowest the value got in the dataframe. And the close is the value the dataframe ended at. Btw for some reason I loop through the dataframe itself, although I don't need to. I will fix this and restructure the code to make it more efficient.
        update_charts. This is what the scheduler controls. If this is turned on, the next time a request is made to add something to the graph, it will update the actual graph itself.
        return_dictionary. This is returned to a html file that uses jinja to process the dictionary and actually show the images. dictionary looks like: {'title_of_image': 'base64_data'}. That simple.
        '''
        self.df=pd.DataFrame()
        self.send_image=False
        self.dict_of_candle_data=dict_of_candle_data
        self.image_array_list=[]
        self.list_of_trades=[]
        self.update_charts=False
        self.return_dictionary={}



    def api_function(self, method_type, req_Json):
        '''
        this is a huge function that depending on the method, it will do one part or another. I'll eventually organize this to make it two different functions to be more organized.
        lets begin with the explanations
        '''

        
        if method_type=='POST':
            # req_Json=request.json

            '''
            the method_type == 'POST' checks whether or not a post request was sent to make sure it's doing the right function.

            The code underneath this until if len(self.list_of_trades)!=0: is about processing the json data sent by the server. (Post requests are always sent by server).
            Ngl ths code is pretty self explanatory, so I'll move on. HOWEVER, there is one thing I should explain.
            1. I split the item name into two parts because each item name is actually sent by its id. an example id is minecraft:dirt
            '''
            starting_price=req_Json['starting_price']
            selling_price=req_Json['selling_price']
            item_name=req_Json['item_name']
            item_name=(item_name.split(':'))[1] #this is due to a minecraft id being minecraft:{item}

            # if item_name=='name_tag': #this was here because before ids we used the names of the items, so theoretically someone could clog the charts with a bunch of random names of random items.
            #     return jsonify(f'item {item_name} will not be turned into chart')

            max_durability=req_Json['max_durability']
            lost_durability=req_Json['lost_durability']
            durability_stat=1
            if max_durability !=0:
                durability_stat=(max_durability-lost_durability)/max_durability
            enchantments=req_Json['enchantments']
            timeOfAuction=req_Json['timeOfAuction']
            timeOfSelling=req_Json['timeOfSelling']

            self.discord_server_id=req_Json['discord_server_id']
            self.channel_id=req_Json['channel_id']

            sell_price=selling_price*(math.pow(durability_stat, -1))


            '''
            this small thing with if len(self.list_of_trades)!=0

            This first checks to make sure the the length of list_of_trades isn't 0. If it is 0, it adds the first dataframe to list_of_trades. If it isn't zero, it continues to the next part.
            Next it iterates over each dataframe in list_of_trades, which is something that holds all the new auction house data that has come in before the graph is to be updated.
            If the item_name is inside one of the dataframes, it adds the value that the current newest auction house value got of the data to it respective dataframe.
            If the item_name isn't inside one of the dataframes, it does the exact same thing if self.list_ot_trades == 0. It creates a the first dataframe for that specific item in list_of_trades.
            '''

            if len(self.list_of_trades)!=0:
                for i, df in enumerate(self.list_of_trades):
                    if item_name in df.columns:
                        df.loc[df.index.max() + 1] = [sell_price]
                        break
                    elif i == len(self.list_of_trades) - 1:
                        new_data = pd.DataFrame({item_name: [sell_price]})
                        self.list_of_trades.append(new_data)
                        break
                    else:
                        continue
            else:
                new_data = pd.DataFrame({item_name: [sell_price]})
                self.list_of_trades.append(new_data)

            for df in self.list_of_trades:
                print(df)

        elif method_type=='GET':

            '''
            this is executed if someone sends a get request, meaning they go to view the website to see the charts.
            '''

            #basically if update charts is false, meaning the time period hasn't passed yet to add a new candle, it will just return the same data/images
            if self.update_charts==False:
                return self.return_dictionary
            

            if len(self.list_of_trades)==0: #this was causing an error because if it returned what it returned, it didn't return data and that screwed it up. Therefore I commented return jsonify("nothing to return") and put in return self.return_dictionary
                # return jsonify("nothing to return")
                return self.return_dictionary


            '''
            this code is executed if the two above if statements are not executed. If you want to see what the if statements do, read the comments next to them.
            Basically, this code first goes through each dataframe in list_of_trades. Each dataframe contains all the data sent by the server for each item. The data is a list of prices the items were sold at.
            It then iterations over the columns of the dataframe.
            Now, although I did iterate (enumerate) over this, I didn't quite need to because technically, there should only be one column for each dataframe, so i isn't necessary. HOWEVER, column is, which you'll find out later. Actually now that I think about it, there is another way I could do without necessarily iterating of the i and columns of the dataframe. But I'll do that later. What I'm thinking is to just grab the columsn by doing df.columns[0]. To access the items in the dict_of_candle_data dictionary.
            temporary_df is made from the open, high, low, close. These are explained previously.
            After creating these, it creates a arbitrary index for temporary_df
            It then tries checking whether there is a column for that specific item in the dict_of_candle_data by doing .get. .get returns a None if it isn't found. If it is found, it returns the dataframe.
            Next is self explanatory. If you don't know what concat is, it basically concatenates (sticks) the two dataframes together.
            Now, the next block of code is yes, I know, horrifying. It is terrible, evil, I hate it myself as well. but, it works, so I'm not touching it. Basically what it does is reset the index to accomodate for the new values. That's it. If you're wondering why we need a arbitrary index in the first place, it's because the mplfinance library requires it to make the base64_image.
            After that, the code iterates over dict_of_candle_data and makes the charts for each of the items's ohlc data. It turns the charts into base64 images, and puts each image in image_array_list.
            It then puts the images into a return_dictionary, which will later be fed into html/jinja where each of the images will be displayed with their titles above their respective images.
            Btw remember, the rest of these steps is only done if update_charts = True and there is actually new trades in list_of_trades.
            '''
            
            for df in self.list_of_trades:
                for i, column in enumerate(df):
                    
                    open=df.iloc[0, i]
                    high=df.iloc[:, i].max()
                    close=df.iloc[-1, i]
                    low=df.iloc[:, i].min()
                    volume=len(df.iloc[:, i])
                    temporary_df=pd.DataFrame()
                    temporary_df = pd.DataFrame({
                        'Open': [open],
                        'High': [high],
                        'Low': [low],
                        'Close': [close],
                        'Volume': [volume]
                        })
                    temporary_df.index = pd.date_range('1/1/2021',periods=(len(temporary_df)))
                    found_dataframe = self.dict_of_candle_data.get(column)
                    if found_dataframe is not None:
                        self.dict_of_candle_data[column]=pd.concat([self.dict_of_candle_data[column], temporary_df], axis=0)
                    else:
                        self.dict_of_candle_data[column]=temporary_df

                    if 'index' in self.dict_of_candle_data[column].columns:
                        self.dict_of_candle_data[column]=self.dict_of_candle_data[column].drop('index', axis=1)
                        self.dict_of_candle_data[column]=self.dict_of_candle_data[column].reset_index()
                        self.dict_of_candle_data[column]=self.dict_of_candle_data[column].drop('index', axis=1)
                        self.dict_of_candle_data[column].index = pd.date_range('1/1/2021',periods=(len(self.dict_of_candle_data[column])))
                    else:
                        self.dict_of_candle_data[column]=self.dict_of_candle_data[column].reset_index()
                        self.dict_of_candle_data[column].index = pd.date_range('1/1/2021',periods=(len(self.dict_of_candle_data[column])))


            for i, column in enumerate(self.dict_of_candle_data):
                fig,ax=mpf.plot(self.dict_of_candle_data[column][['Open', 'High', 'Low', 'Close', 'Volume']], type='candle', style='yahoo', returnfig=True, title=str(column), volume=True)

                buf = io.BytesIO()
                fig.savefig(buf, format='png')
                buf.seek(0)
                image_base64 = base64.b64encode(buf.read()).decode('utf-8')
                buf.close()
                plt.close(fig)
                self.image_array_list.append((image_base64, column))

            df=pd.DataFrame()

            self.list_of_trades=[]


            return_dictionary={}
            image_return_dictionary={}

            for i in range(len(self.image_array_list)):
                title_of_image=self.image_array_list[i][1]
                image_data=self.image_array_list[i][0]

                image_return_dictionary[title_of_image]=image_data

            return_dictionary['discord_server_id']=self.discord_server_id

            return_dictionary['images']=image_return_dictionary

            self.return_dictionary=return_dictionary


            # json_to_return=json.dumps(return_dictionary) #I don't know why I ever did this

            self.image_array_list=[]
            self.update_charts=False
            return self.return_dictionary


    


'''
these are the final parts
the api_object_dictionary is a dictionary that houses all the api objects. Basically all the data for each server.
the tell_api_objects_they_need_to_update_the_charts is literally does what it is in its name.
This function is scheduled every 900 seconds, which is equal to 15 minutes.

Alright, here comes the actual api setup itself.
So, the route to the app is setup, where the user can enter any minecraft_server_name and it will return something based on whether the api object exists for it or not.
This is done with the director function, which works like this
It takes in the minecraft_server_name the user or server entered in the url
It then checks if it a POST or GET request. A POST request would mean a minecraft server is sending it data, whilst a GET request would mean a user is trying to go to the website to see the graphs generated.
If it is a POST request (minecraft server sending data), it takes the Json sent, and checks whether or not a api_object for that specific server exists or not.
If it does exist, it will do the api_function with method_type POST for that api_object.
If it doesn't exist, it will make a new api_object and do the api_function with method_type POST for that new object.
If if it a GET request (user going to url), it will
1. Make a get_data dictionary to be a temporary distraction (placeholder) for req_Json parameter
2. Check if the minecraft_server is in the api_object_dictionary
If it is in the dictionary, it will get the json (dictionary) returned by the api_function with method_type GET
then it will checks if the dictionary returned it a str or not, which happened for some reason but I don't think happens anymore (will check this and probably remove it)
Afterwards it will go through one more check to see if there are actually any images in the dictionary, which deals with a bug that made the web that is hosted have a stroke
If any of thse steps don't happen to workout, the code will default to sending a no_data.html file which is the placeholder for when there isn't any data/charts to put on for the user to see, or there is a error.
'''

api_object_dictionary={}

def tell_api_objects_they_need_to_update_the_charts():
    for col in api_object_dictionary:
        api_object_dictionary[col].update_charts=True

#adds job to scheduler
sched.add_job(tell_api_objects_they_need_to_update_the_charts, 'interval', seconds=900)


#set up flask api that will see if server id exists in dictionary or not and based on that create new api_object
@app.route('/view/<string:minecraft_server_name>', methods=['POST', 'GET'])
def director(minecraft_server_name):
    if request.method=='POST':
        req_Json=request.json
        # if req_Json['discord_server_id'] not in api_object_dictionary.keys():
        if minecraft_server_name not in api_object_dictionary.keys():
            api_object_dictionary[minecraft_server_name]=API_object()
            api_object_dictionary[minecraft_server_name].api_function(method_type='POST', req_Json=req_Json)
            return jsonify('done')
        else:
            api_object_dictionary[minecraft_server_name].api_function(method_type='POST', req_Json=req_Json)
            return jsonify('done')
        

    elif request.method=='GET':
        #will have to add a thing where it will show the old images until a period of time (such as 15 minutes) has passed


        # req_Json=request.json
        get_data={}
        #the reason I cannot use request.json and have to use get_data because the webpage will not load.
        if minecraft_server_name in api_object_dictionary.keys():
            #each object in api_object_dictionary is a api_object.
            json=api_object_dictionary[minecraft_server_name].api_function(method_type='GET', req_Json=get_data)
            # print(json)

            # return json. This is for actual api I will make later.
            if isinstance(json, str):
                json=js.loads(json) #for some reason the json it originally considered a string by jinja(the html code). I do not know why.
            else:
                pass
            
            if 'images' in json: #this if else statement deals with an error where the code takes too long to process the images to load them back. So basically the code knows there is an api object for a server and it has the data, but the return dictionary only updates every 15 seconds, so render template is still an empty dictionary. This is my hypothesis on why this happens.
                return render_template("index.html", data=json['images'])
            else:
                return render_template("no_data.html")

        else:
            return render_template("no_data.html")
        
    else:
        return render_template("no_data.html")
        # return jsonify({'error': 'Invalid request'})

    # print(api_object_dictionary)


if __name__=='__main__':
    sched.start()
    app.run(port=8080)
