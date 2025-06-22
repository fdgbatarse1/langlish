from typing import Union

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse
import shutil
import os
from datetime import datetime

input_router = APIRouter()

@input_router.post("/upload-audio/")
async def upload_audio(file: UploadFile = File(...)):
    try:
        directory = "./storage/audios"
        os.makedirs(directory, exist_ok=True)

        filename = file.filename or "unknown"
        name, ext = os.path.splitext(filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{name}_{timestamp}{ext}"

        file_location = os.path.join(directory, unique_filename)
        
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return JSONResponse(content={"message": "Audio received", "filename": file.filename})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})