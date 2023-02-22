from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from toolkit.logger import Logger
import inspect
from user import load_all_users
import pandas as pd
from tests.big import test_trades as big

logging = Logger(20)  # 2nd param 'logfile.log'
fpath = '../../../confid/bypass_multi.xlsx'

# get leader and followers instance
obj_ldr, objs_usr = load_all_users(fpath)


pages = ['home']
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
jt = Jinja2Templates(directory="templates")


@ app.get("/dummy", response_class=HTMLResponse)
async def home(request: Request):
    ctx = {"request": request, "title": inspect.stack()[0][3]}
    return jt.TemplateResponse("index.html", ctx)


@ app.get("/", response_class=HTMLResponse)
async def users(request: Request, lst_sort_col: str = None):
    lst = []
    for u in objs_usr:
        # lst.append(users[u]._broker.profile)
        lst.append(vars(objs_usr[u]))
    if not lst:
        lst = [{'message': 'no data'}]
    df = pd.DataFrame(
        data=lst,
        columns=lst[0].keys()
    )
    df.set_index(['_userid'], inplace=True)
    df.drop(columns=['_broker', '_enctoken',
            '_totp', '_password'], inplace=True)
    if lst_sort_col:
        df.sort_values(by=[lst_sort_col], ascending=True, inplace=True)
    ctx = {"request": request, "title": inspect.stack()[0][3], 'pages': pages,
           "data": df.to_html()}
    return jt.TemplateResponse("pandas.html", ctx)


@ app.get("/positionbook/{user_id}", response_class=HTMLResponse)
async def positions(request: Request, user_id):
    ctx = {"request": request, "title": inspect.stack()[0][3], 'pages': pages}
    ctx['tx'] = ['message']
    ctx['data'] = ['no data']
    body = []
    for u in objs_usr:
        print(u)
        if u.get('user_id') == user_id:
            for f_dct in u._broker.positions:
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
