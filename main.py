from fastapi import FastAPI
from database import engine, Base
from routes import student, assignment, class_schedule, application
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()


# CORS (if you're calling from localhost:3000 or any frontend)
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create all tables in the database (can be disabled in production)
# Base.metadata.create_all(bind=engine)

# Register API routers
app.include_router(student.router)
app.include_router(assignment.router)
app.include_router(class_schedule.router)
app.include_router(application.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Python API backend"}
