from fastapi import FastAPI, Request
from pydantic import BaseModel
from fastapi.responses import JSONResponse
import joblib
import pandas as pd
import numpy as np
from dotenv import load_dotenv
import os
from openai import OpenAI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

load_dotenv()




# Load the model
rf_model = joblib.load('models/random_forest_model.pkl')
feature_names = joblib.load('models/model_features.pkl')

# fast api instance
app = FastAPI(title="Product Success Predictor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins = ['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_ORIGINS = ["http://65.2.57.138:8080/", "http://localhost:8080", "None"]
# instantiating the open ai client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

#encoded categories
encoded_categories =  ["Finance", "Healthcare", "Retail", "Tech"]


# input schema using pydantic
class ideaSchema (BaseModel):
    launchCost: float
    expectedROI:float
    creatorExperienceLevel: float
    productCategory: str
    trendAlignment: bool
    customerValidation: bool

#idea feedback schema
class ideaFeedbackSchema (BaseModel):
    ideaName:str
    ideaDescription:str

@app.post('/idea-feedback')
def idea_feedback(request_body:ideaFeedbackSchema, request:Request):

    try:
        origin = request.get("origin")
        print("origin", origin)
        if origin is not None and origin not in ALLOWED_ORIGINS:
            return JSONResponse(status_code=403, content={"error" : "this origin is not allowed to access this API"})
        # structing the prompt
        prompt = (
            f"You are a product strategist. Analyze the following startup idea and explain "
            f"in plain English whether it shows potential, any risks, or what could make it better.\n\n"
            f"Idea Name: {request_body.ideaName}\n"
            f"Idea Description: {request_body.ideaDescription}\n\n"
            f"Respond in 4-5 clear and concise sentences."

        )

        #calling the open ai api 
        gpt_response = client.chat.completions.create(
            model = "gpt-3.5-turbo",
            messages=[
                {"role" : "system", "content": 'You are an expert in evaluating product and startup ideas.'},
                {"role" : "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=250
        )
            
        explanation = gpt_response
        return explanation.choices[0].message.content
    
    except Exception as e:
        return JSONResponse(status_code=500, content={"error" : str(e)})
    


@app.post('/predict-success')
def success_predictor(request_body : ideaSchema):
    try:
    
        input_data = request_body.dict()
        

        category_str = input_data.pop("productCategory")
        #one-hot encoding the product category value as we trained the model in the same way 
        category_encoded = {
            f"productCategory_{category}" : 1 if category_str == category else 0
            for category in encoded_categories
        }

        

        #combining all inputs into one dictionary 
        full_input = {
            **input_data,
            **category_encoded
        }

    
        #creating a dataframe from the input
        input_df = pd.DataFrame([full_input])



        #ensuriing column order is the same as the model was trained on 
        input_df = input_df[feature_names]

        #calling the model to get the prediction
        prediction = rf_model.predict_proba(input_df)[0][1]
    

        return {
            "success_prediction": prediction,
            "input_data": full_input
        }
    except Exception as e:

        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))  
    uvicorn.run("main:app", host="0.0.0.0", port=port)