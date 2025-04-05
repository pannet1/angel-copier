from toolkit.logger import Logger
from toolkit.fileutils import Fileutils
from copier import Copier
from user import User
from time import sleep
import pandas as pd

futl = Fileutils()
sec_dir = "../data/"
log_file = sec_dir + "log.txt"
if not futl.is_file_exists(log_file):
    futl.add_path(log_file)
logging = Logger(20, log_file)


dumpfile = sec_dir + "symbols.json"
if not futl.is_file_exists(dumpfile):
    futl.add_path(dumpfile)

ORDER_TYPE = "MARKET"  # or LIMIT
BUFF = 2  # Rs. to add/sub to LTP
fpath = "../../ao_users.xls"
TEST = False


def get_preferences():
    try:
        yaml_file = sec_dir + "ignore.yaml"
        ignore = futl.get_lst_fm_yml(yaml_file)
        print(f"ignore: {ignore}")
        lotsize = futl.get_lst_fm_yml(sec_dir + "lotsize.yaml")
        print(f"lotsize \n {lotsize}")
        freeze = futl.get_lst_fm_yml(sec_dir + "freeze.yaml")
        print(f"freeze:{freeze}")
    except FileNotFoundError as e:
        print(f"{e} while getting preferences")
    return ignore, lotsize, freeze


ignore, lotsize, freeze = get_preferences()


def load_all_users():
    lst_truth = [True, "y", "Y", "Yes", "yes", "YES"]
    users = futl.xls_to_dict(fpath)
    obj_ldr, objs_usr = None, {}
    for u in users:
        is_disabled = u.get("disabled", False)
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
cop = Copier(lotsize)
# mutating combined positions followers df
# df_pos = pd.DataFrame()


def replace_key(fm_key, to_key, dct_keys):
    if dct_keys.get(fm_key, False):
        dct_keys[to_key] = dct_keys[fm_key]
        dct_keys.pop(fm_key)
    return dct_keys


def get_pos(obj):
    try:
        lst_pos = []
        pos = obj._broker.positions
        lst_data = pos.get("data", None)
        if isinstance(lst_data, list):
            for each_pos in lst_data:
                if isinstance(each_pos, dict):
                    dct_pos = each_pos
                    dct_pos = replace_key("tradingsymbol", "symbol", dct_pos)
                    dct_pos = replace_key("netqty", "quantity", dct_pos)
                    dct_pos = replace_key("producttype", "product", dct_pos)
                    lst_pos.append(dct_pos)
    except Exception as e:
        print(f" error {e} while getting positions")
    else:
        return lst_pos


def is_copy_ready():
    is_copy = False
    try:
        prev_df = cop.df_ldr.copy()
        ldr_pos = get_pos(obj_ldr)
        if ldr_pos and any(ldr_pos):
            dct_ldr = cop.filter_pos(ldr_pos)
            cop.set_ldr_df(dct_ldr, ignore)
            if len(prev_df) == len(cop.df_ldr) and cop.df_ldr.equals(prev_df):
                is_copy = True
    except Exception as e:
        print(f" error {e} while getting leader positions")
    finally:
        return is_copy


def flwrs_pos():
    """
    do necessary quantity calculations for
    the follower user accounts
    """
    try:
        df_ord = df_pos = pd.DataFrame()
        if not cop.df_ldr.empty:
            for _, u in objs_usr.items():
                # we show position of flwrs only
                # if there is leader positions
                # pass the flwr multiplier from xls
                df_tgt = cop.get_tgt_df(u._multiplier)
                pos = get_pos(u)
                if pos:
                    dct_flwr = cop.filter_pos(pos)
                else:
                    dct_flwr = {}
                # pass the user id from xls
                df_ord = cop.get_diff_pos(u._userid, df_tgt, dct_flwr)
                df_ord = df_ord[df_ord.quantity != "0"]
                # join the order dfs
                if not df_ord.empty:
                    df_pos = (
                        df_ord
                        if df_pos.empty
                        else pd.concat([df_pos, df_ord], sort=True)
                    )
                else:
                    print("no follower orders")
    except Exception as e:
        print(f"{e} in flwr pos")
    finally:
        return df_pos


def do_multiply(multiplied):
    global objs_usr, BUFF
    for m in multiplied:
        try:
            obj_usr = objs_usr.get(m["userid"])
            m["variety"] = "NORMAL"
            quantity = int(m.get("quantity", 0))
            if quantity == 0:
                logging.warn("quantity cannot be zero")
            dir = 1 if quantity > 0 else -1
            m["side"] = "BUY" if dir == 1 else "SELL"
            """
            ensure that the symbol is in the max lots list
            if not iceberg is zero
            """
            m["token"] = obj_usr.get_symbols(m["symbol"], dumpfile)
            if ORDER_TYPE == "LIMIT":
                dct = obj_usr.ltp(**m)
                lst_price = [value for value in dct["data"].values()]
                if isinstance(lst_price, list):
                    m["price"] = lst_price[-1] + (BUFF * dir)
            m["order_type"] = ORDER_TYPE
            if m["exchange"] == "NFO":
                symbol = next(k for k, v in freeze.items() if m["symbol"].startswith(k))
                iceberg = freeze.get(symbol, 0)
                # iceberg slicing needed
                if iceberg > 0 and abs(quantity) >= iceberg:
                    remainder = int(abs(quantity % iceberg) * dir)
                    if abs(remainder) > 0:
                        m["quantity"] = abs(remainder)
                        print(f"remainder {m['quantity']}")
                        status = obj_usr.place_order(m)
                        logging.info(f"remainder order: {status} {m}")
                    times = int(abs(quantity) / iceberg)
                    for i in range(times):
                        m["quantity"] = iceberg
                        status = obj_usr.place_order(m)
                        logging.info(f"iceberg order: {status} {m}")
                elif iceberg > 0 and abs(quantity) < iceberg:
                    # iceberg slicing not needed
                    SINGLE_ORDER = True
            else:
                SINGLE_ORDER = True

            if SINGLE_ORDER:
                SINGLE_ORDER = False
                m["quantity"] = abs(int(quantity))
                print(m)
                status = obj_usr.place_order(m)
                logging.info(f"single order: {status} {m}")
        except Exception as e:
            logging.warning(f"while multiplying {e}")


if futl.is_file_not_2day(dumpfile):
    obj_ldr.contracts(dumpfile)
while True:
    try:
        data = {}
        data["positions"] = [{"MESSAGE": "no positions yet"}]
        if is_copy_ready():
            df_pos = flwrs_pos()
            if not df_pos.empty:
                data["positions"] = df_pos.to_dict("records")
                do_multiply(data["positions"])
            else:
                print("follower positions are empty")
            interval = 1
            sleep(interval)
            logging.debug(f"sleeping for {interval} ms")

    except Exception as e:
        logging.error(f"error {e} in the main loop")
        sleep(1)
        __import__("sys").exit(1)
