#!/usr/bin/env python
# coding: utf-8

# ### B120 CE W-2

# In[ ]:


code_name = 'B120 CE W-2'
import ctypes
ctypes.windll.kernel32.SetConsoleTitleW(code_name)
print(code_name)

index = 'BANKNIFTY'
scheme_no = 2


# In[ ]:


import sys
import os
sys.path.append(os.path.abspath('..') + '\\inhouse_functions')
import pandas as pd
import datetime
from time import sleep
from Candle_Data import candle_data
from strike_selection import *
from telegram import telegram
from google_sheet import google_sheet as gsheet
from parameter import Parameter
from holiday import *

if index == 'BANKNIFTY':
    caps_strategy = 'BN B120 CE W ' + str(scheme_no)
    BT_sheet, ts_ce_index, ts_pe_index = gsheet().get_sheet_and_index(gsheet.sheet_ids.weekly_bt_bn,caps_strategy)
    slipage = 0.0125
    
elif index == 'NIFTY':
    caps_strategy = 'NF B120 CE W ' + str(scheme_no)
    BT_sheet, ts_ce_index, ts_pe_index = gsheet().get_sheet_and_index(gsheet.sheet_ids.weekly_bt_nf,caps_strategy)
    slipage = 0.01

param = Parameter(index, caps_strategy)
entry_time = param.entry_time
sl = param.get('sl')
trading_day = param.get('trading_day')
hedge_sd = 3

trading_day = set_trading_day(trading_day)

week_list = {'Friday':0, 'Saturday':1, 'Sunday':2, 'Monday':3, 'Tuesday':4, 'Wednesday':5, 'Thursday':6}
now = datetime.datetime.now().date()
parameter_day = now + datetime.timedelta(days = (week_list[trading_day] - week_list[datetime.datetime.today().strftime('%A')]))

entry_time = datetime.datetime.combine(parameter_day , entry_time) - datetime.timedelta(seconds=1)
entry_time = increment_if_holiday(entry_time)
check_time = entry_time

exit_time = datetime.time(15, 30)

check_ce_sl, modify_prices = False, False
sell_flag = 0

live_ce_pnl, booked_ce_pnl = 0,0
previous_day_pnl = 0

sleep_timedelta = ((entry_time - datetime.datetime.now()) - datetime.timedelta(seconds=60))
if sleep_timedelta.days == 0:
    sleep(sleep_timedelta.seconds)

try:
    while True:

        if (datetime.datetime.now() - check_time) > datetime.timedelta(minutes=2):
            sleep_time = 0
        else:
            sleep_time = 5
            sleep(2)

        if datetime.datetime.now() > check_time and sell_flag == 0:
            sleep(sleep_time)
            # getting strangle strike
            ce_scrip, ce_scrip_token, ce_price, t_scrip, t_scrip_token, t_price, future_scrip, future_token, future_price = select_straddle_strikes(index, check_time)

            ce_sl_price = int(round((ce_price * (1+(sl/100))) * 100, -1) + 5)/100

            ce_hedge_limit = int(ce_scrip[:-2]) + ((ce_price + t_price) * hedge_sd)
            ce_hedge = str(int(ce_hedge_limit - (ce_hedge_limit % 100) + 100)) + 'CE'

            print(ce_scrip, ce_price, ce_sl_price)

            # slipage
            ce_slipage_price = ce_price - (ce_price * slipage)

            # update strike on google sheet
            gsheet.Update_Batch(BT_sheet, f"A{ts_ce_index}:C{ts_ce_index}", [[ce_scrip, ce_price, ce_sl_price]])
            gsheet.Update_cell(BT_sheet, ts_ce_index, 4, ce_hedge)

            sell_flag, check_ce_sl, modify_prices = 1, True, True
            check_time = check_time + datetime.timedelta(minutes=1)

        if check_ce_sl:
            if datetime.datetime.now() > check_time:
                sleep(sleep_time)

                ce_o, ce_h, ce_l, ce_c = candle_data(ce_scrip_token, check_time)                
                print(check_time ,f'Call High : {ce_h}')

                ce_pnl = ce_slipage_price - ce_c
                live_ce_pnl = booked_ce_pnl + ce_pnl

                if datetime.datetime.today().date() == check_time.date():
                    gsheet.Update_PL_cell(BT_sheet, update='cell', row_no=ts_ce_index, column_no=11, value=live_ce_pnl)

                if ce_h >= ce_sl_price:
                    print('\nCall SL HIT ', check_time.time())
                    
                    if check_time.time() != datetime.time(9,15,59):
                        booked_ce_pnl = booked_ce_pnl + (ce_slipage_price - ce_sl_price)
                        live_ce_pnl = booked_ce_pnl
                    else:
                        booked_ce_pnl = booked_ce_pnl + ce_pnl
                        live_ce_pnl = booked_ce_pnl
                    
                    total_pnl = live_ce_pnl
                    print('\nStrategy Over\n')
                    print('\nTotal PNL : ', total_pnl)

                    today_pnl = total_pnl - previous_day_pnl
                    print('\nTODAY PNL : ',today_pnl)
                    
                    gsheet.Update_a_cell(BT_sheet, 'F', ts_ce_index, 'HIT')
                    gsheet.Update_cell(BT_sheet, ts_ce_index, 11, live_ce_pnl)
                    
                    if datetime.datetime.today().date() == check_time.date():
                        gsheet.Update_PNL_On_Sheet(caps_strategy, today_pnl)

                    check_ce_sl = False

                check_time = check_time + datetime.timedelta(minutes=1)

        if modify_prices:
            if datetime.datetime.now() > entry_time + datetime.timedelta(minutes=2):
                ce_price = candle_data(ce_scrip_token, entry_time)[-1]
                ce_sl_price = int(round((ce_price * (1+(sl/100))) * 100, -1) + 5)/100

                print('Modified sl prices :', ce_sl_price)

                ce_slipage_price = ce_price - (ce_price * slipage)
                gsheet.Update_Batch(BT_sheet, f"B{ts_ce_index}:C{ts_ce_index}", [[ce_price, ce_sl_price]])
                gsheet.cell_modified(BT_sheet, f"C{ts_ce_index}")

                modify_prices = False

        if check_ce_sl == modify_prices == False and sell_flag == 1:
            break

        if check_time.time() > exit_time:
            check_time = check_time - datetime.timedelta(minutes=1)

            if 'Expiry' in Parameter.Get_trading_day() and datetime.datetime.today().date() == check_time.date():

                total_pnl = live_ce_pnl
                print('\nStrategy Over\n')
                print('\nTotal PNL : ', total_pnl)

                today_pnl = total_pnl - previous_day_pnl
                print('\nTODAY PNL : ',today_pnl)

                gsheet.Update_cell(BT_sheet, ts_ce_index, 11, live_ce_pnl)
                gsheet.Update_PNL_On_Sheet(caps_strategy, today_pnl)  

                break

            check_time = datetime.datetime.combine(check_time + datetime.timedelta(days=1) , datetime.time(9,16)) - datetime.timedelta(seconds=1)
            check_time = increment_if_holiday(check_time)

            if datetime.datetime.today().date() < check_time.date():

                total_pnl = live_ce_pnl
                print('\nTotal PNL', total_pnl)

                today_pnl = total_pnl - previous_day_pnl
                print('\nTODAY PNL : ',today_pnl)

                gsheet.Update_cell(BT_sheet, ts_ce_index, 11, live_ce_pnl)
                gsheet.Update_PNL_On_Sheet(caps_strategy, today_pnl)  

                break
            else:
                total_pnl = live_ce_pnl
                print('\nTotal PNL', total_pnl)

                today_pnl = total_pnl - previous_day_pnl
                print('\nTODAY PNL : ',today_pnl)

                previous_day_pnl = live_ce_pnl
                print(f'\nNext Day {check_time.strftime("%A")}\n\n')

except Exception as e:
    msg = "?????????????????? Error !!! ?????????????????? \n" + caps_strategy + " Code stop "
    telegram().send_message(telegram.group.BT_Vs_Actual_diff, msg + '\n' + str(e))


# In[ ]:




