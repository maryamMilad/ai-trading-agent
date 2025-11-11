"""
Lightweight API Server for Render.com
Serves predictions to QuantConnect
"""

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
import os
from datetime import datetime

app = FastAPI(
    title="AI Trading Agent API",
    description="Serves stock predictions to QuantConnect",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

@app.get("/")
def root():
    """Root endpoint"""
    return {
        "service": "AI Trading Agent API",
        "status": "operational",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "predict": "/predict?ticker=AAPL",
            "batch": "/batch-predict?tickers=AAPL,MSFT,GOOGL"
        }
    }

@app.get("/health")
def health_check():
    """Health check for monitoring"""
    try:
        # Test database connection
        supabase.table("predictions").select("id").limit(1).execute()
        db_status = "connected"
    except:
        db_status = "disconnected"
    
    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "timestamp": datetime.now().isoformat(),
        "database": db_status
    }

@app.get("/predict")
def get_prediction(ticker: str):
    """
    Get latest prediction for a ticker
    
    Example: /predict?ticker=AAPL
    
    Returns:
        {
            "ticker": "AAPL",
            "signal": "BUY",
            "confidence": 0.75,
            "reasoning": "...",
            "timestamp": "2024-11-10T14:30:00"
        }
    """
    ticker = ticker.upper().strip()
    
    try:
        # Get latest prediction
        result = supabase.table("predictions") \
            .select("*") \
            .eq("ticker", ticker) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
        
        if not result.data:
            raise HTTPException(
                status_code=404,
                detail=f"No predictions found for {ticker}"
            )
        
        prediction = result.data[0]
        
        return {
            "ticker": ticker,
            "signal": prediction["signal"],
            "confidence": float(prediction["confidence"]),
            "reasoning": prediction["reasoning"],
            "key_factors": prediction.get("key_factors", []),
            "risks": prediction.get("risks", []),
            "timestamp": prediction["created_at"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving prediction: {str(e)}"
        )

@app.get("/batch-predict")
def batch_predict(tickers: str):
    """
    Get predictions for multiple tickers
    
    Example: /batch-predict?tickers=AAPL,MSFT,GOOGL
    
    Returns:
        {
            "predictions": [
                {"ticker": "AAPL", "signal": "BUY", ...},
                {"ticker": "MSFT", "signal": "HOLD", ...}
            ],
            "count": 2
        }
    """
    ticker_list = [t.strip().upper() for t in tickers.split(",")]
    
    predictions = []
    for ticker in ticker_list:
        try:
            pred = get_prediction(ticker)
            predictions.append(pred)
        except HTTPException as e:
            predictions.append({
                "ticker": ticker,
                "error": e.detail,
                "status": "not_found"
            })
    
    return {
        "predictions": predictions,
        "count": len(predictions),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/history/{ticker}")
def get_history(ticker: str, limit: int = 10):
    """
    Get prediction history for a ticker
    
    Example: /history/AAPL?limit=5
    """
    ticker = ticker.upper().strip()
    
    try:
        result = supabase.table("predictions") \
            .select("*") \
            .eq("ticker", ticker) \
            .order("created_at", desc=True) \
            .limit(min(limit, 50)) \
            .execute()
        
        return {
            "ticker": ticker,
            "history": result.data,
            "count": len(result.data)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving history: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
