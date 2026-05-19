import os
import cv2
import numpy as np
from deepface import DeepFace
from backend.database import SessionLocal
# Assuming your SQLAlchemy Model is named Worker and lives in backend.models
from backend.models import Worker 

# Configuration - Using raw string to prevent unicode escape syntax errors
DATASET_DIR = r"C:\Users\HP\PPE_WebApp_System\known_faces"  
MODEL_NAME = "ArcFace"

def register_workers_from_folders():
    db = SessionLocal()
    print(f"\n[INFO] Scanning directory: {DATASET_DIR}")
    
    if not os.path.exists(DATASET_DIR):
        print(f"[ERROR] Directory '{DATASET_DIR}' does not exist!")
        return

    # Loop through each folder (folder name = worker name)
    for worker_name in os.listdir(DATASET_DIR):
        worker_folder_path = os.path.join(DATASET_DIR, worker_name)
        
        # Skip files, only process directories
        if not os.path.isdir(worker_folder_path):
            continue
            
        print(f"\n[PROCESS] Found folder for worker: {worker_name}")
        
        # Look for images inside the worker's folder
        image_files = [f for f in os.listdir(worker_folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        
        if not image_files:
            print(f"  [WARN] No images found in folder for {worker_name}. Skipping...")
            continue
            
        # We will use the first valid image to generate the base registration embedding
        target_image_path = os.path.join(worker_folder_path, image_files[0])
        print(f"  [INFO] Extracting embedding using: {image_files[0]}")
        
        try:
            # 1. Use DeepFace to calculate the face vector
            # enforce_detection=False stops it from throwing errors on suboptimal photos
            embedding_objs = DeepFace.represent(
                img_path=target_image_path,
                model_name=MODEL_NAME,
                enforce_detection=False
            )
            
            if not embedding_objs:
                print(f"  [ERROR] No embedding returned for {worker_name}.")
                continue
                
            # Extract raw embedding array list (ArcFace returns 512 dimensions)
            embedding_list = embedding_objs[0]["embedding"]
            
            # 2. Check if worker already exists in database, or create a new row
            worker_record = db.query(Worker).filter(Worker.full_name == worker_name).first()
            
            if worker_record:
                # Update existing worker row
                worker_record.face_embedding = embedding_list
                worker_record.face_image_path = target_image_path
                print(f"  [SUCCESS] Updated embedding for existing worker: {worker_name}")
            else:
                # Insert a new worker row if they don't exist yet
                # REMOVED role="worker" to prevent the invalid keyword argument error
                new_worker = Worker(
                    employee_id=f"EMP_{worker_name.upper()[:4]}_{np.random.randint(1000, 9999)}",
                    full_name=worker_name,
                    face_embedding=embedding_list,
                    face_image_path=target_image_path
                )
                db.add(new_worker)
                print(f"  [SUCCESS] Created new worker record and saved embedding for: {worker_name}")
                
            db.commit()
            
        except Exception as e:
            print(f"  [ERROR] Failed to process face for {worker_name}: {str(e)}")
            db.rollback()

    db.close()
    print("\n[INFO] Registration process finalized.")

if __name__ == "__main__":
    register_workers_from_folders()