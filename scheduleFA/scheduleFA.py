# In case of certificate error on MAC, Go to Applications Folder, Python and double click 'Install Certificates.command'
from urllib.request import Request, urlopen
from pyquery import PyQuery
import datetime
import json
import requests
import sys
from time import strftime, localtime
from collections import OrderedDict

def import_initial_data(input_list):
  print("Enter the initial csv data in following format, one line for each vesting:")
  print("Acquire date in ddmmyyyy <space> No of shares <space> Acquire cost per share in INR <space> Sell date in ddmmyyyy(if applicable) <space> Total Sale proceeds in INR(in integer)")
  print("Eg1: 30062020 8 35884.88")
  print("Eg2: 30062020 8 35884.88 30082020 4000")
  print("When done just enter a blank line")

  while True:
    input_line = input()
    if len(input_line) == 0:
      break
    input_list.append(input_line)

  calendar_year = input("Enter calendar year in yyyy for eg 2023: ")
  return calendar_year

def validate_input(input_list, calendar_year):
  for input_line in input_list:
    if int(input_line[4:8]) > int(calendar_year):
      sys.exit("Acquire date is more than calendar year for <" + input_line + ">. Please fix.") 

    if len(input_line.split(" ")) > 3:
      sell_date = input_line.split(" ")[3]
      if int(sell_date[4:8]) != int(calendar_year):
        sys.exit("Sell year is not calendar year for <" + input_line + ">. Please fix.") 

      formatted_sell_date = datetime.datetime.strptime(sell_date, '%d%m%Y').strftime("%Y%m%d")
      formatted_acquire_date = datetime.datetime.strptime(input_line.split(" ")[0], '%d%m%Y').strftime("%Y%m%d")
      if formatted_sell_date < formatted_acquire_date:
        sys.exit("Sell date is earlier than acquire date for <" + input_line + ">. Please fix.") 


def export_data(output_list_unsorted):
  output_list = sorted(output_list_unsorted, key=lambda x: datetime.datetime.strptime(x.split(" ")[0], '%d%m%Y').strftime("%Y%m%d"))   
 
  print("AcquireDate <space> NoOfShares <space> TotalCost <space> TotalPeakValue <space> TotalCloseValue <space> HoldingCost <space> TotalSaleProceeds")
  for output_line in output_list:
    print(output_line)

def fetch_stock_price(calendar_year):
  start_date = datetime.datetime(calendar_year-1,12,15,0,0).strftime("%Y-%m-%d")
  end_date = datetime.datetime(calendar_year+1,1,15,0,0).strftime("%Y-%m-%d")
  stock_prices_url = 'https://api.twelvedata.com/time_series?apikey=f59ddcc6c818426fa713264d877e16ef&interval=1day&symbol=ADBE&start_date='
  stock_prices_url = stock_prices_url + start_date + ' 21:16:00&end_date=' + end_date + ' 21:16:00'
  print("Fetching stock prices from " + stock_prices_url)
  response = requests.get(stock_prices_url)
  response_json = json.loads(response.text)
  if response_json["status"] != "ok":
    sys.exit("Error fetching stock prices from  " + stock_prices_url)
  stock_prices_dict = OrderedDict()
  for line in response_json["values"]:
    date = datetime.datetime.strptime(line["datetime"], '%Y-%m-%d').timestamp()
    stock_prices_dict[date] = line["close"]

  return stock_prices_dict 
   

def find_closing_date(stock_prices_dict):
  # return last stock price in 12th month(December)
  for date in stock_prices_dict:
    month = strftime('%m', localtime(date))
    if month == '12':
      return date


def find_peak_date(stock_prices_dict, calendar_year, start_date_in_ddmmyyyy, end_date_in_ddmmyyyy):
  start_date = datetime.datetime.strptime(start_date_in_ddmmyyyy, '%d%m%Y').timestamp()
  end_date = 0
  if len(end_date_in_ddmmyyyy) > 1:
    end_date = datetime.datetime.strptime(end_date_in_ddmmyyyy, '%d%m%Y').timestamp()
  peak_value = -1
  peak_date = -1
  for date,price in stock_prices_dict.items():
    if peak_date == -1 and end_date != 0 and end_date <= date:
      continue
    if peak_date == -1 and strftime('%Y', localtime(date)) == calendar_year:
      peak_value = price
      peak_date = date
      if date <= start_date:
        break
    elif peak_date != -1 and start_date <= date:
      if peak_value < price:
        peak_value = stock_prices_dict[date]
        peak_date = date
      if date == start_date:
        break
    elif peak_date != -1 and start_date > date:
      if peak_value < price:
        peak_value = stock_prices_dict[date]
        peak_date = date
      break
    if peak_date != -1 and strftime('%Y', localtime(date)) != calendar_year:
      break
  return peak_date


def fetch_sbi_rates(calendar_year):
  sbi_rates_url = "https://raw.githubusercontent.com/sahilgupta/sbi-fx-ratekeeper/main/csv_files/SBI_REFERENCE_RATES_USD.csv"
  print("Fetching sbi rates from " + sbi_rates_url)
  req = Request(sbi_rates_url, headers={'User-Agent': 'Mozilla/5.0'})    
  html = urlopen(req).read()
  sbi_rates_list = []
  for line in html.decode().split("\n"):
    sbi_rate = line.split(",")
    if len(sbi_rate[0]) >= 10 and sbi_rate[0][:4] == calendar_year and sbi_rate[2] != "0.00" and sbi_rate[2] != "0":
      sbi_rates_list.append(str(datetime.datetime.strptime(sbi_rate[0][:10], '%Y-%m-%d').timestamp()) + "," + sbi_rate[2])
  return sbi_rates_list
  

def get_sbi_rate_index_for_date(date, sbi_rates, start_index, end_index):
  if start_index > end_index:
    return -1
  mid_index = int((start_index + end_index) / 2)
  if date == float((sbi_rates[mid_index].split(','))[0]):
    return mid_index
  if date > float((sbi_rates[mid_index].split(','))[0]):
    if mid_index == len(sbi_rates) - 1 or date < float((sbi_rates[mid_index + 1].split(','))[0]):
      return mid_index
  if date < float((sbi_rates[mid_index].split(','))[0]):
    index = get_sbi_rate_index_for_date(date, sbi_rates, start_index, mid_index - 1)
    if index != -1:
      return index
  return get_sbi_rate_index_for_date(date, sbi_rates, mid_index + 1, end_index)
  
    
def get_sbi_rate_for_date(date, sbi_rates):
  if date < float((sbi_rates[0].split(','))[0]):
    return (sbi_rates[0].split(','))[1]
  return (sbi_rates[get_sbi_rate_index_for_date(date, sbi_rates, 0, len(sbi_rates) - 1)].split(','))[1]


        
input_list = []
calendar_year = import_initial_data(input_list)
validate_input(input_list, calendar_year)

stock_prices_dict = fetch_stock_price(int(calendar_year))
sbi_rates = fetch_sbi_rates(calendar_year)

output_list = []
for input_line in input_list:
  input_values = input_line.split(' ')
  sell_date = "0"
  if len(input_values) > 4:
    sell_date = input_values[3]
  peak_date_raw = find_peak_date(stock_prices_dict, calendar_year, input_line[0:8], sell_date)
  closing_date_raw = find_closing_date(stock_prices_dict)

  output_line = input_values[0] + "   " + input_values[1] + "   "
  output_line = output_line + str(round(float(input_values[1]) * float(input_values[2]))) + "   "
  peak_value = round(float(stock_prices_dict[peak_date_raw]) * float(input_values[1]) * float(get_sbi_rate_for_date(peak_date_raw, sbi_rates)))
  if len(input_values) > 4 and peak_value < int(input_values[4]):
    peak_value = int(input_values[4])
  output_line = output_line + str(peak_value)
  #output_line = output_line + "(" + str(strftime('%Y/%m/%d', localtime(peak_date_raw))) + ")"
  if len(input_values) == 3:
    output_line = output_line + "   " + str(round(float(stock_prices_dict[closing_date_raw]) * float(input_values[1]) * float(get_sbi_rate_for_date(closing_date_raw, sbi_rates))))
    #output_line = output_line + "(" + str(strftime('%Y/%m/%d', localtime(closing_date_raw))) + ")"
  if len(input_values) > 4:
    output_line = output_line + "   0   0   " + str(round(float(input_values[4])))
  output_list.append(output_line)

export_data(output_list)

