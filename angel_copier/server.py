from toolkit.fileutils import Fileutils
from user import User
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from toolkit.logger import Logger
import inspect
import pandas as pd
# from tests.big import test_trades as big

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
        th = ['user id', 'target', 'max loss', 'disabled']
        td = [row._userid, row._target, row._max_loss, row._disabled]
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
        for f_dct in lst_pos:
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
        for f_dct in lst_pos:
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
    uvicorn.run(app, host="0.0.0.0", port=8000)
