Frontend 
- npm install
- npm run dev 

Backend
- Download GCP project key JSON file with "Cloud Datastore Owener", "Storage Admin", "Storage Object Admin", "Vertex AI User" role assign
- Keep Key file in safe folder and set enviroment varibale in local machine with path of this file with key name "GOOGLE_APPLICATION_CREDENTIALS"
- pip install -r requirements.txt
- python -m venv venv
- venv\Scripts\Activate.ps1 - powershell
- uvicorn main:app --reload
