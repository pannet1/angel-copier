from toolkit.fileutils import Fileutils
from user import User
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from toolkit.logger import Logger
import inspect

logging = Logger(20)  # 2nd param 'logfile.log'
fpath = '../../../../confid/ketan_users.xls'
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

pages = ['home']
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
jt = Jinja2Templates(directory="templates")


@ app.get("/dummy", response_class=HTMLResponse)
async def home(request: Request):
    ctx = {"request": request, "title": inspect.stack()[0][3]}
    return jt.TemplateResponse("index.html", ctx)


@ app.get("/", response_class=HTMLResponse)
async def users(request: Request):
    ctx = {"request": request, "title": inspect.stack()[0][3], 'pages': pages}
    ctx['th'] = ['message']
    ctx['data'] = ["no data"]
    body = []
    for keys, row in objs_usr.items():
        th = ['user id', 'target', 'max loss', 'disabled', 'orders', 'pnl']
        td = [
            row._userid,
            row._target,
            row._max_loss,
            row._disabled,
            ]
        u = objs_usr.get(row._userid)
        dict_orders = u._broker.orders
        orders = dict_orders.get('data', [])
        completed_count = 0
        if isinstance(orders, list):
            for item in orders:
                if isinstance(item, dict) and item.get('orderstatus') == 'complete':
                    completed_count += 1
        td.append(completed_count)
        pos = u._broker.positions
        lst_pos = pos.get('data', [])
        sum = 0
        for dct in lst_pos:
            sum += int(float(dct.get('pnl', 0)))
        td.append(sum)
        body.append(td)
    if len(body) > 0:
        ctx['th'] = th
        ctx['data'] = body
    return jt.TemplateResponse("users.html", ctx)


@app.get("/orderbook/{user_id}", response_class=HTMLResponse)
async def orders(request: Request,
                    user_id: str = 'no data'):
    ctx = {"request": request, "title": inspect.stack()[0][3], 'pages': pages}
    ctx['th'] = ['message']
    ctx['data'] = [user_id]
    if objs_usr.get(user_id, None):
        body = []
        u = objs_usr[user_id]
        pos = u._broker.orders
        lst_pos = pos.get('data', [])
        pop_keys = [
                'variety',
                'producttype',
                'duration',
                'price',
                'squareoff',
                'trailingstoploss',
                'stoploss',
                'triggerprice',
                'disclosedquantity',
                'exchange',
                'symboltoken',
                'ordertag',
                'instrumenttype',
                'expirydate',
                'strikeprice',
                'optiontype',
                'filledshares',
                'unfilledshares',
                'cancelsize',
                'status',
                'exchtime',
                'exchorderupdatetime',
                'fillid',
                'filltime',
                'parentorderid'
                ]
        for f_dct in lst_pos:
            [f_dct.pop(key) for key in pop_keys]
            quantity = f_dct.pop('quantity', 0)
            lotsize = f_dct.pop('lotsize', 0)
            try:
                lots = int(quantity) / int(lotsize)
            except Exception as e:
                print({e})
                f_dct['quantity'] = quantity
            else:
                f_dct['quantity'] = int(lots)
            k = f_dct.keys()
            th = list(k)
            v = f_dct.values()
            td = list(v)
            body.append(td)
        if len(body) > 0:
            ctx['th'] = th
            ctx['data'] = body
    return jt.TemplateResponse("table.html", ctx)


@app.get("/positionbook/{user_id}", response_class=HTMLResponse)
async def positions(request: Request,
                    user_id: str = 'no data'):
    ctx = {"request": request, "title": inspect.stack()[0][3], 'pages': pages}
    ctx['th'] = ['message']
    ctx['data'] = [user_id]
    if objs_usr.get(user_id, None):
        body = []
        u = objs_usr[user_id]
        pos = u._broker.positions
        lst_pos = pos.get('data', [])
        pop_keys = [
                "symboltoken",
                "instrumenttype",
                "priceden",
                "pricenum",
                "genden",
                "gennum",
                "precision",
                "multiplier",
                "boardlotsize",
                "exchange",
                "tradingsymbol",
                "symbolgroup",
                "cfbuyqty",
                "cfsellqty",
                "cfbuyamount",
                "cfsellamount",
                "buyavgprice",
                "sellavgprice",
                "avgnetprice",
                "netvalue",
                "totalbuyvalue",
                "totalsellvalue",
                "cfbuyavgprice",
                "cfsellavgprice",
                "totalbuyavgprice",
                "totalsellavgprice",
                "netprice",
                "buyqty",
                "sellqty",
                "buyamount",
                "sellamount",
                "close"
                ]
        for f_dct in lst_pos:
            [f_dct.pop(key) for key in pop_keys]
            quantity = f_dct.pop('netqty', 0)
            lotsize = f_dct.pop('lotsize', 0)
            try:
                lots = int(quantity) / int(lotsize)
            except Exception as e:
                print({e})
                f_dct['netqty'] = quantity
            else:
                f_dct['netqty'] = int(lots)
            k = f_dct.keys()
            th = list(k)
            v = f_dct.values()
            td = list(v)
            body.append(td)
        if len(body) > 0:
            ctx['th'] = th
            ctx['data'] = body
    return jt.TemplateResponse("table.html", ctx)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
