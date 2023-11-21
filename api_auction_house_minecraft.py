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

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor


app=Flask(__name__)


executors = {
    'default': ThreadPoolExecutor(16),
    'processpool': ProcessPoolExecutor(4)
}

sched = BackgroundScheduler(timezone='Asia/Seoul', executors=executors)



class API_object:
    def __init__(self, dict_of_candle_data={}):
        # self.discord_server_id=server_id
        self.df=pd.DataFrame()
        self.send_image=False
        self.dict_of_candle_data=dict_of_candle_data
        self.image_array_list=[]
        self.list_of_trades=[]
        self.update_charts=False
        self.return_dictionary={}
        # self.server_id=server_id
        # app.add_url_rule(f'/{str(self.server_id)}', server_id, self.api_function, methods=['POST', 'GET'])


    def api_function(self, method_type, req_Json):
        if method_type=='POST':
            # req_Json=request.json
            starting_price=req_Json['starting_price']
            selling_price=req_Json['selling_price']
            item_name=req_Json['item_name']
            item_name=(item_name.split(':'))[1] #this is due to a minecraft id being minecraft:{item}

            if item_name=='name_tag':
                return jsonify(f'item {item_name} will not be turned into chart')

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

            #basically if update charts is false, meaning the time period hasn't passed yet to add a new candle, it will just return the same data/images
            if self.update_charts==False:
                return self.return_dictionary
            

            if len(self.list_of_trades)==0: #this was causing an error because if it returned what it returned, it didn't return data and that screwed it up. Therefore I commented return jsonify("nothing to return") and put in return self.return_dictionary
                # return jsonify("nothing to return")
                return self.return_dictionary
            
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

                # fig.savefig('/Users/rafayelsargsyan/Documents/PythonPrograms/auction_house/ez.png')

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


    




api_object_dictionary={}

def tell_api_objects_they_need_to_update_the_charts():
    for col in api_object_dictionary:
        api_object_dictionary[col].update_charts=True

#adds job to scheduler
sched.add_job(tell_api_objects_they_need_to_update_the_charts, 'interval', seconds=15)


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
        return jsonify({'error': 'Invalid request'})

    # print(api_object_dictionary)


if __name__=='__main__':
    sched.start()
    app.run(port=8080)