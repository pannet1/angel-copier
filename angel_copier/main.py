from toolkit.logger import Logger
from toolkit.fileutils import Fileutils
from copier import Copier
from user import User
from datetime import datetime as dt
from time import sleep
import pandas as pd


logging = Logger(20)  # 2nd param 'logfile.log'

ignore = [
    {'product': 'CNC'},
    {'symbol': 'HDFC-EQ', 'exchange': 'NSE'},
]
ORDER_TYPE = 'LIMIT'  # OR MARKET
BUFF = 2              # Rs. to add/sub to LTP
dct_lots = {'NIFTY': 50, 'BANKNIFTY': 25, 'FINNIFTY': 40}
maxlots = {'NIFTY': 900, 'BANKNIFTY': 1800, 'FINNIFTY': 1000}
fpath = '../../../../confid/ketan_users.xls'
dumpfile = "../../../../confid/symbols.json"
futil = Fileutils()


def load_all_users(fpath=fpath):
    lst_truth = [True, 'y', 'Y', 'Yes', 'yes', 'YES']
    users = futil.xls_to_dict(fpath)
    obj_ldr, objs_usr = None, {}
    for u in users:
        is_disabled = u.get('disabled', False)
        if is_disabled not in lst_truth:
            au = User(**u)
            au.auth()
            if not au._disabled:
                if obj_ldr:
                    objs_usr[au._userid] = au
                else:
                    obj_ldr = au
    return obj_ldr, objs_usr


# get leader and followers instance
obj_ldr, objs_usr = load_all_users()
# get copier class instance
cop = Copier(dct_lots)
# mutating combined positions followers df
# df_pos = pd.DataFrame()


def get_pos(obj):
    try:
        pos = obj._broker.positions
        data = None
        if type(pos) is dict:
            for k, v in pos.items():
                if k == "data" and v:
                    data = v
                    data = [
                        {key.replace("tradingsymbol", "symbol"): value for key, value in data[0].items()}]
                    data = [
                        {key.replace("netqty", "quantity"): value for key, value in data[0].items()}]
                    data = [
                        {key.replace("producttype", "product"): value for key, value in data[0].items()}]
    except Exception as e:
        print(f' error {e} while getting positions')
    else:
        return data


def flwrs_pos():
    """
    do necessary quantity calculations for
    the follower user accounts
    """
    try:
        df_ord = df_pos = pd.DataFrame()
        ldr_pos = get_pos(obj_ldr)
        if ldr_pos:
            dct_ldr = cop.filter_pos(ldr_pos)
            cop.set_ldr_df(dct_ldr, ignore)
            if not cop.df_ldr.empty:
                for id, u in objs_usr.items():
                    # we show position of flwrs only
                    # if there is eader positions
                    # pass the flwr multiplier from xls
                    df_tgt = cop.get_tgt_df(u._multiplier)
                    pos = get_pos(u)
                    if pos:
                        dct_flwr = cop.filter_pos(pos)
                    else:
                        dct_flwr = {}
                        # pass the user id from xls
                        df_ord = cop.get_diff_pos(u._userid, df_tgt, dct_flwr)
                        df_ord = df_ord[df_ord.quantity != '0']
                    # join the order dfs
                    if not df_ord.empty:
                        df_pos = df_ord if df_pos.empty else pd.concat(
                            [df_pos, df_ord], sort=True)
    except Exception as e:
        print(f'{e} in flwr pos')
    finally:
        return df_pos


def do_multiply(multiplied):
    global objs_usr, BUFF
    for m in multiplied:
        try:
            obj_usr = objs_usr.get(m['userid'])
            m['variety'] = 'NORMAL'
            quantity = int(m.get('quantity', 0))
            if quantity == 0:
                logging.warn('quantity cannot be zero')
            dir = 1 if quantity > 0 else -1
            m['side'] = 'BUY' if dir == 1 else 'SELL'
            """
            ensure that the symbol is in the max lots list
            if not iceberg is zero
            """
            if ORDER_TYPE == 'LIMIT':
                m['token'] = obj_usr.get_symbols(m['symbol'], dumpfile)
                dct = obj_usr.ltp(**m)
                lst_price = [value for value in dct['data'].values()]
                if type(lst_price) == list:
                    m['price'] = lst_price[-1] + (BUFF*dir)
            m['order_type'] = ORDER_TYPE
            if m['exchange'] == 'NFO':
                symbol = next(k for k, v in maxlots.items()
                              if m['symbol'].startswith(k))
                iceberg = maxlots.get(symbol, 0)
                if iceberg > 0 and abs(quantity) >= iceberg:
                    remainder = int(abs(quantity % iceberg) * dir)
                    if abs(remainder) > 0:
                        m['quantity'] = remainder
                        status = obj_usr.place_order(m)
                    times = int(abs(quantity) / iceberg)
                    for i in range(times):
                        m['quantity'] = iceberg * dir
                        status = obj_usr.place_order(m)
            else:
                m['quantity'] = int(quantity)
            status = obj_usr.place_order(m)
            logging.info(f'order: {status} {m}')
        except Exception as e:
            logging.warning(f"while multiplying {e}")


def slp_til_next_sec():
    t = dt.now()
    interval = t.microsecond / 1000000
    sleep(interval)
    return interval


if futil.is_file_not_2day(dumpfile):
    obj_ldr.contracts(dumpfile)
while True:
    try:
        data = {}
        data['positions'] = [{'MESSAGE': 'no positions yet'}]
        df_pos = flwrs_pos()
        if not df_pos.empty:
            data['positions'] = df_pos.to_dict('records')
            do_multiply(data['positions'])
        interval = 1
        sleep(interval)
        print(f'sleeping for {interval} ms')

    except Exception as e:
        print(f"error {e} in the main loop")
        sleep(1)
        continue
