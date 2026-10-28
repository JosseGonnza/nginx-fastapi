from fastapi import FastAPI

app = FastAPI()


@app.get("/users")
async def listar_users():
    return [
        {"id": 1, "nombre": "Ana"},
        {"id": 2, "nombre": "Luis"},
        {"id": 3, "nombre": "Marta"},
    ]
