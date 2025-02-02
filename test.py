from fastapi import FastAPI
import time

app = FastAPI()

logs = []

def a():
    time.sleep(2)
    logs.append("Function A executed")

def b():
    time.sleep(2)
    logs.append("Function B executed")

def c():
    time.sleep(2)
    logs.append("Function C executed")

def d():
    time.sleep(2)
    logs.append("Function D executed")

@app.post("/execute-abcd")
def execute_abcd():
    a()
    b()
    c()
    d()
    return {"message": "Functions A, B, C, and D executed in order"}

@app.get("/logs")
def get_logs():
    return {"logs": logs}