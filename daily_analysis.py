"""
Daily Stock Analysis Script
Runs once per day via GitHub Actions
"""

import os
import requests
import json
from datetime import datetime
from supabase import create_client, Client

# Configuration
WATCHLIST = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA"]

class SimplifiedAgent:
    def __init__(self):
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.alpha_vantage_key = os.getenv("ALPHA_VANTAGE_KEY")
        self.supabase: Client = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )
    
    def fetch_news(self, ticker: str):
        """Fetch latest news for ticker"""
        print(f"📰 Fetching news for {ticker}...")
        
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "NEWS_SENTIMENT",
            "tickers": ticker,
            "apikey": self.alpha_vantage_key,
            "limit": 20,
            "sort": "LATEST"
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if "feed" not in data:
                print(f"⚠️ No news data returned for {ticker}")
                return []
            
            articles = []
            for item in data.get("feed", [])[:10]:  # Top 10 articles
                articles.append({
                    "title": item.get("title", ""),
                    "summary": item.get("summary", ""),
                    "source": item.get("source", ""),
                    "sentiment": float(item.get("overall_sentiment_score", 0)),
                    "time": item.get("time_published", "")
                })
            
            print(f"   Found {len(articles)} articles")
            return articles
            
        except Exception as e:
            print(f"❌ Error fetching news for {ticker}: {e}")
            return []
    
    def analyze_with_claude(self, ticker: str, news: list):
        """Analyze using Claude API"""
        print(f"🤖 Analyzing {ticker} with Claude...")
        
        # Build context
        news_text = "\n".join([
            f"- {n['title']} (sentiment: {n['sentiment']:.2f}, source: {n['source']})"
            for n in news
        ])
        
        if not news_text:
            news_text = "No recent news available"
        
        # Get historical predictions
        historical = self.get_historical_predictions(ticker, limit=5)
        historical_text = "\n".join([
            f"- {h['created_at'][:10]}: {h['signal']} "
            f"(confidence: {h['confidence']}) - {h['reasoning'][:80]}..."
            for h in historical
        ]) if historical else "No historical predictions yet"
        
        prompt = f"""Analyze {ticker} for a trading decision.

RECENT NEWS (Last 24-48 hours):
{news_text}

PREVIOUS PREDICTIONS:
{historical_text}

Based on this information, provide a trading recommendation.

Consider:
1. News sentiment and credibility
2. Historical patterns (if available)
3. Potential risks and opportunities
4. Market context

Respond in this EXACT JSON format (no extra text):
{{
  "signal": "BUY" or "SELL" or "HOLD",
  "confidence": 0.75,
  "reasoning": "Clear 2-3 sentence explanation of why this signal",
  "key_factors": ["factor1", "factor2", "factor3"],
  "risks": ["risk1", "risk2"],
  "timeframe": "short-term (1-5 days)"
}}"""

        # Call Claude
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1500,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Extract text from response
            text = result["content"][0]["text"]
            
            # Parse JSON from response
            import re
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
            if json_match:
                prediction = json.loads(json_match.group())
                print(f"   Signal: {prediction['signal']} (confidence: {prediction['confidence']})")
                return prediction
            else:
                print(f"⚠️ Could not parse JSON from Claude response")
                return None
                
        except Exception as e:
            print(f"❌ Error calling Claude: {e}")
            return None
    
    def get_historical_predictions(self, ticker: str, limit: int = 5):
        """Get past predictions for context"""
        try:
            result = self.supabase.table("predictions") \
                .select("*") \
                .eq("ticker", ticker) \
                .order("created_at", desc=True) \
                .limit(limit) \
                .execute()
            
            return result.data if result.data else []
        except Exception as e:
            print(f"⚠️ Error fetching historical: {e}")
            return []
    
    def store_prediction(self, ticker: str, prediction: dict):
        """Store prediction in Supabase"""
        print(f"💾 Storing prediction for {ticker}...")
        
        try:
            data = {
                "ticker": ticker,
                "signal": prediction["signal"],
                "confidence": float(prediction["confidence"]),
                "reasoning": prediction["reasoning"],
                "key_factors": prediction.get("key_factors", []),
                "risks": prediction.get("risks", []),
                "created_at": datetime.now().isoformat()
            }
            
            result = self.supabase.table("predictions").insert(data).execute()
            print(f"   ✅ Stored successfully")
            return result
            
        except Exception as e:
            print(f"   ❌ Error storing prediction: {e}")
            return None

def main():
    """Main execution"""
    print("=" * 60)
    print("🚀 AI Trading Agent - Daily Analysis")
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Initialize agent
    agent = SimplifiedAgent()
    
    # Analyze each stock
    results = []
    for ticker in WATCHLIST:
        print(f"\n{'='*60}")
        print(f"📊 Analyzing {ticker}")
        print(f"{'='*60}")
        
        # Fetch news
        news = agent.fetch_news(ticker)
        
        # Analyze
        prediction = agent.analyze_with_claude(ticker, news)
        
        if prediction:
            # Store prediction
            agent.store_prediction(ticker, prediction)
            results.append({
                "ticker": ticker,
                "status": "success",
                "signal": prediction["signal"],
                "confidence": prediction["confidence"]
            })
        else:
            results.append({
                "ticker": ticker,
                "status": "failed"
            })
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 SUMMARY")
    print(f"{'='*60}")
    for r in results:
        if r["status"] == "success":
            print(f"{r['ticker']}: {r['signal']} (confidence: {r['confidence']:.2f})")
        else:
            print(f"{r['ticker']}: ❌ Failed")
    
    print(f"\n✅ Analysis complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
