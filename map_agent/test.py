from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Hello"}

@app.get("/test")
def test():
    return {"ok": True}